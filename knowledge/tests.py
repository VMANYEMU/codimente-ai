from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from ai.models import Assistant, AssistantAccess
from core.models import (
    AuditLog,
    Organisation,
    OrganisationMembership,
)
from knowledge.forms import DocumentUploadForm
from knowledge.models import Document, KnowledgeBase


def _run_worker_synchronously(document_id):

    from knowledge.services import processing_worker

    processing_worker._process_in_thread(document_id)


class KnowledgeFixtureMixin:

    def setUp(self):

        self.organisation = Organisation.objects.create(
            name="Codimente Demo Organisation",
        )

        self.other_organisation = Organisation.objects.create(
            name="Other Organisation",
        )

        self.admin = User.objects.create_user(
            username="orgadmin",
            password="testpass123",
        )

        self.member = User.objects.create_user(
            username="member",
            password="testpass123",
        )

        self.admin_membership = (
            OrganisationMembership.objects.create(
                organisation=self.organisation,
                user=self.admin,
                role="admin",
                is_active=True,
            )
        )

        OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role="user",
            is_active=True,
        )

        self.assistant = Assistant.objects.create(
            organisation=self.organisation,
            name="Human Resources",
            slug="human-resources",
            is_active=True,
        )

        self.knowledge_base = KnowledgeBase.objects.create(
            organisation=self.organisation,
            assistant=self.assistant,
            name="Human Resources Knowledge",
        )

        self.other_assistant = Assistant.objects.create(
            organisation=self.other_organisation,
            name="Other HR",
            slug="human-resources",
            is_active=True,
        )

    def _upload(self, filename="policy.pdf"):

        from django.core.files.uploadedfile import (
            SimpleUploadedFile,
        )

        return SimpleUploadedFile(
            filename,
            b"%PDF-1.4 fake pdf bytes",
            content_type="application/pdf",
        )


class KnowledgeHomeTests(KnowledgeFixtureMixin, TestCase):

    def test_requires_admin_role(self):

        self.client.login(
            username="member",
            password="testpass123",
        )

        response = self.client.get(
            reverse("knowledge-home")
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_sees_sections(self):

        self.client.login(
            username="orgadmin",
            password="testpass123",
        )

        response = self.client.get(reverse("knowledge-home"))

        self.assertEqual(response.status_code, 200)

        sections = response.context["sections"]

        self.assertEqual(len(sections), 1)

        self.assertEqual(
            sections[0]["assistant"].slug,
            "human-resources",
        )


class DocumentUploadTests(KnowledgeFixtureMixin, TestCase):
    """
    View-level upload tests. The processing worker is
    mocked out here: running it would close the shared
    test database connection (close_old_connections), so
    worker execution is covered by the
    TransactionTestCase suite below.
    """

    def test_upload_defers_processing_until_commit(self):

        self.client.login(
            username="orgadmin",
            password="testpass123",
        )

        url = reverse(
            "document-upload",
            args=[self.assistant.slug],
        )

        # The patch must be entered BEFORE the capture so
        # it is still active when the captured callbacks
        # execute (with-blocks exit in reverse order).

        with mock.patch(
            "knowledge.views._spawn_processing",
        ) as fake_spawn, self.captureOnCommitCallbacks(
            execute=True,
        ):

            response = self.client.post(
                url,
                {
                    "title": "HR Policy",
                    "file": self._upload(),
                },
            )

        self.assertRedirects(
            response,
            reverse("knowledge-home"),
        )

        document = Document.objects.get(title="HR Policy")

        # The upload returns immediately with the document
        # pending; the worker owns the later transitions.

        self.assertEqual(
            document.status,
            "pending",
        )

        self.assertFalse(document.is_processed)

        self.assertTrue(
            AuditLog.objects.filter(
                action="document.uploaded",
                object_id=str(document.id),
            ).exists()
        )

        # Processing is deferred until the upload
        # transaction commits.

        fake_spawn.assert_called_once_with(document.id)

    def test_upload_rejects_bad_extension(self):

        self.client.login(
            username="orgadmin",
            password="testpass123",
        )

        url = reverse(
            "document-upload",
            args=[self.assistant.slug],
        )

        response = self.client.post(
            url,
            {
                "title": "Malware",
                "file": self._upload("malware.exe"),
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            Document.objects.filter(title="Malware").exists()
        )

        form = response.context["form"]

        self.assertIn("file", form.errors)

    def test_member_cannot_upload(self):

        self.client.login(
            username="member",
            password="testpass123",
        )

        url = reverse(
            "document-upload",
            args=[self.assistant.slug],
        )

        response = self.client.post(
            url,
            {
                "title": "Sneaky",
                "file": self._upload(),
            },
        )

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            Document.objects.filter(title="Sneaky").exists()
        )


class DocumentProcessingTests(
    KnowledgeFixtureMixin,
    TransactionTestCase,
):
    """
    End-to-end processing tests. TransactionTestCase keeps
    every query in autocommit, so the worker may close and
    reopen connections exactly as it does in production.
    """

    def _upload_document(self, title):

        self.client.login(
            username="orgadmin",
            password="testpass123",
        )

        url = reverse(
            "document-upload",
            args=[self.assistant.slug],
        )

        return self.client.post(
            url,
            {
                "title": title,
                "file": self._upload(),
            },
        )

    def _mock_pipeline(self, embed_kwargs):

        return (
            mock.patch(
                "knowledge.views._spawn_processing",
                side_effect=_run_worker_synchronously,
            ),
            mock.patch(
                "knowledge.services.document_processor."
                "EmbeddingService.embed_texts",
                **embed_kwargs,
            ),
            mock.patch(
                "knowledge.services.document_processor."
                "extract_pdf",
                return_value=[
                    {
                        "page": 1,
                        "text": "Annual leave is 25 days.",
                    }
                ],
            ),
        )

    def test_upload_processes_document_end_to_end(self):

        embeds, extracts, pdfs = self._mock_pipeline(
            {"return_value": [[0.1] * 384]},
        )

        with embeds, extracts, pdfs:

            response = self._upload_document("HR Policy")

        self.assertRedirects(
            response,
            reverse("knowledge-home"),
        )

        document = Document.objects.get(title="HR Policy")

        self.assertEqual(
            document.status,
            "processed",
        )

        self.assertTrue(document.is_processed)

        self.assertEqual(
            document.chunks.count(),
            1,
        )

        # The worker records a completion audit event.

        self.assertTrue(
            AuditLog.objects.filter(
                action="document.processed",
                object_id=str(document.id),
            ).exists()
        )

    def test_processing_failure_marks_failed_and_audits(self):

        embeds, extracts, pdfs = self._mock_pipeline(
            {
                "side_effect": RuntimeError(
                    "embedding backend down"
                ),
            },
        )

        with embeds, extracts, pdfs:

            self._upload_document("Broken Doc")

        document = Document.objects.get(title="Broken Doc")

        self.assertEqual(
            document.status,
            "failed",
        )

        self.assertFalse(document.is_processed)

        self.assertEqual(
            document.chunks.count(),
            0,
        )

        event = AuditLog.objects.get(
            action="document.failed",
            object_id=str(document.id),
        )

        self.assertIn(
            "embedding backend down",
            event.detail["error"],
        )


class DocumentActionTests(KnowledgeFixtureMixin, TestCase):

    def _create_document(self):

        return Document.objects.create(
            knowledge_base=self.knowledge_base,
            title="HR Policy",
            file="knowledge/documents/hr-policy.pdf",
            is_processed=True,
            status="processed",
        )

    def test_reprocess_marks_pending_and_audits(self):

        document = self._create_document()

        self.client.login(
            username="orgadmin",
            password="testpass123",
        )

        url = reverse(
            "document-reprocess",
            args=[document.id],
        )

        with mock.patch(
            "knowledge.views._spawn_processing",
        ) as fake_spawn, self.captureOnCommitCallbacks(
            execute=True,
        ):

            response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse("knowledge-home"),
        )

        document.refresh_from_db()

        self.assertEqual(
            document.status,
            "pending",
        )

        fake_spawn.assert_called_once_with(document.id)

        self.assertTrue(
            AuditLog.objects.filter(
                action="document.reprocess_requested",
                object_id=str(document.id),
            ).exists()
        )

    def test_reprocess_rejects_get_requests(self):

        document = self._create_document()

        self.client.login(
            username="orgadmin",
            password="testpass123",
        )

        url = reverse(
            "document-reprocess",
            args=[document.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            405,
        )

    def test_status_endpoint_returns_payload(self):

        document = self._create_document()

        self.client.login(
            username="orgadmin",
            password="testpass123",
        )

        url = reverse(
            "document-status",
            args=[document.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["status"],
            "processed",
        )

        self.assertEqual(
            data["document_id"],
            document.id,
        )

        self.assertIn(
            "chunk_count",
            data,
        )

    def test_status_endpoint_hides_foreign_documents(self):

        document = self._create_document()

        other_admin = User.objects.create_user(
            username="otheradmin",
            password="testpass123",
        )

        OrganisationMembership.objects.create(
            organisation=self.other_organisation,
            user=other_admin,
            role="admin",
            is_active=True,
        )

        self.client.login(
            username="otheradmin",
            password="testpass123",
        )

        url = reverse(
            "document-status",
            args=[document.id],
        )

        response = self.client.get(url)

        # Org-scoped lookup: foreign documents do not
        # exist as far as this admin is concerned.

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_status_endpoint_refuses_non_admins(self):

        document = self._create_document()

        self.client.login(
            username="member",
            password="testpass123",
        )

        url = reverse(
            "document-status",
            args=[document.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_other_organisation_admin_cannot_delete(self):

        document = self._create_document()

        # An admin of another organisation must not be able
        # to delete this document, even with the id.

        other_admin = User.objects.create_user(
            username="otheradmin",
            password="testpass123",
        )

        other_membership = (
            OrganisationMembership.objects.create(
                organisation=self.other_organisation,
                user=other_admin,
                role="admin",
                is_active=True,
            )
        )

        AssistantAccess.objects.create(
            membership=other_membership,
            assistant=self.other_assistant,
        )

        self.client.login(
            username="otheradmin",
            password="testpass123",
        )

        url = reverse(
            "document-delete",
            args=[document.id],
        )

        response = self.client.post(url)

        # The org-scoped lookup hides foreign documents
        # behind a 404 instead of leaking their existence
        # with a 403.

        self.assertEqual(response.status_code, 404)

        self.assertTrue(
            Document.objects.filter(id=document.id).exists()
        )

    def test_admin_can_delete(self):

        document = self._create_document()

        self.client.login(
            username="orgadmin",
            password="testpass123",
        )

        url = reverse(
            "document-delete",
            args=[document.id],
        )

        response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse("knowledge-home"),
        )

        self.assertFalse(
            Document.objects.filter(id=document.id).exists()
        )

        self.assertTrue(
            AuditLog.objects.filter(
                action="document.deleted",
                object_id=str(document.id),
            ).exists()
        )

    def test_delete_rejects_get_requests(self):

        document = self._create_document()

        self.client.login(
            username="orgadmin",
            password="testpass123",
        )

        url = reverse(
            "document-delete",
            args=[document.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            405,
        )


class DocumentFormTests(KnowledgeFixtureMixin, TestCase):

    def test_rejects_oversized_file(self):

        from knowledge.forms import MAX_UPLOAD_MB

        big_file = ContentFile(
            b"x" * (MAX_UPLOAD_MB * 1024 * 1024 + 1),
            name="huge.pdf",
        )

        form = DocumentUploadForm(
            files={"file": big_file},
            data={"title": ""},
        )

        self.assertFalse(form.is_valid())

        self.assertIn("file", form.errors)


class SeedOrganisationCommandTests(TestCase):
    """
    The seeder is the deployment path for portal access:
    it must be idempotent, never reset passwords, and wire
    up accounts that were created by hand in the Django
    admin (membership + assistant access), not just brand
    new users.
    """

    def test_seeds_fresh_environment(self):

        call_command(
            "seed_organisation",
            "--admin-password",
            "seedpass123",
        )

        organisation = Organisation.objects.get(
            name="Codimente Demo Organisation",
        )

        self.assertEqual(
            Assistant.objects.filter(
                organisation=organisation,
            ).count(),
            5,
        )

        admin = User.objects.get(username="admin")

        membership = OrganisationMembership.objects.get(
            organisation=organisation,
            user=admin,
        )

        self.assertEqual(
            membership.role,
            "admin",
        )

        self.assertEqual(
            AssistantAccess.objects.filter(
                membership=membership,
            ).count(),
            5,
        )

    def test_existing_user_is_wired_for_portal_access(self):

        # An account created by hand in the Django admin:
        # no membership, no assistant access, a password
        # only its creator knows. Seeding must make it
        # fully usable without touching the password.

        User.objects.create_user(
            username="guest",
            password="original-pass-123",
        )

        call_command(
            "seed_organisation",
            "--admin-username",
            "guest",
            "--django-admin",
        )

        guest = User.objects.get(username="guest")

        organisation = Organisation.objects.get()

        membership = OrganisationMembership.objects.get(
            user=guest,
        )

        self.assertEqual(
            membership.organisation,
            organisation,
        )

        self.assertEqual(
            membership.role,
            "admin",
        )

        self.assertEqual(
            AssistantAccess.objects.filter(
                membership=membership,
            ).count(),
            5,
        )

        # Django admin status granted, password untouched.

        self.assertTrue(guest.is_staff)

        self.assertTrue(guest.is_superuser)

        self.assertTrue(
            guest.check_password("original-pass-123"),
        )

    def test_rerun_is_idempotent(self):

        call_command(
            "seed_organisation",
            "--admin-password",
            "seedpass123",
        )

        call_command(
            "seed_organisation",
            "--admin-password",
            "other-pass",
        )

        self.assertEqual(
            Organisation.objects.count(),
            1,
        )

        self.assertEqual(
            OrganisationMembership.objects.count(),
            1,
        )

        self.assertEqual(
            AssistantAccess.objects.count(),
            5,
        )

        admin = User.objects.get(username="admin")

        # The password set on creation survives reruns;
        # a rerun must never lock the admin out.

        self.assertTrue(
            admin.check_password("seedpass123"),
        )

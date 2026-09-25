from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from ai.models import Assistant, AssistantAccess
from core.models import Organisation, OrganisationMembership
from knowledge.forms import DocumentUploadForm
from knowledge.models import Document, KnowledgeBase


class KnowledgeViewTestBase(TestCase):

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


class KnowledgeHomeTests(KnowledgeViewTestBase):

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


class DocumentUploadTests(KnowledgeViewTestBase):

    def test_upload_processes_document(self):

        self.client.login(
            username="orgadmin",
            password="testpass123",
        )

        url = reverse(
            "document-upload",
            args=[self.assistant.slug],
        )

        with mock.patch(
            "knowledge.services.document_processor."
            "EmbeddingService.embed_texts",
            return_value=[[0.1] * 384],
        ), mock.patch(
            "knowledge.services.document_processor."
            "extract_pdf",
            return_value=[
                {"page": 1, "text": "Annual leave is 25 days."}
            ],
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

        self.assertTrue(document.is_processed)

        self.assertEqual(
            document.chunks.count(),
            1,
        )

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


class DocumentActionTests(KnowledgeViewTestBase):

    def _create_document(self):

        return Document.objects.create(
            knowledge_base=self.knowledge_base,
            title="HR Policy",
            file="knowledge/documents/hr-policy.pdf",
            is_processed=True,
        )

    def test_reprocess_runs(self):

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
            "knowledge.views.process_document",
            return_value=5,
        ) as fake_process:

            response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse("knowledge-home"),
        )

        fake_process.assert_called_once()

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


class DocumentFormTests(KnowledgeViewTestBase):

    def test_rejects_oversized_file(self):

        from django.core.files.uploadedfile import (
            SimpleUploadedFile,
        )

        from knowledge.forms import MAX_UPLOAD_MB

        big_file = SimpleUploadedFile(
            "huge.pdf",
            b"x" * (MAX_UPLOAD_MB * 1024 * 1024 + 1),
        )

        form = DocumentUploadForm(
            files={"file": big_file},
            data={"title": ""},
        )

        self.assertFalse(form.is_valid())

        self.assertIn("file", form.errors)

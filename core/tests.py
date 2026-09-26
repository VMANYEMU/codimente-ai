from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase
from django.urls import reverse

from ai.models import Assistant, AssistantAccess
from core import health_views
from core.models import AuditLog, Organisation, OrganisationMembership
from core.services import record_audit


class AuditServiceTests(TestCase):

    def setUp(self):

        self.organisation = Organisation.objects.create(
            name="Codimente Demo Organisation",
        )

        self.user = User.objects.create_user(
            username="orguser",
            password="testpass123",
        )

        self.membership = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.user,
            role="admin",
            is_active=True,
        )

    def test_record_audit_persists_event(self):

        record_audit(
            organisation=self.organisation,
            actor=self.user,
            action="document.uploaded",
            object_type="document",
            object_id=7,
            detail={"title": "HR Policy"},
        )

        self.assertEqual(AuditLog.objects.count(), 1)

        event = AuditLog.objects.get()

        self.assertEqual(event.actor, self.user)

        self.assertEqual(
            event.actor_username,
            "orguser",
        )

        self.assertEqual(
            event.detail["title"],
            "HR Policy",
        )

        self.assertEqual(
            event.object_id,
            "7",
        )

    def test_record_audit_handles_anonymous_actor(self):

        event = record_audit(
            organisation=self.organisation,
            actor=AnonymousUser(),
            action="auth.login_failed",
        )

        self.assertIsNone(event.actor)

        self.assertEqual(
            event.actor_username,
            "",
        )

    def test_record_audit_never_raises(self):

        # Unserialisable audit detail must never break the
        # request that triggered the audit event.

        event = record_audit(
            organisation=self.organisation,
            actor=self.user,
            action="test.unserialisable",
            detail={"value": object()},
        )

        self.assertIsNone(event)

        self.assertEqual(AuditLog.objects.count(), 0)


class AuthAuditSignalTests(TestCase):

    def setUp(self):

        self.organisation = Organisation.objects.create(
            name="Codimente Demo Organisation",
        )

        self.user = User.objects.create_user(
            username="orguser",
            password="testpass123",
        )

        self.membership = OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.user,
            role="user",
            is_active=True,
        )

    def test_login_is_audited(self):

        self.client.login(
            username="orguser",
            password="testpass123",
        )

        event = AuditLog.objects.get(
            action="auth.login",
        )

        self.assertEqual(
            event.actor,
            self.user,
        )

        self.assertEqual(
            event.organisation,
            self.organisation,
        )

    def test_logout_is_audited(self):

        self.client.login(
            username="orguser",
            password="testpass123",
        )

        AuditLog.objects.all().delete()

        self.client.logout()

        self.assertTrue(
            AuditLog.objects.filter(
                action="auth.logout",
            ).exists()
        )

    def test_failed_login_is_audited(self):

        response = self.client.post(
            reverse("login"),
            {
                "username": "orguser",
                "password": "definitely-wrong",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        event = AuditLog.objects.get(
            action="auth.login_failed",
        )

        self.assertEqual(
            event.detail["username"],
            "orguser",
        )

    def test_access_grant_is_audited(self):

        assistant = Assistant.objects.create(
            organisation=self.organisation,
            name="Human Resources",
            slug="human-resources",
            is_active=True,
        )

        AssistantAccess.objects.create(
            membership=self.membership,
            assistant=assistant,
        )

        event = AuditLog.objects.get(
            action="assistant.access_granted",
        )

        self.assertEqual(
            event.organisation,
            self.organisation,
        )

        self.assertEqual(
            event.detail["assistant"],
            "human-resources",
        )

        self.assertEqual(
            event.detail["username"],
            "orguser",
        )

    def test_access_revocation_is_audited(self):

        assistant = Assistant.objects.create(
            organisation=self.organisation,
            name="Human Resources",
            slug="human-resources",
            is_active=True,
        )

        access = AssistantAccess.objects.create(
            membership=self.membership,
            assistant=assistant,
        )

        AuditLog.objects.all().delete()

        access.delete()

        self.assertTrue(
            AuditLog.objects.filter(
                action="assistant.access_revoked",
            ).exists()
        )


class OrganisationSwitchTests(TestCase):

    def setUp(self):

        self.organisation_a = Organisation.objects.create(
            name="Organisation A",
        )

        self.organisation_b = Organisation.objects.create(
            name="Organisation B",
        )

        self.user = User.objects.create_user(
            username="orguser",
            password="testpass123",
        )

        self.membership_a = (
            OrganisationMembership.objects.create(
                organisation=self.organisation_a,
                user=self.user,
                role="admin",
                is_active=True,
            )
        )

        self.membership_b = (
            OrganisationMembership.objects.create(
                organisation=self.organisation_b,
                user=self.user,
                role="user",
                is_active=True,
            )
        )

        self.assistant = Assistant.objects.create(
            organisation=self.organisation_a,
            name="Human Resources",
            slug="human-resources",
            is_active=True,
        )

        AssistantAccess.objects.create(
            membership=self.membership_a,
            assistant=self.assistant,
        )

    def _login(self):

        self.client.login(
            username="orguser",
            password="testpass123",
        )

    def test_switch_updates_session_and_audits(self):

        self._login()

        response = self.client.get(
            reverse(
                "organisation-switch",
                args=[self.membership_b.id],
            )
        )

        # Do not follow the redirect: /chat/ would return
        # 403 because this user holds no assistant access
        # in organisation B. The switch itself succeeded.

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            response["Location"],
            reverse("chat"),
        )

        self.assertEqual(
            self.client.session[
                "active_organisation_id"
            ],
            self.membership_b.id,
        )

        event = AuditLog.objects.get(
            action="organisation.switched",
        )

        self.assertEqual(
            event.organisation,
            self.organisation_b,
        )

        self.assertEqual(
            event.actor,
            self.user,
        )

    def test_switch_to_foreign_membership_is_refused(self):

        foreign_user = User.objects.create_user(
            username="foreigner",
            password="testpass123",
        )

        foreign_membership = (
            OrganisationMembership.objects.create(
                organisation=Organisation.objects.create(
                    name="Organisation C",
                ),
                user=foreign_user,
                role="admin",
                is_active=True,
            )
        )

        self._login()

        response = self.client.get(
            reverse(
                "organisation-switch",
                args=[foreign_membership.id],
            )
        )

        # Another user's membership id must not be usable:
        # the lookup is scoped to the logged-in user.

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_inactive_membership_cannot_be_selected(self):

        self.membership_b.is_active = False
        self.membership_b.save()

        self._login()

        response = self.client.get(
            reverse(
                "organisation-switch",
                args=[self.membership_b.id],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )


class AuditLogPageTests(TestCase):

    def setUp(self):

        self.organisation = Organisation.objects.create(
            name="Codimente Demo Organisation",
        )

        self.admin = User.objects.create_user(
            username="orgadmin",
            password="testpass123",
        )

        self.member = User.objects.create_user(
            username="member",
            password="testpass123",
        )

        OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.admin,
            role="admin",
            is_active=True,
        )

        OrganisationMembership.objects.create(
            organisation=self.organisation,
            user=self.member,
            role="user",
            is_active=True,
        )

    def test_admin_sees_audit_events(self):

        record_audit(
            organisation=self.organisation,
            actor=self.admin,
            action="document.uploaded",
            object_type="document",
            object_id=1,
        )

        self.client.login(
            username="orgadmin",
            password="testpass123",
        )

        response = self.client.get(
            reverse("audit-log")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "document.uploaded",
        )

    def test_member_cannot_see_audit_log(self):

        self.client.login(
            username="member",
            password="testpass123",
        )

        response = self.client.get(
            reverse("audit-log")
        )

        self.assertEqual(
            response.status_code,
            403,
        )


class ChatViewTests(TestCase):

    def setUp(self):

        self.organisation_a = Organisation.objects.create(
            name="Organisation A",
        )

        self.organisation_b = Organisation.objects.create(
            name="Organisation B",
        )

        self.user = User.objects.create_user(
            username="orguser",
            password="testpass123",
        )

        self.membership_a = (
            OrganisationMembership.objects.create(
                organisation=self.organisation_a,
                user=self.user,
                role="admin",
                is_active=True,
            )
        )

        self.membership_b = (
            OrganisationMembership.objects.create(
                organisation=self.organisation_b,
                user=self.user,
                role="user",
                is_active=True,
            )
        )

        self.assistant = Assistant.objects.create(
            organisation=self.organisation_a,
            name="Human Resources",
            slug="human-resources",
            is_active=True,
        )

        AssistantAccess.objects.create(
            membership=self.membership_a,
            assistant=self.assistant,
        )

    def test_chat_renders_for_authorised_user(self):

        self.client.login(
            username="orguser",
            password="testpass123",
        )

        response = self.client.get(
            reverse("assistant-chat",
                    args=["human-resources"])
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Human Resources",
        )

    def test_chat_requires_membership(self):

        User.objects.create_user(
            username="outsider",
            password="testpass123",
        )

        self.client.login(
            username="outsider",
            password="testpass123",
        )

        response = self.client.get(reverse("chat"))

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_other_memberships_power_the_switcher(self):

        self.client.login(
            username="orguser",
            password="testpass123",
        )

        response = self.client.get(reverse("chat"))

        other = list(
            response.context["other_memberships"]
        )

        self.assertIn(
            self.membership_b,
            other,
        )


class HealthEndpointTests(TestCase):

    def setUp(self):

        # Reset the module-level cache so every test
        # performs a fresh probe regardless of order.

        health_views._health_state.update(
            {
                "checked_at": 0.0,
                "status": None,
                "database": None,
            }
        )

    def test_health_reports_ok(self):

        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["status"], "ok")

        self.assertEqual(data["database"], "ok")

    def test_health_reports_degraded_without_database(self):

        with mock.patch(
            "core.health_views.connection"
        ) as fake_connection:

            fake_connection.cursor.side_effect = Exception(
                "database down"
            )

            response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 503)

        self.assertEqual(
            response.json()["status"],
            "degraded",
        )

    def test_health_requires_no_authentication(self):

        # Monitors cannot log in: the endpoint must stay
        # unauthenticated and leak nothing but status.

        self.client.logout()

        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)

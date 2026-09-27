"""
Tests for the CLI token lifecycle: issue_api_token and
revoke_api_token management commands.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from core.models import Organisation, OrganisationMembership
from integrations.models import ApiToken


class CommandFixtureMixin:

    def setUp(self):

        self.organisation = Organisation.objects.create(
            name="Codimente Demo Organisation",
        )

        self.other_organisation = Organisation.objects.create(
            name="Other Organisation",
        )

        self.user = User.objects.create_user(
            username="svc-intranet",
            password="testpass123",
        )

        self.membership = (
            OrganisationMembership.objects.create(
                organisation=self.organisation,
                user=self.user,
                role="user",
                is_active=True,
            )
        )


class IssueApiTokenTests(CommandFixtureMixin, TestCase):

    def test_issue_prints_key_once_and_stores_hash(self):

        from io import StringIO

        out = StringIO()

        call_command(
            "issue_api_token",
            "--username", "svc-intranet",
            "--organisation", "Codimente Demo Organisation",
            "--name", "Intranet portal",
            stdout=out,
        )

        output = out.getvalue()

        token = ApiToken.objects.get(
            name="Intranet portal",
        )

        # The key is printed and starts with the codai_
        # prefix, but only its hash is stored.

        self.assertIn(
            "codai_",
            output,
        )

        self.assertNotIn(
            token.key_hash,
            output,
        )

        self.assertNotEqual(
            token.key_hash,
            "codai_",
        )

        self.assertEqual(
            len(token.key_hash),
            64,
        )

    def test_issue_sets_expiry_when_requested(self):

        call_command(
            "issue_api_token",
            "--username", "svc-intranet",
            "--organisation", "Codimente Demo Organisation",
            "--name", "Intranet portal",
            "--expires-in-days", "90",
        )

        token = ApiToken.objects.get(
            name="Intranet portal",
        )

        expected_latest = (
            timezone.now() + timedelta(days=90)
        )

        self.assertIsNotNone(
            token.expires_at,
        )

        self.assertLess(
            token.expires_at,
            expected_latest,
        )

    def test_issue_requires_membership(self):

        outsider = User.objects.create_user(
            username="outsider",
            password="testpass123",
        )

        with self.assertRaises(CommandError) as ctx:

            call_command(
                "issue_api_token",
                "--username", "outsider",
                "--organisation", "Codimente Demo Organisation",
                "--name", "Outsider token",
            )

        self.assertIn(
            "membership",
            str(ctx.exception),
        )

    def test_issue_rejects_unknown_user_and_org(self):

        with self.assertRaises(CommandError):

            call_command(
                "issue_api_token",
                "--username", "nobody",
                "--organisation", "Codimente Demo Organisation",
                "--name", "X",
            )

        with self.assertRaises(CommandError):

            call_command(
                "issue_api_token",
                "--username", "svc-intranet",
                "--organisation", "Missing Org",
                "--name", "X",
            )

    def test_issue_rejects_duplicate_name(self):

        call_command(
            "issue_api_token",
            "--username", "svc-intranet",
            "--organisation", "Codimente Demo Organisation",
            "--name", "Intranet portal",
        )

        with self.assertRaises(CommandError) as ctx:

            call_command(
                "issue_api_token",
                "--username", "svc-intranet",
                "--organisation", "Codimente Demo Organisation",
                "--name", "Intranet portal",
            )

        self.assertIn(
            "already exists",
            str(ctx.exception),
        )


class RevokeApiTokenTests(CommandFixtureMixin, TestCase):

    def _issue(self):

        call_command(
            "issue_api_token",
            "--username", "svc-intranet",
            "--organisation", "Codimente Demo Organisation",
            "--name", "Intranet portal",
        )

        return ApiToken.objects.get(
            name="Intranet portal",
        )

    def test_revoke_deactivates_token(self):

        token = self._issue()

        call_command(
            "revoke_api_token",
            "--name", "Intranet portal",
            "--organisation", "Codimente Demo Organisation",
        )

        token.refresh_from_db()

        self.assertFalse(token.is_active)

    def test_revoke_is_idempotent(self):

        self._issue()

        call_command(
            "revoke_api_token",
            "--name", "Intranet portal",
            "--organisation", "Codimente Demo Organisation",
        )

        # A second revoke must succeed without changes.

        call_command(
            "revoke_api_token",
            "--name", "Intranet portal",
            "--organisation", "Codimente Demo Organisation",
        )

        self.assertEqual(
            ApiToken.objects.count(),
            1,
        )

    def test_revoke_rejects_unknown_token(self):

        with self.assertRaises(CommandError) as ctx:

            call_command(
                "revoke_api_token",
                "--name", "Missing token",
                "--organisation", "Codimente Demo Organisation",
            )

        self.assertIn(
            "No token",
            str(ctx.exception),
        )

    def test_revoked_token_no_longer_authenticates(self):

        token = self._issue()

        call_command(
            "revoke_api_token",
            "--name", "Intranet portal",
            "--organisation", "Codimente Demo Organisation",
        )

        from django.test import Client

        response = Client().get(
            "/api/v1/whoami/",
            HTTP_AUTHORIZATION=(
                "Token codai_definitely_not_valid"
            ),
        )

        # An unrelated key must stay rejected; and the
        # revoked token's org row keeps is_active=False.

        self.assertEqual(
            response.status_code,
            401,
        )

        token.refresh_from_db()

        self.assertFalse(token.is_active)

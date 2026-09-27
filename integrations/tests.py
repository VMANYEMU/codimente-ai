"""
Tests for external integrations: API token issuance,
authentication behaviour and token-scoped access to the
conversation API.
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ai.models import Assistant, AssistantAccess, Conversation, Message
from core.models import Organisation, OrganisationMembership
from integrations.models import ApiToken, generate_api_key, hash_api_key


class ApiTokenTestBase(TestCase):

    def setUp(self):

        # The chat rate limiter counts on the shared cache;
        # tests must start from a clean counter.

        cache.clear()

        self.organisation = Organisation.objects.create(
            name="Codimente Demo Organisation",
        )

        self.other_organisation = Organisation.objects.create(
            name="Other Organisation",
        )

        self.integration_user = User.objects.create_user(
            username="svc-intranet",
            password="testpass123",
        )

        self.membership = (
            OrganisationMembership.objects.create(
                organisation=self.organisation,
                user=self.integration_user,
                role="user",
                is_active=True,
            )
        )

        self.assistant = Assistant.objects.create(
            organisation=self.organisation,
            name="Human Resources",
            slug="human-resources",
            system_prompt="You are the HR assistant.",
            is_active=True,
        )

        AssistantAccess.objects.create(
            membership=self.membership,
            assistant=self.assistant,
        )

        self.token, self.raw_key = ApiToken.issue(
            user=self.integration_user,
            organisation=self.organisation,
            name="Intranet portal",
        )

    def _auth_header(self, key=None):

        return {
            "HTTP_AUTHORIZATION":
                "Token " + (key or self.raw_key),
        }

    def _issue_other_org_token(self):

        other_user = User.objects.create_user(
            username="other-svc",
            password="testpass123",
        )

        other_membership = (
            OrganisationMembership.objects.create(
                organisation=self.other_organisation,
                user=other_user,
                role="user",
                is_active=True,
            )
        )

        other_assistant = Assistant.objects.create(
            organisation=self.other_organisation,
            name="Other HR",
            slug="human-resources",
            is_active=True,
        )

        AssistantAccess.objects.create(
            membership=other_membership,
            assistant=other_assistant,
        )

        token, raw_key = ApiToken.issue(
            user=other_user,
            organisation=self.other_organisation,

            # Deliberately the same name as the base
            # organisation's token: uniqueness is scoped
            # per organisation.

            name="Intranet portal",
        )

        return token, raw_key


class ApiTokenModelTests(ApiTokenTestBase):

    def test_issue_stores_only_the_hash(self):

        token = ApiToken.objects.get(
            pk=self.token.pk,
        )

        # The database must never contain the raw key.

        self.assertNotEqual(
            token.key_hash,
            self.raw_key,
        )

        self.assertEqual(
            len(token.key_hash),
            64,
        )

        self.assertEqual(
            token.prefix,
            self.raw_key[:10],
        )

        self.assertTrue(
            token.matches(self.raw_key),
        )

        self.assertFalse(
            token.matches("codai_wrong_key"),
        )

    def test_token_name_is_unique_per_organisation(self):

        with self.assertRaises(IntegrityError):

            with transaction.atomic():

                ApiToken.objects.create(
                    user=self.integration_user,
                    organisation=self.organisation,
                    name="Intranet portal",
                    key_hash=hash_api_key(
                        generate_api_key(),
                    ),
                    prefix="codai_dup",
                )

    def test_same_name_allowed_in_other_organisation(self):

        other_token, _ = self._issue_other_org_token()

        self.assertEqual(
            other_token.name,
            self.token.name,
        )


class WhoamiEndpointTests(ApiTokenTestBase):

    def test_whoami_returns_token_scope(self):

        response = self.client.get(
            reverse("api-whoami"),
            **self._auth_header(),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["user"],
            "svc-intranet",
        )

        self.assertEqual(
            data["organisation"],
            "Codimente Demo Organisation",
        )

        self.assertEqual(
            data["token_name"],
            "Intranet portal",
        )

        slugs = [
            assistant["slug"]
            for assistant in data["assistants"]
        ]

        self.assertIn(
            "human-resources",
            slugs,
        )

    def test_whoami_accepts_bearer_scheme(self):

        response = self.client.get(
            reverse("api-whoami"),
            **{
                "HTTP_AUTHORIZATION":
                    "Bearer " + self.raw_key,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_whoami_rejects_missing_token(self):

        response = self.client.get(
            reverse("api-whoami"),
        )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_whoami_rejects_unknown_token(self):

        response = self.client.get(
            reverse("api-whoami"),
            **self._auth_header("codai_not_a_real_key"),
        )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_whoami_rejects_deactivated_token(self):

        self.token.is_active = False
        self.token.save()

        response = self.client.get(
            reverse("api-whoami"),
            **self._auth_header(),
        )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_whoami_rejects_expired_token(self):

        self.token.expires_at = (
            timezone.now() - timedelta(hours=1)
        )

        self.token.save()

        response = self.client.get(
            reverse("api-whoami"),
            **self._auth_header(),
        )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_whoami_rejects_deactivated_user(self):

        self.integration_user.is_active = False
        self.integration_user.save()

        response = self.client.get(
            reverse("api-whoami"),
            **self._auth_header(),
        )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_whoami_refuses_browser_sessions(self):

        # A logged-in browser session is not an
        # integration credential: the endpoint must
        # only answer to tokens.

        self.client.login(
            username="svc-intranet",
            password="testpass123",
        )

        response = self.client.get(
            reverse("api-whoami"),
        )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_whoami_updates_last_used(self):

        self.assertIsNone(self.token.last_used_at)

        self.client.get(
            reverse("api-whoami"),
            **self._auth_header(),
        )

        self.token.refresh_from_db()

        self.assertIsNotNone(
            self.token.last_used_at,
        )


class TokenChatApiTests(ApiTokenTestBase):

    def _post_chat(self, payload, key=None):

        return self.client.post(
            reverse("ai-chat"),
            data=payload,
            content_type="application/json",
            **self._auth_header(key),
        )

    def test_chat_works_with_token(self):

        # Retrieval and the AI provider are mocked so the
        # test exercises only the token path: auth, org
        # scoping, authorisation and persistence.

        with mock.patch(
            "ai.views.retrieve_knowledge",
            return_value=[],
        ), mock.patch(
            "ai.views.HostedProvider",
        ) as fake_provider:

            fake_provider.return_value.chat.return_value = (
                "Employees receive 25 days of annual leave."
            )

            response = self._post_chat(
                {
                    "message":
                        "How many annual leave days do we get?",
                    "assistant": "human-resources",
                },
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["answer"],
            "Employees receive 25 days of annual leave.",
        )

        conversation = Conversation.objects.get(
            id=data["conversation_id"],
        )

        # The token acts inside its own organisation and
        # on behalf of its own user.

        self.assertEqual(
            conversation.organisation,
            self.organisation,
        )

        self.assertEqual(
            conversation.user,
            self.integration_user,
        )

        self.assertEqual(
            conversation.messages.count(),
            2,
        )

    def test_chat_token_cannot_use_unauthorised_assistant(self):

        Assistant.objects.create(
            organisation=self.organisation,
            name="Finance",
            slug="finance",
            is_active=True,
        )

        response = self._post_chat(
            {
                "message": "What is the budget?",
                "assistant": "finance",
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_chat_cannot_continue_foreign_conversation(self):

        conversation = Conversation.objects.create(
            organisation=self.organisation,
            user=self.integration_user,
            assistant=self.assistant,
            title="Leave question",
        )

        Message.objects.create(
            conversation=conversation,
            role="user",
            content="How many leave days?",
        )

        other_token, other_raw_key = (
            self._issue_other_org_token()
        )

        response = self.client.post(
            reverse("ai-chat"),
            data={
                "message": "And sick leave?",
                "assistant": "human-resources",
                "conversation_id": conversation.id,
            },
            content_type="application/json",
            **{
                "HTTP_AUTHORIZATION":
                    "Token " + other_raw_key,
            },
        )

        # The other organisation's token must not even be
        # able to confirm this conversation exists.

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_chat_without_token_is_unauthorized(self):

        response = self.client.post(
            reverse("ai-chat"),
            data={"message": "Hello"},
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_chat_rate_limit_per_user(self):

        # Drive the counter to the limit; the next call
        # must be refused with 429.

        with mock.patch(
            "ai.views.retrieve_knowledge",
            return_value=[],
        ), mock.patch(
            "ai.views.HostedProvider",
        ) as fake_provider:

            fake_provider.return_value.chat.return_value = "ok"

            for _ in range(30):

                response = self._post_chat(
                    {
                        "message": "Hello",
                        "assistant": "human-resources",
                    },
                )

                self.assertEqual(
                    response.status_code,
                    200,
                )

            response = self._post_chat(
                {
                    "message": "Hello again",
                    "assistant": "human-resources",
                },
            )

        self.assertEqual(
            response.status_code,
            429,
        )


class TokenConversationEndpointTests(ApiTokenTestBase):

    def test_list_returns_token_scoped_conversations(self):

        conversation = Conversation.objects.create(
            organisation=self.organisation,
            user=self.integration_user,
            assistant=self.assistant,
            title="Leave question",
        )

        response = self.client.get(
            reverse("conversation-list"),
            **self._auth_header(),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        ids = [
            item["id"]
            for item in response.json()["conversations"]
        ]

        self.assertIn(
            conversation.id,
            ids,
        )

    def test_detail_works_with_token(self):

        conversation = Conversation.objects.create(
            organisation=self.organisation,
            user=self.integration_user,
            assistant=self.assistant,
            title="Leave question",
        )

        Message.objects.create(
            conversation=conversation,
            role="user",
            content="How many leave days?",
        )

        response = self.client.get(
            reverse(
                "conversation-detail",
                args=[conversation.id],
            ),
            **self._auth_header(),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json()["title"],
            "Leave question",
        )

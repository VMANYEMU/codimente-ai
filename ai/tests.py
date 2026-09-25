from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ai.models import Assistant, AssistantAccess, Conversation, Message
from core.models import Organisation, OrganisationMembership


class ConversationTestBase(TestCase):

    def setUp(self):

        self.organisation = Organisation.objects.create(
            name="Codimente Demo Organisation",
        )

        self.other_organisation = Organisation.objects.create(
            name="Other Organisation",
        )

        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
        )

        self.other_user = User.objects.create_user(
            username="intruder",
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

        self.other_membership = (
            OrganisationMembership.objects.create(
                organisation=self.other_organisation,
                user=self.other_user,
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

        self.other_organisation_assistant = (
            Assistant.objects.create(
                organisation=self.other_organisation,
                name="Other HR",
                slug="human-resources",
                is_active=True,
            )
        )

        AssistantAccess.objects.create(
            membership=self.membership,
            assistant=self.assistant,
        )

        AssistantAccess.objects.create(
            membership=self.other_membership,
            assistant=self.other_organisation_assistant,
        )

        self.conversation = Conversation.objects.create(
            organisation=self.organisation,
            user=self.user,
            assistant=self.assistant,
            title="How many annual leave days do employees receive?",
        )

        Message.objects.create(
            conversation=self.conversation,
            role="user",
            content="How many annual leave days do employees receive?",
        )

        Message.objects.create(
            conversation=self.conversation,
            role="assistant",
            content="Employees receive 25 working days annual leave.",
            sources=[
                {
                    "title": "HR Policy",
                    "page": 3,
                    "knowledge_base": "HR Knowledge",
                    "chunk_index": 2,
                    "similarity": 0.8123,
                }
            ],
        )


class ConversationAuthenticationTests(ConversationTestBase):

    def test_conversation_detail_requires_authentication(self):

        url = reverse(
            "conversation-detail",
            args=[self.conversation.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_conversation_list_requires_authentication(self):

        url = reverse("conversation-list")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_chat_api_requires_authentication(self):

        url = reverse("ai-chat")

        response = self.client.post(
            url,
            {
                "message": "Hello",
                "assistant": "human-resources",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            401,
        )


class ConversationSecurityTests(ConversationTestBase):

    def test_detail_returns_own_conversation(self):

        self.client.login(
            username="testuser",
            password="testpass123",
        )

        url = reverse(
            "conversation-detail",
            args=[self.conversation.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["conversation_id"],
            self.conversation.id,
        )

        self.assertEqual(
            len(data["messages"]),
            2,
        )

        # Sources must survive the round trip.

        assistant_message = data["messages"][1]

        self.assertEqual(
            assistant_message["sources"][0]["title"],
            "HR Policy",
        )

    def test_detail_hides_conversation_from_other_users(self):

        self.client.login(
            username="intruder",
            password="testpass123",
        )

        url = reverse(
            "conversation-detail",
            args=[self.conversation.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_detail_hides_conversation_without_assistant_access(self):

        # The intruder belongs to another organisation and
        # holds no AssistantAccess for this assistant. Even
        # with a guessed id, the security chain must hold:
        # user, organisation and assistant access.

        self.client.login(
            username="intruder",
            password="testpass123",
        )

        url = reverse(
            "conversation-detail",
            args=[self.conversation.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_chat_api_rejects_unauthorised_assistant(self):

        # testuser has no AssistantAccess for a Finance
        # assistant, so the backend must refuse the chat.

        finance_assistant = Assistant.objects.create(
            organisation=self.organisation,
            name="Finance",
            slug="finance",
            is_active=True,
        )

        self.client.login(
            username="testuser",
            password="testpass123",
        )

        url = reverse("ai-chat")

        response = self.client.post(
            url,
            {
                "message": "What is the budget?",
                "assistant": "finance",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_chat_api_rejects_invalid_conversation_id(self):

        self.client.login(
            username="testuser",
            password="testpass123",
        )

        url = reverse("ai-chat")

        response = self.client.post(
            url,
            {
                "message": "Hello",
                "assistant": "human-resources",
                "conversation_id": "not-a-number",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

    def test_chat_api_hides_other_users_conversations(self):

        self.client.login(
            username="intruder",
            password="testpass123",
        )

        url = reverse("ai-chat")

        response = self.client.post(
            url,
            {
                "message": "Hello",
                "assistant": "human-resources",
                "conversation_id": self.conversation.id,
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            404,
        )


class ConversationListTests(ConversationTestBase):

    def test_list_returns_own_conversations(self):

        self.client.login(
            username="testuser",
            password="testpass123",
        )

        url = reverse("conversation-list")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        ids = [
            conversation["id"]
            for conversation in data["conversations"]
        ]

        self.assertIn(
            self.conversation.id,
            ids,
        )

    def test_list_filters_by_assistant(self):

        self.client.login(
            username="testuser",
            password="testpass123",
        )

        url = reverse("conversation-list")

        response = self.client.get(
            url,
            {"assistant": "human-resources"},
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            len(data["conversations"]),
            1,
        )

    def test_list_refuses_unauthorised_assistant(self):

        Assistant.objects.create(
            organisation=self.organisation,
            name="Procurement",
            slug="procurement",
            is_active=True,
        )

        self.client.login(
            username="testuser",
            password="testpass123",
        )

        url = reverse("conversation-list")

        response = self.client.get(
            url,
            {"assistant": "procurement"},
        )

        self.assertEqual(
            response.status_code,
            403,
        )


class AssistantAccessValidationTests(ConversationTestBase):

    def test_assistant_access_cannot_cross_organisations(self):

        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            AssistantAccess.objects.create(
                membership=self.membership,
                assistant=self.other_organisation_assistant,
            )

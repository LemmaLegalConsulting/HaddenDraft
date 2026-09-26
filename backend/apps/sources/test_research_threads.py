"""Research chat threads follow the same rules as case chat threads."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai.chat_history import append_message, archive_current_conversation
from apps.ai.models import ChatConversation


class ResearchThreadTests(TestCase):
    url = "/api/research/"

    def setUp(self):
        self.user = get_user_model().objects.create_user("advocate", "a@example.com", "pw")
        self.client.force_login(self.user)
        self.chat = {"user": self.user, "kind": ChatConversation.RESEARCH}

    def test_opening_research_chat_creates_nothing(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["threadId"])
        self.assertFalse(ChatConversation.objects.exists())

    def test_an_unknown_thread_is_not_found(self):
        self.assertEqual(self.client.get(self.url, {"threadId": 999999}).status_code, 404)

    def test_an_archived_thread_opens_by_id_and_refuses_new_messages(self):
        append_message(**self.chat, role="user", content="Earlier question")
        old = ChatConversation.objects.get().id
        archive_current_conversation(**self.chat)
        opened = self.client.get(self.url, {"threadId": old}).json()
        self.assertEqual(opened["messages"][0]["content"], "Earlier question")
        refused = self.client.post(
            self.url, data={"query": "Follow-up", "threadId": old}, content_type="application/json"
        )
        self.assertEqual(refused.status_code, 409)
        self.assertEqual(self.client.delete(f"{self.url}?threadId={old}").status_code, 409)

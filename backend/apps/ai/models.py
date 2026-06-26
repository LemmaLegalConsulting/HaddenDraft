from django.conf import settings
from django.db import models


class PromptOverride(models.Model):
    """An optional database override for a file-backed prompt catalog entry."""

    key = models.CharField(max_length=120, unique=True)
    system = models.TextField()
    user = models.TextField()
    default_model = models.CharField(max_length=120, blank=True)
    default_reasoning_level = models.CharField(max_length=40, blank=True)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key


class ChatConversation(models.Model):
    RESEARCH = "research"
    CASE = "case"
    KIND_CHOICES = [(RESEARCH, "Research"), (CASE, "Case chat")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="chat_conversations", on_delete=models.CASCADE)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    # ``research`` uses a fixed user scope; case chat uses the selected Matter id.
    scope_key = models.CharField(max_length=100, default="default")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]


class ChatMessage(models.Model):
    conversation = models.ForeignKey(ChatConversation, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=20)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

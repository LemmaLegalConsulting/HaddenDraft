"""Small persistence boundary for per-user AI conversations."""

from django.db import transaction
from django.utils import timezone

from apps.ai.models import ChatConversation, ChatMessage


def conversation_for_user(*, user, kind, scope_key="default"):
    conversation = ChatConversation.objects.filter(user=user, kind=kind, scope_key=str(scope_key), archived_at__isnull=True).first()
    return conversation or ChatConversation.objects.create(user=user, kind=kind, scope_key=str(scope_key))


def messages_for_user(*, user, kind, scope_key="default", conversation_id=None):
    if conversation_id:
        conversation = ChatConversation.objects.filter(
            id=conversation_id, user=user, kind=kind, scope_key=str(scope_key)
        ).first()
        if not conversation:
            return []
    else:
        conversation = conversation_for_user(user=user, kind=kind, scope_key=scope_key)
    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            **message.metadata,
            "createdAt": message.created_at.isoformat(),
        }
        for message in conversation.messages.all()
    ]


@transaction.atomic
def append_message(*, user, kind, scope_key="default", role, content, metadata=None):
    conversation = conversation_for_user(user=user, kind=kind, scope_key=scope_key)
    message = ChatMessage.objects.create(
        conversation=conversation,
        role=role,
        content=content,
        metadata=metadata or {},
    )
    # Updating the parent lets future conversation-list features sort correctly.
    ChatConversation.objects.filter(pk=conversation.pk).update(updated_at=message.created_at)
    return message


def clear_messages(*, user, kind, scope_key="default"):
    conversation = conversation_for_user(user=user, kind=kind, scope_key=scope_key)
    conversation.messages.all().delete()


def archive_current_conversation(*, user, kind, scope_key="default"):
    conversation = conversation_for_user(user=user, kind=kind, scope_key=scope_key)
    conversation.archived_at = timezone.now()
    conversation.save(update_fields=["archived_at"])


def conversation_list(*, user, kind, scope_key="default"):
    conversations = ChatConversation.objects.filter(user=user, kind=kind, scope_key=str(scope_key)).prefetch_related("messages")
    return [{"id": item.id, "active": item.archived_at is None, "updatedAt": item.updated_at.isoformat(), "preview": (item.messages.first().content[:90] if item.messages.first() else "New chat")} for item in conversations]

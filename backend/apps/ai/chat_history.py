"""Small persistence boundary for per-user AI conversations."""

from django.db import transaction

from apps.ai.models import ChatConversation, ChatMessage


def conversation_for_user(*, user, kind, scope_key="default"):
    return ChatConversation.objects.get_or_create(user=user, kind=kind, scope_key=str(scope_key))[0]


def messages_for_user(*, user, kind, scope_key="default"):
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

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


def current_conversation(*, user, kind, scope_key="default"):
    """The conversation new messages go to, or None -- never creates one."""
    return ChatConversation.objects.filter(
        user=user, kind=kind, scope_key=str(scope_key), archived_at__isnull=True
    ).first()


def _message_dicts(conversation):
    if conversation is None:
        return []
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


def read_conversation(*, user, kind, scope_key="default", conversation_id=None):
    """Read a conversation without creating one.

    With an id, exactly that conversation of this user and scope, or
    LookupError: an explicit thread that does not resolve must never be
    answered with some other conversation, or with an empty one that looks
    like it. Without an id, the current conversation, which may not exist yet.
    Returns (conversation_or_None, messages).
    """
    if conversation_id:
        conversation = ChatConversation.objects.filter(
            id=conversation_id, user=user, kind=kind, scope_key=str(scope_key)
        ).first()
        if conversation is None:
            raise LookupError("No such conversation.")
    else:
        conversation = current_conversation(user=user, kind=kind, scope_key=scope_key)
    return conversation, _message_dicts(conversation)


def is_current_thread(*, user, kind, scope_key="default", thread_id=None):
    """Whether a write that names a thread names the one writes go to.

    No thread named means "the current one", as before. A named thread that
    has since been archived -- another window started a new chat -- is not
    current, and a message meant for it must not land in a different one.
    """
    if not thread_id:
        return True
    current = current_conversation(user=user, kind=kind, scope_key=scope_key)
    return current is not None and str(current.id) == str(thread_id)


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

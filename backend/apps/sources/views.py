from django.http import JsonResponse

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.chat_history import append_message, archive_current_conversation, clear_messages, conversation_list, messages_for_user
from apps.ai.models import ChatConversation
from apps.ai.prompt_catalog import render_prompt
from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.core.views import default_jurisdiction_for_user
from apps.matters.services import matter_for_user
from apps.sources.document_text import DocumentExtractionError, extract_text
from apps.sources.models import RetrievedDocument, UserResource
from apps.sources.registry import connector_registry
from apps.sources.selection import automatic_source_selection, source_decision_with_counts, source_kinds


def _truthy(value):
    return str(value).lower() in {"1", "true", "yes", "on"}


def _research_answer(*, query, matter, results, messages, jurisdiction):
    if not results:
        return "No matching source results were found."

    source_lines = []
    for index, result in enumerate(results[:12], start=1):
        citation = f" Citation: {result.citation}." if result.citation else ""
        source_lines.append(
            f"[{index}] {result.title} [{result.source_label}].{citation}\n"
            f"Excerpt: {result.snippet}"
        )

    chat_lines = []
    for message in messages[-6:]:
        role = "Assistant" if message.get("role") == "assistant" else "User"
        content = str(message.get("content") or "").strip()
        if content:
            chat_lines.append(f"{role}: {content}")

    prompt = render_prompt(
        "research.answer",
        query=query,
        matter_summary=getattr(matter, "summary", "") if matter else "",
        jurisdiction=jurisdiction,
        conversation="\n".join(chat_lines) or "- None",
        sources="\n".join(source_lines),
    )
    client = OpenAICompatibleClient()
    return client.complete(
        system=prompt.system,
        user=prompt.user,
        temperature=0.1,
        model=prompt.default_model,
        reasoning_level=prompt.default_reasoning_level,
    )


@api_login_required
def sources(_request):
    return JsonResponse({"sources": [connector.metadata() for connector in connector_registry.all()]})


@api_login_required
def research(request):
    if request.method == "GET":
        thread_id = request.GET.get("threadId")
        return JsonResponse({"messages": messages_for_user(user=request.user, kind=ChatConversation.RESEARCH, conversation_id=thread_id), "threads": conversation_list(user=request.user, kind=ChatConversation.RESEARCH)})
    if request.method == "DELETE":
        clear_messages(user=request.user, kind=ChatConversation.RESEARCH)
        return JsonResponse({"ok": True})
    if request.method != "POST":
        return method_not_allowed(["GET", "POST", "DELETE"])

    body = json_body(request)
    if body.get("action") == "new_thread":
        archive_current_conversation(user=request.user, kind=ChatConversation.RESEARCH)
        return JsonResponse({"messages": [], "threads": conversation_list(user=request.user, kind=ChatConversation.RESEARCH)})
    query = body.get("query", "")
    matter = None
    if body.get("matterId"):
        matter = matter_for_user(request.user, body["matterId"])
        if not matter:
            return JsonResponse({"error": "Case not found or not available to this user"}, status=404)

    jurisdiction = (
        getattr(matter, "jurisdiction", "").strip()
        or str(body.get("jurisdiction") or "").strip()
        or default_jurisdiction_for_user(request.user)
    )

    history = messages_for_user(user=request.user, kind=ChatConversation.RESEARCH)
    current_message = {"role": "user", "content": query}
    conversation = [*history, current_message]
    source_ids = body.get("sourceIds") or []
    auto_mode = body.get("sourceMode") == "auto"
    auto_selection = None
    if auto_mode:
        auto_selection = automatic_source_selection(query, matter=matter)
        source_ids = auto_selection["source_ids"]
    kinds = body.get("sourceKinds") or source_kinds(source_ids)
    results = connector_registry.search(
        query,
        kinds=kinds,
        source_ids=source_ids,
        matter=matter,
        jurisdiction=jurisdiction,
        limit_per_source=body.get("limitPerSource", 5),
        user=request.user,
        request=request,
    )
    for result in results:
        RetrievedDocument.objects.create(
            source_kind=result.source_kind,
            source_label=result.source_label,
            external_id=result.id,
            title=result.title,
            snippet=result.snippet,
            url=result.url,
            citation=result.citation,
            metadata=result.metadata,
        )
    payload = {"results": [result.to_dict() for result in results], "usedAi": False, "selectedSourceIds": source_ids}
    if auto_selection:
        payload["sourceDecision"] = source_decision_with_counts(auto_selection, results)
    if _truthy(body.get("useAi")):
        try:
            payload["answer"] = _research_answer(
                query=query,
                matter=matter,
                results=results,
                messages=conversation,
                jurisdiction=jurisdiction,
            )
            payload["usedAi"] = True
            append_message(user=request.user, kind=ChatConversation.RESEARCH, role="user", content=query)
            append_message(
                user=request.user,
                kind=ChatConversation.RESEARCH,
                role="assistant",
                content=payload["answer"],
                metadata={"citations": payload["results"]},
            )
        except OpenAIBackendError as exc:
            return JsonResponse({"error": f"AI research failed: {exc}"}, status=502)
    return JsonResponse(payload)


def user_resource_to_dict(resource):
    return {
        "id": resource.id,
        "title": resource.title,
        "resourceType": resource.resource_type,
        "originalFilename": resource.original_filename,
        "snippet": " ".join(resource.text.split())[:240],
        "createdAt": resource.created_at.isoformat(),
        "updatedAt": resource.updated_at.isoformat(),
    }


@api_login_required
def user_resources(request):
    if request.method == "GET":
        resources = UserResource.objects.filter(user=request.user)
        return JsonResponse({"resources": [user_resource_to_dict(resource) for resource in resources]})
    if request.method != "POST":
        return method_not_allowed(["GET", "POST"])

    title = ""
    resource_type = "other"
    original_filename = ""
    extractor = ""
    text = ""
    try:
        if request.content_type and request.content_type.startswith("multipart/"):
            upload = request.FILES.get("file")
            if not upload:
                return JsonResponse({"error": "Upload a reference document"}, status=400)
            extracted = extract_text(upload.read(), filename=upload.name, content_type=upload.content_type or "")
            title = request.POST.get("title") or upload.name
            resource_type = request.POST.get("resourceType") or request.POST.get("resource_type") or "other"
            original_filename = upload.name
            extractor = extracted["extractor"]
            text = extracted["text"]
        else:
            body = json_body(request)
            title = body.get("title") or "Private reference"
            resource_type = body.get("resourceType") or body.get("resource_type") or "other"
            text = body.get("text") or ""
    except DocumentExtractionError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if resource_type not in dict(UserResource.RESOURCE_TYPE_CHOICES):
        resource_type = "other"
    if not text.strip():
        return JsonResponse({"error": "Reference text could not be extracted"}, status=400)

    resource = UserResource.objects.create(
        user=request.user,
        title=title.strip() or original_filename or "Private reference",
        resource_type=resource_type,
        original_filename=original_filename,
        text=text,
        extractor=extractor,
    )
    return JsonResponse({"resource": user_resource_to_dict(resource)}, status=201)

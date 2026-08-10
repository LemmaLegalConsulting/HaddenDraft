from django.http import JsonResponse
from django.http import FileResponse

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.chat_history import append_message, archive_current_conversation, clear_messages, conversation_list, messages_for_user
from apps.ai.models import ChatConversation
from apps.ai.prompt_catalog import render_prompt
from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.core.content_library import content_paths
from apps.core.views import default_jurisdiction_for_user
from apps.matters.services import matter_for_user
from apps.sources.document_text import DocumentExtractionError, extract_text
from apps.sources.library import (
    document_chunks,
    document_summary,
    filter_chunks,
    find_document,
    library_documents,
    manifest_paths,
    section_tree,
)
from apps.sources.models import RetrievedDocument, UserResource
from apps.sources.augmentation import augmented_search
from apps.sources.registry import connector_registry
from apps.sources.selection import automatic_source_selection, source_decision_with_counts, source_kinds

import yaml


def _truthy(value):
    return str(value).lower() in {"1", "true", "yes", "on"}


def _source_text(path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    marker = "## Source text"
    return text.split(marker, 1)[-1].strip() if marker in text else text.strip()


def _content_chunk(document_slug, chunk_id):
    for manifest_path in manifest_paths():
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if manifest.get("document_slug") != document_slug:
            continue
        for item in manifest.get("chunks", []):
            item_id = str(item.get("id"))
            requested_id = str(chunk_id)
            if item_id != requested_id and item_id != requested_id.lstrip("0"):
                continue
            chunk_path = manifest_path.parent / item["file"]
            if not chunk_path.is_file():
                continue
            return manifest_path, manifest, item, chunk_path
    return None


def _content_file(source_path):
    if not source_path:
        return None
    relative = [part for part in str(source_path).split("/") if part and part != "."]
    # source_path comes from generated manifests rather than the request, but a
    # traversal component would still resolve outside the content library.
    if any(part == ".." for part in relative) or not relative:
        return None
    for path in content_paths(*relative):
        if path.is_file():
            return path
    return None


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
def library(request):
    """Every document on the shelf, so a reader can browse without a query."""
    if request.method != "GET":
        return method_not_allowed(["GET"])
    return JsonResponse({"documents": library_documents()})


@api_login_required
def library_document(request, document_slug):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    manifest_path, manifest = find_document(document_slug)
    if not manifest:
        return JsonResponse({"error": "Document not found"}, status=404)
    query = (request.GET.get("q") or "").strip()
    chunks = document_chunks(manifest_path, manifest)
    matched = filter_chunks(chunks, query)
    return JsonResponse({
        "document": {
            **document_summary(manifest_path, manifest),
            "hasPdf": bool(_content_file(manifest.get("source_path", ""))),
            "readableCount": len(chunks),
        },
        "query": query,
        "matchCount": len(matched),
        "tree": section_tree(matched, document_title=manifest.get("document_title", "")),
    })


@api_login_required
def content_source(request, document_slug, chunk_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    resolved = _content_chunk(document_slug, chunk_id)
    if not resolved:
        return JsonResponse({"error": "Content source not found"}, status=404)
    _manifest_path, manifest, item, chunk_path = resolved
    source_path = item.get("source_path") or manifest.get("source_path", "")
    return JsonResponse({
        "source": {
            "chunkId": item.get("id"),
            "documentSlug": manifest.get("document_slug", ""),
            "documentTitle": manifest.get("document_title", "Source"),
            "documentVersion": manifest.get("document_version", ""),
            "heading": item.get("heading", ""),
            "sectionPath": item.get("path", []),
            "contentKind": item.get("content_kind", ""),
            "pdfPages": item.get("pages", []),
            "sourcePath": source_path,
            "hasPdf": bool(_content_file(source_path)),
            "sourceSha256": item.get("source_sha256") or manifest.get("source_sha256", ""),
            "citation": item.get("citation", ""),
            "url": item.get("url", ""),
            "effectiveDate": item.get("effective_date", ""),
            "jurisdiction": manifest.get("jurisdiction", ""),
            "sourceText": _source_text(chunk_path),
        }
    })


@api_login_required
def content_source_pdf(request, document_slug, chunk_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    resolved = _content_chunk(document_slug, chunk_id)
    if not resolved:
        return JsonResponse({"error": "Content source not found"}, status=404)
    _manifest_path, manifest, item, _chunk_path = resolved
    pdf_path = _content_file(item.get("source_path") or manifest.get("source_path", ""))
    if not pdf_path:
        return JsonResponse({"error": "No PDF source is available for this content chunk."}, status=404)
    response = FileResponse(pdf_path.open("rb"), content_type="application/pdf", filename=pdf_path.name, as_attachment=False)
    response["Content-Disposition"] = f'inline; filename="{pdf_path.name}"'
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response


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
    use_augmentation = _truthy(body.get("useAi")) or auto_mode or _truthy(body.get("augmentSearch"))
    if use_augmentation:
        search_payload = augmented_search(
            query,
            connector_registry=connector_registry,
            kinds=kinds,
            source_ids=source_ids,
            matter=matter,
            jurisdiction=jurisdiction,
            limit_per_source=body.get("limitPerSource", 5),
            user=request.user,
            request=request,
            max_rounds=body.get("maxSearchRounds") or 2,
            # Explicit modes ("Cases only" / manual pick) must never widen the
            # search to sources the user excluded; only Auto may add sources.
            allow_source_expansion=auto_mode,
        )
        results = search_payload["results"]
        source_ids = search_payload["selected_source_ids"]
        augmentation = search_payload["augmentation"]
    else:
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
        augmentation = {"enabled": False, "rounds": [], "expanded": False}
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
    payload = {
        "results": [result.to_dict() for result in results],
        "usedAi": False,
        "selectedSourceIds": source_ids,
        "searchAugmentation": augmentation,
    }
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

import json
import re

from django.conf import settings
from django.http import JsonResponse

from apps.ai.case_chat import case_chat_reply
from apps.core.http import api_login_required
from apps.core.http import json_body
from apps.matters.document_context import (
    chunk_text,
    document_to_public_dict,
    get_case_document,
    get_case_documents,
    get_document_text,
    search_chunks,
    summarize_text,
)
from apps.matters.models import MatterFact
from apps.matters.seed import seed_matters
from apps.matters.serializers import fact_to_dict, matter_to_dict
from apps.matters.services import (
    legalserver_account_status,
    matter_for_user,
    sync_legalserver_matter,
    sync_legalserver_matters_for_user,
)
from apps.sources.document_text import DocumentExtractionError, extract_text
from apps.sources.models import UserSourceIdentity


def _matter_or_404(user, matter_id):
    matter = matter_for_user(user, matter_id)
    if matter:
        return matter, None
    return None, JsonResponse({"error": "Case not found or not available to this user"}, status=404)


@api_login_required
def cases(request):
    query = request.GET.get("q", "").strip()
    sync = sync_legalserver_matters_for_user(request.user, query=query, restrict_to_user=True)
    if settings.ENABLE_DEMO_MATTERS and not sync.matters:
        seed_matters()
    matters = sync.matters if not settings.ENABLE_DEMO_MATTERS else matter_for_demo_list()
    account = legalserver_account_status(request.user)
    return JsonResponse(
        {
            "cases": [matter_to_dict(matter) for matter in matters],
            "legalserver": {
                **account,
                "syncError": sync.error,
            },
        }
    )


def matter_for_demo_list():
    from apps.matters.models import Matter

    return Matter.objects.all()


@api_login_required
def legalserver_account(request):
    if request.method == "GET":
        return JsonResponse({"legalserver": legalserver_account_status(request.user)})
    if request.method not in ("POST", "PATCH", "DELETE"):
        return JsonResponse({"error": "GET, POST, PATCH, or DELETE required"}, status=405)

    if request.method == "DELETE":
        UserSourceIdentity.objects.filter(user=request.user, provider="legalserver").update(enabled=False)
        return JsonResponse({"legalserver": legalserver_account_status(request.user)})

    body = json.loads(request.body.decode("utf-8") or "{}")
    identifier = (body.get("identifier") or "").strip()
    if not identifier:
        return JsonResponse({"error": "LegalServer identifier is required"}, status=400)
    UserSourceIdentity.objects.update_or_create(
        user=request.user,
        provider="legalserver",
        defaults={"identifier": identifier, "enabled": True},
    )
    return JsonResponse({"legalserver": legalserver_account_status(request.user)})


@api_login_required
def case_detail(request, matter_id):
    matter = matter_for_user(request.user, matter_id)
    if not matter:
        sync_legalserver_matter(matter_id, user=request.user)
        matter = matter_for_user(request.user, matter_id)
    if not matter and settings.ENABLE_DEMO_MATTERS:
        seed_matters()
        matter = matter_for_user(request.user, matter_id)
    if not matter:
        return JsonResponse({"error": "Case not found or not available to this user"}, status=404)
    matter = matter.__class__.objects.prefetch_related("facts").get(id=matter.id)
    return JsonResponse({"case": matter_to_dict(matter, include_facts=True)})


@api_login_required
def case_documents(request, matter_id):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)
    matter, error = _matter_or_404(request.user, matter_id)
    if error:
        return error
    documents = [document_to_public_dict(document) for document in get_case_documents(matter)]
    return JsonResponse({"documents": documents})


@api_login_required
def case_document_context(request, matter_id, document_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    matter, error = _matter_or_404(request.user, matter_id)
    if error:
        return error
    document = get_case_document(matter, document_id)
    if not document:
        return JsonResponse({"error": "Document not found"}, status=404)

    body = json_body(request)
    level = body.get("level", "summary")
    text = get_document_text(document)
    chunks = chunk_text(text)
    payload = {"document": document_to_public_dict(document)}
    if level == "full":
        payload["text"] = text
        payload["summary"] = summarize_text(text)
        payload["chunks"] = chunks
    elif level == "chunks":
        payload["summary"] = summarize_text(text)
        payload["chunks"] = chunks
    elif level == "search":
        payload["summary"] = summarize_text(text)
        payload["chunks"] = search_chunks(chunks, body.get("query", ""), limit=body.get("limit", 5))
    else:
        payload["summary"] = summarize_text(text)
    return JsonResponse(payload)


def _fact_slug(matter, title):
    base = re.sub(r"[^a-z0-9]+", "-", (title or "added fact").lower()).strip("-") or "added-fact"
    slug = base
    index = 2
    while MatterFact.objects.filter(matter=matter, slug=slug).exists():
        slug = f"{base}-{index}"
        index += 1
    return slug


def _fact_title(text, fallback):
    first_line = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    if not first_line:
        return fallback
    return first_line[:80]


def _create_case_fact(matter, *, title, text, source_label):
    text = (text or "").strip()
    if not text:
        return None
    title = (title or "").strip() or _fact_title(text, "Added fact")
    return MatterFact.objects.create(
        matter=matter,
        slug=_fact_slug(matter, title),
        title=title,
        text=text,
        source_label=source_label or "Added during drafting",
        confidence="user_added",
        selected_by_default=False,
    )


@api_login_required
def case_facts(request, matter_id):
    matter, error = _matter_or_404(request.user, matter_id)
    if error:
        return error

    if request.method == "GET":
        return JsonResponse({"facts": [fact_to_dict(fact) for fact in matter.facts.all()]})

    if request.method != "POST":
        return JsonResponse({"error": "GET or POST required"}, status=405)

    created = []
    if request.content_type and request.content_type.startswith("multipart/"):
        upload = request.FILES.get("file")
        if not upload:
            return JsonResponse({"error": "Upload a document file"}, status=400)
        try:
            extracted = extract_text(upload.read(), filename=upload.name, content_type=upload.content_type or "")
        except DocumentExtractionError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        fact = _create_case_fact(
            matter,
            title=request.POST.get("title") or upload.name,
            text=extracted["text"],
            source_label=f"Uploaded document: {upload.name}",
        )
        if fact:
            created.append(fact)
    else:
        body = json_body(request)
        fact = _create_case_fact(
            matter,
            title=body.get("title") or "",
            text=body.get("text") or "",
            source_label=body.get("source") or "Typed during drafting",
        )
        if fact:
            created.append(fact)

    if not created:
        return JsonResponse({"error": "Fact text is required"}, status=400)

    matter = matter.__class__.objects.prefetch_related("facts").get(id=matter.id)
    return JsonResponse(
        {
            "facts": [fact_to_dict(fact) for fact in matter.facts.all()],
            "created": [fact_to_dict(fact) for fact in created],
            "case": matter_to_dict(matter, include_facts=True),
        },
        status=201,
    )


@api_login_required
def case_fact_recommendations(request, matter_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    matter, error = _matter_or_404(request.user, matter_id)
    if error:
        return error
    matter = matter.__class__.objects.prefetch_related("facts").get(id=matter.id)

    from apps.ai.services import drafting_ai

    recommended_slugs = set(drafting_ai.recommend_fact_slugs(matter))
    recommended = [
        fact
        for fact in matter.facts.all()
        if fact.slug in recommended_slugs or fact.selected_by_default
    ]
    return JsonResponse(
        {
            "factIds": [fact.id for fact in recommended],
            "facts": [fact_to_dict(fact) for fact in recommended],
        }
    )


@api_login_required
def case_chat(request, matter_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    matter = matter_for_user(request.user, matter_id)
    if not matter:
        sync_legalserver_matter(matter_id, user=request.user)
        matter = matter_for_user(request.user, matter_id)
    if not matter:
        return JsonResponse({"error": "Case not found or not available to this user"}, status=404)
    body = json.loads(request.body.decode("utf-8") or "{}")
    reply = case_chat_reply(matter=matter, messages=body.get("messages") or [])
    return JsonResponse(reply)

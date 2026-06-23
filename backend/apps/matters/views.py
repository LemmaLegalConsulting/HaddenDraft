import json

from django.conf import settings
from django.http import JsonResponse

from apps.ai.case_chat import case_chat_reply
from apps.core.http import api_login_required
from apps.matters.models import Matter
from apps.matters.seed import seed_matters
from apps.matters.serializers import matter_to_dict
from apps.matters.services import (
    legalserver_account_status,
    sync_legalserver_matter,
    sync_legalserver_matters_for_user,
)
from apps.sources.models import UserSourceIdentity


@api_login_required
def cases(request):
    query = request.GET.get("q", "").strip()
    sync = sync_legalserver_matters_for_user(request.user, query=query, restrict_to_user=not bool(query))
    if settings.ENABLE_DEMO_MATTERS and not sync.matters:
        seed_matters()
    matters = sync.matters if not settings.ENABLE_DEMO_MATTERS else Matter.objects.all()
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
def case_detail(_request, matter_id):
    if not Matter.objects.filter(external_id=matter_id).exists():
        sync_legalserver_matter(matter_id)
    if not Matter.objects.filter(external_id=matter_id).exists():
        if settings.ENABLE_DEMO_MATTERS:
            seed_matters()
    if not Matter.objects.filter(external_id=matter_id).exists():
        return JsonResponse({"error": "Case not found or LegalServer account not connected"}, status=404)
    matter = Matter.objects.prefetch_related("facts").get(external_id=matter_id)
    return JsonResponse({"case": matter_to_dict(matter, include_facts=True)})


@api_login_required
def case_chat(request, matter_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    if not Matter.objects.filter(external_id=matter_id).exists():
        sync_legalserver_matter(matter_id)
    matter = Matter.objects.filter(external_id=matter_id).first()
    if not matter:
        return JsonResponse({"error": "Case not found"}, status=404)
    body = json.loads(request.body.decode("utf-8") or "{}")
    reply = case_chat_reply(matter=matter, messages=body.get("messages") or [])
    return JsonResponse(reply)

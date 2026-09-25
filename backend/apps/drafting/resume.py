"""Reopening saved drafting work from a URL.

A link to `/drafting/26-0222/sessions/184` has to land on the furthest point
the session actually reached -- and only by reading. Nothing here generates,
approves, validates, or saves; the advisory `resume` block is derived from what
the session has persisted (its drafts, its plan, a generation still running),
not from `status`, whose vocabulary predates the current workflow screens.

A route names a chain -- case, session, draft -- and every link of it is checked
here. A session that exists but belongs to another case answers exactly as a
session that does not exist, so a URL never reveals which case a session is on.
"""

from django.db.models import Count

from apps.drafting.models import DraftGenerationJob, DraftingSession
from apps.drafting.services import normalize_status
from apps.matters.route_aliases import resolve_matter_route_key, route_key_for_matter
from apps.matters.serializers import matter_case_number

# Session modes each workspace opens. An advice letter or a template fill has
# its own screen; opening one in the drafting editor edits it the wrong way.
WORKSPACE_MODES = {
    "drafting": {"draft_from_template", "draft_from_scratch"},
    "advice-letters": {"advice_letter"},
}

MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20


def _plan_has_content(plan):
    return bool(plan) and bool(plan.get("documents") or plan.get("missingInformation") or plan.get("summary"))


def resume_payload(session):
    """Where a reopened session should land, from what it has saved."""
    drafts = list(session.drafts.order_by("created_at").values("id", "updated_at"))
    running = (
        session.generation_jobs.filter(status__in=[DraftGenerationJob.PENDING, DraftGenerationJob.RUNNING])
        .order_by("-created_at", "-id")
        .first()
    )
    latest_job = session.generation_jobs.order_by("-created_at", "-id").first()
    last_draft = max(drafts, key=lambda item: item["updated_at"], default=None)
    if running:
        view = "job"
    elif drafts:
        view = "draft"
    elif _plan_has_content(session.draft_plan or {}):
        view = "plan"
    else:
        view = "goal"
    return {
        "recommendedView": view,
        "activeJobId": running.id if running else None,
        "latestJob": {"id": latest_job.id, "status": latest_job.status, "error": latest_job.error} if latest_job else None,
        "draftIds": [item["id"] for item in drafts],
        "lastDraftId": last_draft["id"] if last_draft else None,
        "hasPlan": _plan_has_content(session.draft_plan or {}),
    }


def session_in_route(user, session, *, case_key="", workspace=""):
    """Whether the session is the one a URL's parent chain names.

    Access to the session's case is checked by the caller; this checks that
    the URL's case key names that same case and that the session belongs in
    the workspace the URL opened.
    """
    if workspace:
        modes = WORKSPACE_MODES.get(workspace)
        if modes is None or session.mode not in modes:
            return False
    if case_key:
        matter = resolve_matter_route_key(user, case_key)
        if not matter or matter.pk != session.matter_id:
            return False
    return True


def session_summary(session):
    template = session.template
    draft_count = getattr(session, "draft_count", None)
    if draft_count is None:
        draft_count = session.drafts.count()
    plan_documents = (session.draft_plan or {}).get("documents") or []
    return {
        "id": session.id,
        "mode": session.mode,
        "status": normalize_status(session.status),
        "matterId": session.matter.external_id,
        "caseNumber": matter_case_number(session.matter),
        "routeCaseKey": route_key_for_matter(session.matter),
        "goal": session.goal,
        "templateTitle": template.title if template else "",
        "plannedDocuments": [item.get("title", "") for item in plan_documents if isinstance(item, dict)],
        "draftCount": draft_count,
        "createdAt": session.created_at.isoformat(),
        "updatedAt": session.updated_at.isoformat(),
    }


def page_bounds(raw_limit, raw_offset):
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = DEFAULT_PAGE_SIZE
    try:
        offset = int(raw_offset)
    except (TypeError, ValueError):
        offset = 0
    return max(1, min(limit, MAX_PAGE_SIZE)), max(0, offset)


def sessions_for_matter(matter, *, modes, limit, offset):
    queryset = (
        DraftingSession.objects.select_related("matter", "template")
        .filter(matter=matter, mode__in=modes)
        .annotate(draft_count=Count("drafts"))
        .order_by("-updated_at", "-id")
    )
    total = queryset.count()
    page = list(queryset[offset : offset + limit])
    return page, total

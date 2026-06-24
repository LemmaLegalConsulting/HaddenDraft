from django.utils import timezone

from apps.facts.models import ExtractedFact


REVIEWED_STATUSES = ["approved", "corrected"]
UNREVIEWED_STATUSES = ["unreviewed", "needs_review"]


def set_path(data: dict, path: str, value):
    current = data
    parts = path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def build_fact_snapshot(case_id: str, include_unreviewed: bool = True) -> dict:
    facts = {}
    qs = ExtractedFact.objects.filter(case_id=case_id).exclude(review_status="rejected").order_by("id")

    if not include_unreviewed:
        qs = qs.filter(review_status__in=REVIEWED_STATUSES)

    for fact in qs:
        set_path(facts, fact.field_path, fact.value)

    return facts


def get_fact_status_map(case_id: str) -> dict:
    facts = (
        ExtractedFact.objects.filter(case_id=case_id)
        .exclude(review_status="rejected")
        .order_by("id")
    )
    return {fact.field_path: fact.review_status for fact in facts}


def approve_fact(fact_id, user, corrected_value=None):
    fact = ExtractedFact.objects.get(id=fact_id)
    if corrected_value is not None:
        fact.value = corrected_value
        fact.review_status = "corrected"
    else:
        fact.review_status = "approved"
    fact.reviewed_by = user
    fact.reviewed_at = timezone.now()
    fact.save(update_fields=["value", "review_status", "reviewed_by", "reviewed_at"])
    return fact


def reject_fact(fact_id, user):
    fact = ExtractedFact.objects.get(id=fact_id)
    fact.review_status = "rejected"
    fact.reviewed_by = user
    fact.reviewed_at = timezone.now()
    fact.save(update_fields=["review_status", "reviewed_by", "reviewed_at"])
    return fact

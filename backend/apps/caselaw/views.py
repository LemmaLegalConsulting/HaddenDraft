import re
from collections import Counter

from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404

from apps.caselaw.catalog import ROW_FIELDS, browse_catalog, read_filters
from apps.caselaw.models import CaseLawDecision, CaseLawSimilarityEdge
from apps.caselaw.storage import get_caselaw_storage
from apps.core.http import api_login_required, method_not_allowed


def _date(value):
    return value.isoformat() if value else None


def decision_summary(decision):
    return {
        "id": decision.id,
        "title": decision.title,
        "shortTitle": decision.short_title,
        "docketNumber": decision.docket_number,
        "caseNumber": decision.case_number,
        "court": decision.court,
        "county": decision.county,
        "jurisdiction": decision.jurisdiction,
        "judge": decision.judge,
        "decisionDate": _date(decision.decision_date),
        "entryDate": _date(decision.entry_date),
        "publicationStatus": decision.publication_status,
        "precedentialStatus": decision.precedential_status,
        "authorityLevel": decision.authority_level,
        "treatmentStatus": decision.treatment_status,
        "metadataVerified": decision.metadata_verified,
        "approvedForSearch": decision.approved_for_search,
        "approvedForDrafting": decision.approved_for_drafting,
        "citation": decision.citation_string,
        "sourceSha256": decision.source_sha256,
    }


def decision_source_result(decision, *, document_type="overview", score=0):
    citation = decision.citation_string
    if not citation:
        parts = [decision.short_title or decision.title]
        if decision.docket_number:
            parts.append(f"No. {decision.docket_number}")
        if decision.court:
            parts.append(decision.court)
        if decision.decision_date:
            parts.append(decision.decision_date.isoformat())
        citation = ", ".join(parts)
    snippet = " ".join(part for part in [decision.key_facts, decision.outcome, decision.posture] if part).strip()
    return {
        "id": f"local-case:{decision.id}:browse",
        "title": decision.title,
        "snippet": snippet[:520],
        "sourceKind": "local_cases",
        "sourceLabel": "Local case law",
        "citation": citation,
        "url": f"/api/caselaw/decisions/{decision.id}/",
        "metadata": {
            "decisionId": decision.id,
            "court": decision.court,
            "county": decision.county,
            "judge": decision.judge,
            "decisionDate": _date(decision.decision_date),
            "entryDate": _date(decision.entry_date),
            "publicationStatus": decision.publication_status,
            "precedentialStatus": decision.precedential_status,
            "authorityLevel": decision.authority_level,
            "treatmentStatus": decision.treatment_status,
            "metadataVerified": decision.metadata_verified,
            "approvedForDrafting": decision.approved_for_drafting,
            "documentType": document_type,
            "sourceSha256": decision.source_sha256,
            "rankScore": score,
            "warning": "Treatment/currentness has not been checked." if decision.treatment_status == "unchecked" else "",
        },
    }


def _terms(value):
    return [term for term in re.findall(r"[a-z0-9]+", (value or "").casefold()) if len(term) > 2]


def _list(value):
    return value if isinstance(value, list) else []


def _facet_items(counter, facet):
    return [
        {"facet": facet, "value": value, "count": count}
        for value, count in counter.most_common(12)
        if value
    ]


def _decision_text(decision):
    return " ".join([
        decision.title,
        decision.short_title,
        decision.docket_number,
        decision.court,
        decision.county,
        decision.judge,
        decision.key_facts,
        decision.outcome,
        " ".join(_list(decision.issues)),
        " ".join(_list(decision.holdings)),
        " ".join(_list(decision.rules_applied)),
        " ".join(_list(decision.statutes_cited)),
        " ".join(_list(decision.regulations_cited)),
        " ".join(_list(decision.cases_cited)),
    ]).casefold()


def _score_related(candidate, seed, query_terms):
    score = 0
    reasons = []
    text = _decision_text(candidate)
    hits = sum(term in text for term in query_terms)
    if hits:
        score += hits * 8
        reasons.append("query match")
    if seed:
        shared_statutes = set(_list(candidate.statutes_cited)) & set(_list(seed.statutes_cited))
        shared_regs = set(_list(candidate.regulations_cited)) & set(_list(seed.regulations_cited))
        shared_cases = set(_list(candidate.cases_cited)) & set(_list(seed.cases_cited))
        if shared_statutes:
            score += 45 + len(shared_statutes) * 5
            reasons.append("shared statute")
        if shared_regs:
            score += 35 + len(shared_regs) * 5
            reasons.append("shared regulation")
        if shared_cases:
            score += 40 + len(shared_cases) * 5
            reasons.append("shared cited case")
        seed_terms = set(_terms(" ".join(_list(seed.issues) + _list(seed.holdings)) + " " + seed.key_facts))
        overlap = seed_terms & set(_terms(" ".join(_list(candidate.issues) + _list(candidate.holdings)) + " " + candidate.key_facts))
        if overlap:
            score += min(len(overlap), 8) * 4
            reasons.append("similar issues")
        if candidate.county and candidate.county == seed.county:
            score += 8
            reasons.append("same county")
        if candidate.court and candidate.court == seed.court:
            score += 6
            reasons.append("same court")
    if candidate.treatment_status == "unchecked":
        score -= 2
    if candidate.negative_treatment_type or candidate.vacated_date or candidate.reversed_date or candidate.overruled_by:
        score -= 35
        reasons.append("negative treatment")
    return score, list(dict.fromkeys(reasons))


def decision_detail_payload(decision):
    return {
        **decision_summary(decision),
        "parties": decision.parties,
        "partyRoles": decision.party_roles,
        "issues": decision.issues,
        "holdings": decision.holdings,
        "rulesApplied": decision.rules_applied,
        "statutesCited": decision.statutes_cited,
        "regulationsCited": decision.regulations_cited,
        "casesCited": decision.cases_cited,
        "keyFacts": decision.key_facts,
        "outcome": decision.outcome,
        "reliefGranted": decision.relief_granted,
        "reliefDenied": decision.relief_denied,
        "disposition": decision.disposition,
        "treatmentNotes": decision.treatment_notes,
        "negativeTreatmentType": decision.negative_treatment_type,
        "negativeTreatmentSource": decision.negative_treatment_source,
        "laterHistory": decision.later_history,
        "pages": [{"pageNumber": page.page_number, "text": page.text} for page in decision.pages.all()],
    }


@api_login_required
def decisions(request):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    query = (request.GET.get("q") or "").strip()
    queryset = CaseLawDecision.objects.all()
    if query:
        queryset = queryset.filter(title__icontains=query)
    return JsonResponse({"decisions": [decision_summary(item) for item in queryset[:100]]})


@api_login_required
def browse(request):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    query = (request.GET.get("q") or "").strip()
    facet = (request.GET.get("facet") or "").strip()
    value = (request.GET.get("value") or "").strip()
    decision_id = request.GET.get("decisionId")
    seed = CaseLawDecision.objects.filter(pk=decision_id).first() if decision_id else None
    queryset = CaseLawDecision.objects.filter(approved_for_search=True)
    list_facet = ""
    if facet and value:
        if facet in {"court", "county", "judge", "authorityLevel", "treatmentStatus"}:
            field = {
                "authorityLevel": "authority_level",
                "treatmentStatus": "treatment_status",
            }.get(facet, facet)
            queryset = queryset.filter(**{field: value})
        elif facet in {"statute", "regulation", "caseCitation", "issue"}:
            list_facet = facet
    if query:
        q = Q(title__icontains=query) | Q(short_title__icontains=query) | Q(docket_number__icontains=query) | Q(key_facts__icontains=query) | Q(outcome__icontains=query)
        queryset = queryset.filter(q)

    candidates = list(queryset[:1200])
    if list_facet:
        field = {
            "statute": "statutes_cited",
            "regulation": "regulations_cited",
            "caseCitation": "cases_cited",
            "issue": "issues",
        }[list_facet]
        candidates = [
            candidate for candidate in candidates
            if value.casefold() in " ".join(_list(getattr(candidate, field))).casefold()
        ]
    query_terms = _terms(query)
    court_counts = Counter(item.court for item in candidates if item.court)
    county_counts = Counter(item.county for item in candidates if item.county)
    judge_counts = Counter(item.judge for item in candidates if item.judge)
    authority_counts = Counter(item.authority_level for item in candidates if item.authority_level)
    treatment_counts = Counter(item.treatment_status for item in candidates if item.treatment_status)
    statute_counts = Counter(statute for item in candidates for statute in _list(item.statutes_cited))
    regulation_counts = Counter(reg for item in candidates for reg in _list(item.regulations_cited))
    case_counts = Counter(case for item in candidates for case in _list(item.cases_cited))
    issue_counts = Counter(issue for item in candidates for issue in _list(item.issues))

    scored = []
    for candidate in candidates:
        if seed and candidate.id == seed.id:
            continue
        score, reasons = _score_related(candidate, seed, query_terms)
        if seed and score <= 0:
            continue
        if not seed and not query and not facet:
            score = 1
        scored.append((score, reasons, candidate))
    scored.sort(key=lambda item: (-item[0], item[2].decision_date or item[2].imported_at.date(), item[2].title))
    results = [
        {**decision_source_result(candidate, score=score), "clusterReasons": reasons}
        for score, reasons, candidate in scored[:40]
    ]

    clusters = []
    for label, reason in [
        ("Shared authorities", "shared statute"),
        ("Similar issues", "similar issues"),
        ("Same court or county", "same county"),
        ("Query matches", "query match"),
    ]:
        items = [
            {**decision_source_result(candidate, score=score), "clusterReasons": reasons}
            for score, reasons, candidate in scored
            if reason in reasons
        ][:8]
        if items:
            clusters.append({"label": label, "results": items})

    return JsonResponse({
        "facets": {
            "court": _facet_items(court_counts, "court"),
            "county": _facet_items(county_counts, "county"),
            "judge": _facet_items(judge_counts, "judge"),
            "authorityLevel": _facet_items(authority_counts, "authorityLevel"),
            "treatmentStatus": _facet_items(treatment_counts, "treatmentStatus"),
            "statute": _facet_items(statute_counts, "statute"),
            "regulation": _facet_items(regulation_counts, "regulation"),
            "caseCitation": _facet_items(case_counts, "caseCitation"),
            "issue": _facet_items(issue_counts, "issue"),
        },
        "clusters": clusters,
        "results": results,
        "totalCandidates": len(candidates),
        "seed": decision_summary(seed) if seed else None,
    })


@api_login_required
def catalog(request):
    """The whole approved corpus, narrowed by metadata rather than by a query."""
    if request.method != "GET":
        return method_not_allowed(["GET"])
    rows = list(CaseLawDecision.objects.filter(approved_for_search=True).values(*ROW_FIELDS))
    payload = browse_catalog(
        rows,
        query=request.GET.get("q", ""),
        filters=read_filters(request.GET),
        sort=request.GET.get("sort", "newest"),
        limit=request.GET.get("limit", 25),
        offset=request.GET.get("offset", 0),
    )
    page_ids = payload.pop("ids")
    decisions = {decision.id: decision for decision in CaseLawDecision.objects.filter(pk__in=page_ids)}
    payload["results"] = [
        decision_source_result(decisions[decision_id])
        for decision_id in page_ids
        if decision_id in decisions
    ]
    return JsonResponse(payload)


@api_login_required
def decision_detail(request, decision_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    decision = get_object_or_404(CaseLawDecision, pk=decision_id)
    return JsonResponse({"decision": decision_detail_payload(decision)})


@api_login_required
def decision_artifacts(request, decision_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    decision = get_object_or_404(CaseLawDecision, pk=decision_id)
    artifacts = [
        {
            "id": artifact.id,
            "artifactType": artifact.artifact_type,
            "originalFilename": artifact.original_filename,
            "storageBackend": artifact.storage_backend,
            "storageKey": artifact.storage_key,
            "contentType": artifact.content_type,
            "sizeBytes": artifact.size_bytes,
            "sha256": artifact.sha256,
            "createdAt": artifact.created_at.isoformat(),
        }
        for artifact in decision.artifacts.all()
    ]
    return JsonResponse({"artifacts": artifacts})


@api_login_required
def decision_pdf(request, decision_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    decision = get_object_or_404(CaseLawDecision, pk=decision_id)
    artifact = decision.artifacts.filter(artifact_type="original_pdf").first()
    if not artifact:
        return JsonResponse({"error": "No original PDF artifact is available for this decision."}, status=404)
    storage = get_caselaw_storage()
    try:
        file_handle = storage.open(artifact.storage_key)
    except OSError:
        return JsonResponse({"error": "The stored PDF artifact could not be opened."}, status=404)
    response = FileResponse(
        file_handle,
        content_type=artifact.content_type or "application/pdf",
        filename=artifact.original_filename or f"decision-{decision.id}.pdf",
        as_attachment=False,
    )
    response["Content-Disposition"] = f'inline; filename="{artifact.original_filename or f"decision-{decision.id}.pdf"}"'
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response


@api_login_required
def decision_similar(request, decision_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    decision = get_object_or_404(CaseLawDecision, pk=decision_id)
    edges = CaseLawSimilarityEdge.objects.filter(from_decision=decision).select_related("to_decision")[:25]
    return JsonResponse({
        "similar": [
            {
                "relationType": edge.relation_type,
                "score": edge.score,
                "metadata": edge.metadata,
                "decision": decision_summary(edge.to_decision),
            }
            for edge in edges
        ]
    })

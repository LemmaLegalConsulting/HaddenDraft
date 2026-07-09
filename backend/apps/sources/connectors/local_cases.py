import re

from django.db.models import Q

from apps.caselaw.models import CaseLawSearchDocument
from apps.sources.connectors.base import SourceConnector, SourceResult


QUERY_STOPWORDS = {
    "about", "after", "against", "also", "and", "are", "can", "does", "for", "from", "have", "how",
    "into", "may", "must", "not", "of", "or", "the", "this", "to", "under", "what", "when", "with",
}

DOCUMENT_TYPE_WEIGHTS = {
    "issues": 60,
    "holdings": 55,
    "rules": 50,
    "facts": 40,
    "procedural_posture": 35,
    "outcome": 35,
    "overview": 30,
    "ocr_chunk": 20,
}


def _terms(value):
    return [term for term in re.findall(r"[a-z0-9]+", (value or "").casefold()) if len(term) > 2 and term not in QUERY_STOPWORDS]


def _snippet(text, terms, *, length=500):
    compact = " ".join((text or "").split())
    if not compact:
        return ""
    positions = [compact.casefold().find(term) for term in terms]
    start_at = min((position for position in positions if position >= 0), default=0)
    start = max(start_at - 100, 0)
    end = min(start + length, len(compact))
    return f"{'... ' if start else ''}{compact[start:end]}{' ...' if end < len(compact) else ''}"


def _date(value):
    return value.isoformat() if value else None


def _citation(decision):
    if decision.citation_string:
        return decision.citation_string
    parts = [decision.short_title or decision.title]
    if decision.docket_number:
        parts.append(f"No. {decision.docket_number}")
    if decision.court:
        parts.append(decision.court)
    if decision.decision_date:
        parts.append(decision.decision_date.isoformat())
    return ", ".join(parts)


def _metadata(decision, document_type):
    return {
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
        "issues": decision.issues,
        "statutesCited": decision.statutes_cited,
        "regulationsCited": decision.regulations_cited,
        "casesCited": decision.cases_cited,
        "sourceSha256": decision.source_sha256,
        "warning": "Treatment/currentness has not been checked." if decision.treatment_status == "unchecked" else "",
    }


def _score(search_doc, terms, jurisdiction):
    decision = search_doc.decision
    haystack = f"{search_doc.title}\n{search_doc.search_text}".casefold()
    hits = sum(term in haystack for term in terms)
    if not hits:
        return 0
    score = DOCUMENT_TYPE_WEIGHTS.get(search_doc.document_type, 10) + hits * 8
    exact_targets = [decision.title, decision.short_title, decision.docket_number, decision.case_number]
    query_phrase = " ".join(terms)
    if query_phrase and any(query_phrase in (target or "").casefold() for target in exact_targets):
        score += 100
    if jurisdiction and jurisdiction.casefold() in (decision.jurisdiction or decision.court or "").casefold():
        score += 10
    if decision.treatment_status == "unchecked":
        score -= 5
    if decision.negative_treatment_type or decision.vacated_date or decision.reversed_date or decision.overruled_by:
        score -= 40
    return score


class LocalCaseIndexConnector(SourceConnector):
    kind = "local_cases"
    label = "Local archived cases"
    status = "Indexed"
    detail = "Postgres-backed local case-law decisions and OCR text"

    def search(self, query, *, matter=None, jurisdiction="", limit=5, user=None, request=None):
        terms = _terms(query)
        if not terms:
            return []
        filters = Q()
        for term in terms:
            filters |= Q(search_text__icontains=term) | Q(title__icontains=term) | Q(decision__title__icontains=term) | Q(decision__docket_number__icontains=term)
        queryset = (
            CaseLawSearchDocument.objects
            .select_related("decision")
            .filter(filters, decision__approved_for_search=True)
        )
        if jurisdiction:
            queryset = queryset.filter(
                Q(decision__jurisdiction__icontains=jurisdiction)
                | Q(decision__court__icontains=jurisdiction)
                | Q(decision__county__icontains=jurisdiction)
            )

        ranked = []
        for search_doc in queryset[:500]:
            score = _score(search_doc, terms, jurisdiction)
            if score <= 0:
                continue
            ranked.append((score, search_doc))
        ranked.sort(key=lambda item: (-item[0], item[1].decision.title, item[1].id))

        results = []
        used_decisions = set()
        for score, search_doc in ranked:
            decision = search_doc.decision
            if decision.id in used_decisions:
                continue
            used_decisions.add(decision.id)
            results.append(
                SourceResult(
                    id=f"local-case:{decision.id}:{search_doc.id}",
                    title=decision.title,
                    snippet=_snippet(search_doc.search_text, terms),
                    source_kind=self.kind,
                    source_label="Local case law",
                    citation=_citation(decision),
                    url=f"/api/caselaw/decisions/{decision.id}/",
                    metadata={**_metadata(decision, search_doc.document_type), "rankScore": score},
                )
            )
            if len(results) >= limit:
                break
        return results

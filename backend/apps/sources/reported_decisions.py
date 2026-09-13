"""Free, source-specific opinion fallbacks ahead of CourtListener."""

from io import BytesIO
import re

from eyecite import get_citations
from pypdf import PdfReader
import requests

from apps.caselaw.cap import CapClient, CapError, parse_citation
from apps.caselaw.remote_importing import import_public_opinion
from apps.sources.connectors.base import SourceResult


OHIO_ROD_BASE = "https://www.supremecourt.ohio.gov/rod/docs/pdf"


def _reporter_citations(value):
    values = []
    for citation in get_citations(str(value or "")):
        corrected = getattr(citation, "corrected_citation", lambda: "")()
        if corrected and parse_citation(corrected):
            values.append(corrected)
    return list(dict.fromkeys(values))


def _ohio_location(target):
    combined = f"{target.get('citation', '')} {target.get('proposition', '')}"
    webcite = re.search(r"\b(19\d{2}|20\d{2})-Ohio-(\d{1,5})\b", combined, re.I)
    if not webcite:
        return None
    district = re.search(r"\b(1[0-2]|[1-9])(?:st|nd|rd|th|d)\s+Dist\.?\b", combined, re.I)
    if district:
        district_number = district.group(1)
    elif re.search(r"Ohio St\.?|Supreme Court of Ohio", combined, re.I):
        district_number = "0"
    else:
        return None
    citation = f"{webcite.group(1)}-Ohio-{webcite.group(2)}"
    return district_number, webcite.group(1), citation


def _pdf_text(content):
    try:
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages).strip()
    except Exception:  # malformed/unreadable remote PDF is an unavailable source
        return ""


class FreeReportedDecisionFallback:
    """Resolve Ohio ROD first, then CAP; persist every successful opinion."""

    def __init__(self, *, session=None, cap_client=None, timeout=30):
        self.session = session or requests.Session()
        self.cap = cap_client or CapClient(timeout=timeout)
        self.timeout = timeout

    def resolve(self, targets):
        results = []
        unresolved = []
        trace = {"method": "ohio_rod_then_cap", "ohioRequested": 0, "ohioResolved": 0,
                 "capRequested": 0, "capResolved": 0}
        for target in targets:
            result = self._ohio(target, trace)
            if result:
                results.append(result)
            else:
                unresolved.append(target)
        for target in unresolved:
            result = self._cap(target, trace)
            if result:
                results.append(result)
        trace["resolved"] = len(results)
        return results, trace

    def _ohio(self, target, trace):
        location = _ohio_location(target)
        if not location:
            return None
        district, year, webcite = location
        url = f"{OHIO_ROD_BASE}/{district}/{year}/{webcite}.pdf"
        trace["ohioRequested"] += 1
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException:
            return None
        if response.status_code != 200:
            return None
        text = _pdf_text(response.content)
        if not text:
            return None
        title = target.get("claimedCaseName") or webcite
        decision = import_public_opinion(
            title=title, external_id=f"ohio-rod:{webcite}", text=text,
            citations=[webcite], source_url=url, metadata_source="ohio_reported_decisions",
            decision_date=f"{year}-01-01", publication_status="published",
            storage_slug="ohio-reported-decisions",
        )
        trace["ohioResolved"] += 1
        return SourceResult(
            id=f"ohio-rod:{webcite}", title=title, citation=webcite, snippet=text,
            source_kind="ohio_reported_decisions", source_label="Supreme Court of Ohio Reporter of Decisions",
            url=url, metadata={"targetId": target["targetId"], "decisionId": decision.id,
                               "provider": "Supreme Court of Ohio"},
        )

    def _cap(self, target, trace):
        citations = _reporter_citations(target.get("citation"))
        for citation in citations:
            trace["capRequested"] += 1
            try:
                resolved = self.cap.resolve(citation)
            except CapError:
                continue
            if resolved.get("status") != "found":
                continue
            metadata = resolved["metadata"]
            decision = import_public_opinion(
                title=metadata["title"], external_id=metadata["external_source_id"],
                text=resolved["text"], citations=[metadata["citation_string"], *metadata["parallel_citations"]],
                source_url=metadata["source_url"], metadata_source="caselaw_access_project",
                decision_date=metadata.get("decision_date", ""), publication_status="published",
                storage_slug="cap",
            )
            trace["capResolved"] += 1
            return SourceResult(
                id=metadata["external_source_id"], title=metadata["title"],
                citation=metadata["citation_string"], snippet=resolved["text"],
                source_kind="cap", source_label="Caselaw Access Project",
                url=metadata["source_url"], metadata={"targetId": target["targetId"],
                    "decisionId": decision.id, "provider": "Harvard Caselaw Access Project"},
            )
        return None

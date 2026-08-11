"""Filling citation-only records from the Caselaw Access Project's bulk files.

Part of this corpus arrived as citation stubs: a single generated page carrying
a case name and a reporter citation, with the opinion never obtained.  A
citation is not nothing — it lets the tool confirm that a cited case exists —
but the opinion is what a reader needs.

CAP publishes its scanned reporters as static files, no API key and no request
signing, laid out by reporter and volume:

    /<reporter>/<volume>/CasesMetadata.json   every case in the volume
    /<reporter>/<volume>/cases/<file>.json    one case, with opinion text
    /<reporter>/<volume>/case-pdfs/<file>.pdf the reporter pages themselves

A citation resolves to a volume and a first page, which is enough to find the
case without searching.  Volume metadata is fetched once and reused, because one
volume usually answers several citations.

Coverage ends where CAP's scanning did, around 2018-2020. A citation newer than
its reporter's run is not an error to retry; it is a case this route cannot
reach, and it stays a citation-only record.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

CAP_BASE = "https://static.case.law"
USER_AGENT = "agentic-housing-drafting/1.0 (legal aid research tool)"

# Reporter short names as this corpus writes them, mapped to CAP's directory
# slugs. Hand-written rather than derived: CAP's slugs are not a mechanical
# transform of the short name ("F.2d" is "f2d" but "Ohio St. 3d" is
# "ohio-st-3d"), and guessing wrong fetches the wrong reporter silently.
REPORTER_SLUGS = {
    "ohio app.3d": "ohio-app-3d",
    "ohio app. 3d": "ohio-app-3d",
    "ohio app.2d": "ohio-app-2d",
    "ohio app. 2d": "ohio-app-2d",
    "ohio app.": "ohio-app",
    "ohio app": "ohio-app",
    "ohio st.3d": "ohio-st-3d",
    "ohio st. 3d": "ohio-st-3d",
    "ohio st.2d": "ohio-st-2d",
    "ohio st. 2d": "ohio-st-2d",
    "ohio st.": "ohio-st",
    "ohio st": "ohio-st",
    "ohio misc.2d": "ohio-misc-2d",
    "ohio misc. 2d": "ohio-misc-2d",
    "ohio misc.": "ohio-misc",
    "ohio misc": "ohio-misc",
    "ohio law abs.": "ohio-law-abs",
    "n.e.2d": "ne2d",
    "n.e.3d": "ne3d",
    "f.2d": "f2d",
    "f.3d": "f3d",
    "f.supp.": "f-supp",
    "f.supp.2d": "f-supp-2d",
    "b.r.": "br",
    "u.s.": "us",
    "s.ct.": "s-ct",
}

CITATION = re.compile(r"^\s*(?P<volume>\d+)\s+(?P<reporter>.+?)\s+(?:at\s+)?(?P<page>\d+)\s*$")


class CapError(Exception):
    """A CAP lookup failed in a way the caller should report, not retry blindly."""


def parse_citation(citation):
    """Split "104 Ohio St. 372" into the volume, reporter slug, and first page.

    Returns None when the citation is not a volume-reporter-page cite or names a
    reporter CAP does not publish, so an unresolvable citation is visibly
    unresolvable rather than silently mapped to the wrong reporter.
    """
    match = CITATION.match(str(citation or ""))
    if not match:
        return None
    reporter = re.sub(r"\s+", " ", match.group("reporter")).strip().casefold()
    slug = REPORTER_SLUGS.get(reporter) or REPORTER_SLUGS.get(reporter.replace(" ", ""))
    if not slug:
        return None
    return {
        "citation": f"{match.group('volume')} {match.group('reporter').strip()} {match.group('page')}",
        "reporter": slug,
        "volume": match.group("volume"),
        "page": match.group("page"),
    }


def normalize_citation(value):
    return re.sub(r"[\s.]+", "", str(value or "")).casefold()


def find_case(cases, parsed):
    """The case in a volume that a citation points at.

    Matched on the citation itself first, and only then on the first page, so a
    volume whose page numbering restarts cannot hand back the wrong case.
    """
    wanted = normalize_citation(parsed["citation"])
    for case in cases:
        for cite in case.get("citations") or []:
            if normalize_citation(cite.get("cite")) == wanted:
                return case
    for case in cases:
        if str(case.get("first_page")) == parsed["page"]:
            return case
    return None


def opinion_text(case):
    """The readable opinion, head matter first, as ingestion expects plain text."""
    body = case.get("casebody") or {}
    parts = []
    head = (body.get("head_matter") or "").strip()
    if head:
        parts.append(head)
    for opinion in body.get("opinions") or []:
        text = (opinion.get("text") or "").strip()
        if text:
            author = (opinion.get("author") or "").strip()
            parts.append(f"{author}\n{text}" if author and not text.startswith(author) else text)
    return "\n\n".join(parts).strip()


def case_metadata(case, parsed, *, source_url):
    """A sidecar in the shape ingestion already reads, with CAP's provenance kept."""
    court = (case.get("court") or {}).get("name") or ""
    jurisdiction = (case.get("jurisdiction") or {}).get("name_long") or ""
    citations = [cite.get("cite") for cite in case.get("citations") or [] if cite.get("cite")]
    official = next((cite for cite in citations if cite), parsed["citation"])
    return {
        "title": case.get("name") or case.get("name_abbreviation") or parsed["citation"],
        "short_title": case.get("name_abbreviation") or "",
        "docket_number": case.get("docket_number") or "",
        "citation_string": official,
        "parallel_citations": [cite for cite in citations if cite != official],
        "decision_date": case.get("decision_date") or "",
        "court": court,
        "jurisdiction": jurisdiction,
        "judges": (case.get("casebody") or {}).get("judges") or [],
        "parties": (case.get("casebody") or {}).get("parties") or [],
        "publication_status": "published",
        "precedential_status": "published opinion",
        "is_unpublished": False,
        "external_source_id": f"cap:{case.get('id')}",
        "metadata_source": "caselaw_access_project",
        "source_url": source_url,
        "cap_provenance": case.get("provenance") or {},
        "cap_last_updated": case.get("last_updated") or "",
        "treatment_status": "unchecked",
        "treatment_notes": (
            "Imported from the Caselaw Access Project static bulk files. "
            "Currentness and subsequent history have not been checked."
        ),
    }


class CapClient:
    """Reads CAP's static files. Volume indexes are fetched once and reused."""

    def __init__(self, *, base=CAP_BASE, opener=None, timeout=60):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self._opener = opener or self._fetch
        self._volumes = {}

    def _fetch(self, url):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise CapError(f"{url} returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise CapError(f"{url} could not be read: {error}") from error

    def volume_cases(self, reporter, volume):
        key = (reporter, volume)
        if key not in self._volumes:
            raw = self._opener(f"{self.base}/{reporter}/{volume}/CasesMetadata.json")
            try:
                self._volumes[key] = json.loads(raw.decode("utf-8")) if raw else []
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise CapError(f"{reporter}/{volume} index is not readable JSON: {error}") from error
        return self._volumes[key]

    def case(self, reporter, volume, file_name):
        raw = self._opener(f"{self.base}/{reporter}/{volume}/cases/{file_name}.json")
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise CapError(f"{reporter}/{volume}/{file_name} is not readable JSON: {error}") from error

    def case_pdf(self, reporter, volume, file_name):
        return self._opener(f"{self.base}/{reporter}/{volume}/case-pdfs/{file_name}.pdf")

    def resolve(self, citation):
        """Everything needed to write a bundle for one citation, or a reason it failed."""
        parsed = parse_citation(citation)
        if not parsed:
            return {"status": "unparsed_citation", "citation": citation}
        cases = self.volume_cases(parsed["reporter"], parsed["volume"])
        if not cases:
            return {"status": "volume_not_published", **parsed}
        found = find_case(cases, parsed)
        if not found:
            return {"status": "case_not_in_volume", **parsed}
        case = self.case(parsed["reporter"], parsed["volume"], found["file_name"])
        if not case:
            return {"status": "case_body_missing", **parsed}
        text = opinion_text(case)
        if not text:
            return {"status": "no_opinion_text", **parsed}
        url = f"{self.base}/{parsed['reporter']}/{parsed['volume']}/cases/{found['file_name']}.json"
        return {
            "status": "found",
            **parsed,
            "file_name": found["file_name"],
            "text": text,
            "metadata": case_metadata(case, parsed, source_url=url),
        }

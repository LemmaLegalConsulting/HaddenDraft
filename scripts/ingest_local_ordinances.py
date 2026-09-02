#!/usr/bin/env python3
"""Fetch, provenance-stamp, chunk, and differentially refresh Ohio local law.

Local law reaches this corpus by a different road than the Revised Code does.
There is no single official publisher of Ohio municipal codes: the text most
lawyers read lives on two commercial codifier sites, and both refuse automated
retrieval -- American Legal Publishing answers a script with a Cloudflare bot
challenge, and Municode's content API requires an authenticated token.  Working
around either would mean evading an access control, so neither is a fetch
target here.  They stay citation targets instead.

What can be read directly is the city's own legislative record.  Cities running
Legistar publish a documented, unauthenticated Web API that returns the enacted
act -- its file number, its dates, and its full text.  That is authoritative in
the strongest sense available: it is the legislature's own record of what it
passed.  It is also *not* the codified chapter as it stands today, so every
record generated from it is stamped ``text_basis: enacted_act`` and carries the
codifier URL a reader must check before relying on it.  Saying which of those
two things a record is beats quietly implying it is the other.

A target with no permitted route is written into the manifest as ``pending``
with the reason.  It produces no chunk, so retrieval can never return it as
law, and it stays visible as a gap rather than vanishing into an absence that
looks like coverage.

Examples:
  python scripts/ingest_local_ordinances.py --all
  python scripts/ingest_local_ordinances.py --municipality toledo
  python scripts/ingest_local_ordinances.py --topic pay-to-stay
  python scripts/ingest_local_ordinances.py --priority 1 --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "content" / "ordinances"
SCOPE_PATH = LIBRARY / "scope.yaml"
GENERATOR = "scripts/ingest_local_ordinances.py"
USER_AGENT = "agentic-housing-drafting ordinance indexer/1.0"
LEGISTAR_BASE = "https://webapi.legistar.com/v1"
MAX_WORDS = 1100

# Below this, a Legistar matter body is a title stub rather than the act, and
# the real text is in an attachment.  Cleveland files its ordinances that way.
MIN_MATTER_TEXT_CHARS = 1500

# Legistar renders its own field markers into the plain-text body.
LEGISTAR_MARKER = re.compile(r"^\.\.[A-Za-z]+\s*$")

# Some councils enact a chapter by reference: the act recites "Chapter 792 ...
# is hereby enacted ... as set forth in EXHIBIT A", and the chapter itself is
# an attachment.  Such an act is long enough to pass the length check and
# contains none of the law, which is the worst combination -- it looks like a
# successful retrieval.  The exhibit language is the tell.
INCORPORATES_BY_EXHIBIT = re.compile(
    r"set forth in\s+(?:the\s+)?exhibit|attached hereto and made a part", re.IGNORECASE,
)

DOCX_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class AcquisitionError(RuntimeError):
    """A target could not be retrieved from the route its scope entry names."""


def sha256(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def front(data: dict) -> str:
    return "---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip() + "\n---\n"


def collapse(text: str) -> str:
    """Normalize whitespace without dissolving paragraph boundaries."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def date_only(value) -> str:
    return str(value)[:10] if value else ""


# --------------------------------------------------------------------------
# Document text
# --------------------------------------------------------------------------

def docx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise AcquisitionError("Could not read DOCX text") from exc
    root = ElementTree.fromstring(xml)
    paragraphs = []
    for paragraph in root.iter(f"{DOCX_NAMESPACE}p"):
        line = "".join(node.text or "" for node in paragraph.iter(f"{DOCX_NAMESPACE}t"))
        if line.strip():
            paragraphs.append(line.strip())
    return collapse("\n\n".join(paragraphs))


def pdf_text(content: bytes, *, pages=None) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - declared in requirements.txt
        raise AcquisitionError("PDF extraction requires pypdf") from exc
    reader = PdfReader(io.BytesIO(content))
    selected = reader.pages
    if pages:
        first, last = int(pages[0]), int(pages[-1])
        selected = reader.pages[max(first - 1, 0):last]
        if not selected:
            raise AcquisitionError(f"Pages {first}-{last} are outside a {len(reader.pages)}-page document")
    return collapse("\n\n".join(page.extract_text() or "" for page in selected))


def ocr_pdf(content: bytes, *, pages=None, dpi=300, language="eng") -> str:
    """Read a scanned ordinance by rendering it and recognizing the glyphs.

    Much of what a small municipality publishes is a photograph of paper.  The
    document is public, fetchable, and completely unreadable to everything
    downstream, which is a worse outcome than a missing link because it looks
    like coverage.

    OCR output is derived text, not the publisher's characters: it mistakes
    digits, drops diacritics, and mangles tables.  Everything produced here is
    stamped ``ocr_text`` so a section number or a dollar figure read out of a
    scan is never mistaken for one read off a page.
    """
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        raise AcquisitionError("OCR needs poppler-utils (pdftoppm) and tesseract on PATH")
    with tempfile.TemporaryDirectory() as staging:
        workspace = Path(staging)
        (workspace / "source.pdf").write_bytes(content)
        render = ["pdftoppm", "-r", str(dpi), "-png"]
        if pages:
            render += ["-f", str(int(pages[0])), "-l", str(int(pages[-1]))]
        try:
            subprocess.run(
                [*render, str(workspace / "source.pdf"), str(workspace / "page")],
                check=True, capture_output=True, timeout=1800,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise AcquisitionError(f"Could not render the PDF for OCR: {exc}") from exc
        rendered = sorted(workspace.glob("page-*.png"))
        if pages:
            # ``pdftoppm`` only takes a first and a last page, so a list with a
            # gap in it renders the pages in between too.  Drop them here.
            #
            # The gap is the point.  An amending ordinance shows what it deletes
            # as struck-through text: South Euclid's Ord. 12-17 strikes three
            # whole pages.  OCR reads a strikethrough as noise, and the text
            # underneath it is the old chapter, which is not law either.  Keeping
            # those pages would put several hundred lines of garble into the
            # corpus under the heading of an enacted chapter.
            wanted = {int(number) for number in pages}
            rendered = [
                image for image in rendered
                if int(image.stem.rsplit("-", 1)[-1]) in wanted
            ]
        if not rendered:
            raise AcquisitionError("Rendering produced no pages to recognize")
        recognized = []
        for image in rendered:
            try:
                result = subprocess.run(
                    ["tesseract", str(image), "stdout", "-l", language],
                    check=True, capture_output=True, text=True, timeout=600,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise AcquisitionError(f"OCR failed on {image.name}: {exc}") from exc
            recognized.append(result.stdout)
    text = collapse("\n\n".join(recognized))
    if not text:
        raise AcquisitionError("OCR recognized no text in the rendered pages")
    return text


def html_text(content: bytes) -> str:
    text = content.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", "\n\n", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    return collapse(html.unescape(re.sub(r"<[^>]+>", " ", text)))


def document_text(content: bytes, *, url: str = "", content_type: str = "", pages=None) -> str:
    """Extract text by declared type, falling back to the URL's own suffix."""
    kind = (content_type or "").casefold()
    suffix = Path(urlsplit(url).path).suffix.casefold()
    if "wordprocessingml" in kind or suffix == ".docx":
        return docx_text(content)
    if "pdf" in kind or suffix == ".pdf":
        return pdf_text(content, pages=pages)
    if "html" in kind or suffix in {".html", ".htm"}:
        return html_text(content)
    if kind.startswith("text/") or suffix in {".txt", ".md"}:
        return collapse(content.decode("utf-8", errors="replace"))
    raise AcquisitionError(f"No extractor for {content_type or suffix or url or 'document'}")


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def request(session: requests.Session, url: str, *, params=None, expect_json=False):
    response = None
    for attempt in range(4):
        response = session.get(
            url,
            params=params,
            timeout=60,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json" if expect_json else "*/*"},
        )
        if response.status_code not in {429, 502, 503, 504}:
            break
        try:
            delay = min(float(response.headers.get("Retry-After", "")), 60)
        except ValueError:
            delay = 2**attempt
        time.sleep(delay)
    assert response is not None
    if response.status_code == 403:
        raise AcquisitionError(
            f"{url} refused automated retrieval (HTTP 403). "
            "Codifier sites are citation targets, not fetch targets."
        )
    if not response.ok:
        raise AcquisitionError(f"{url} returned HTTP {response.status_code}")
    return response.json() if expect_json else response


# --------------------------------------------------------------------------
# Acquisition: Legistar
# --------------------------------------------------------------------------

def legistar_matters(session, client, *, filter_expression, top=25):
    return request(
        session,
        f"{LEGISTAR_BASE}/{client}/matters",
        params={"$filter": filter_expression, "$top": top},
        expect_json=True,
    )


def _quote(value: str) -> str:
    return str(value).replace("'", "''")


def legistar_find_matter(session, client, acquire):
    """Resolve a scope entry to one matter, by file number or by title search."""
    file_number = acquire.get("file_number")
    if file_number:
        matters = legistar_matters(session, client, filter_expression=f"MatterFile eq '{_quote(file_number)}'")
        if not matters:
            raise AcquisitionError(f"No {client} matter with file number {file_number}")
        return matters[0]

    search = acquire.get("search")
    if not search:
        raise AcquisitionError("A legistar target needs either file_number or search")
    matters = legistar_matters(
        session, client, filter_expression=f"substringof('{_quote(search)}',MatterTitle)", top=50,
    )
    # An unqualified title search reaches committee reports and communications
    # as well as legislation.  Only an ordinance enacts text, and only a passed
    # one is law, so the search narrows to those before choosing the latest.
    ordinances = [
        matter for matter in matters
        if "ordinance" in str(matter.get("MatterTypeName") or "").casefold()
        and matter.get("MatterPassedDate")
    ]
    if not ordinances:
        raise AcquisitionError(f"No passed {client} ordinance matched search {search!r}")
    ordinances.sort(key=lambda matter: str(matter.get("MatterPassedDate") or ""), reverse=True)
    return ordinances[0]


def legistar_matter_text(session, client, matter_id):
    versions = request(session, f"{LEGISTAR_BASE}/{client}/matters/{matter_id}/versions", expect_json=True)
    if not versions:
        return ""
    key = versions[0].get("Key")
    payload = request(session, f"{LEGISTAR_BASE}/{client}/matters/{matter_id}/texts/{key}", expect_json=True)
    body = payload.get("MatterTextPlain") or ""
    lines = [line for line in body.splitlines() if not LEGISTAR_MARKER.match(line.strip())]
    return collapse("\n".join(lines))


def legistar_attachment_text(session, client, matter_id, *, prefer=""):
    attachments = request(
        session, f"{LEGISTAR_BASE}/{client}/matters/{matter_id}/attachments", expect_json=True,
    )
    if not attachments:
        return "", ""
    wanted = (prefer or "").casefold()
    ordered = sorted(
        attachments,
        key=lambda item: 0 if wanted and wanted in str(item.get("MatterAttachmentName") or "").casefold() else 1,
    )
    for attachment in ordered:
        url = attachment.get("MatterAttachmentHyperlink")
        if not url:
            continue
        try:
            response = request(session, url)
            text = document_text(
                response.content, url=url, content_type=response.headers.get("Content-Type", ""),
            )
        except AcquisitionError:
            continue
        if text:
            return text, str(attachment.get("MatterAttachmentName") or "")
    return "", ""


# A chapter number is a short string, so a bare substring search for it also
# reaches an unrelated ordinance number ("1365-2023"), a dollar figure, and a
# fund code.  A real amendment names the code it changes, so the number has to
# appear as a chapter or section reference and not inside a longer number.
CODE_REFERENCE = r"(?:chapter|section)s?\b[^.;:]{0,80}?(?<!\d)%s(?!\d)"


def mentions_code_reference(title, query):
    return bool(re.search(CODE_REFERENCE % re.escape(query), title, re.IGNORECASE))


def legistar_amendments(session, client, query, *, exclude_file=""):
    """Later acts touching the same chapter, newest first.

    A chapter is rarely enacted once.  Toledo's Chapter 1760 was enacted,
    repealed and re-enacted twice, and then technically corrected; a reader
    handed only the first act would be reading law that no longer exists.  This
    does not decide which act controls -- it shows the chain so a person can.
    """
    if not query:
        return []
    try:
        matters = legistar_matters(
            session, client, filter_expression=f"substringof('{_quote(query)}',MatterTitle)", top=50,
        )
    except AcquisitionError:
        return []
    history = [
        {
            "file_number": str(matter.get("MatterFile") or ""),
            "title": " ".join(str(matter.get("MatterTitle") or "").split())[:400],
            "type": str(matter.get("MatterTypeName") or ""),
            "status": str(matter.get("MatterStatusName") or ""),
            "passed_date": date_only(matter.get("MatterPassedDate")),
            "intro_date": date_only(matter.get("MatterIntroDate")),
        }
        for matter in matters
        if "ordinance" in str(matter.get("MatterTypeName") or "").casefold()
        and str(matter.get("MatterFile") or "") != exclude_file
        and mentions_code_reference(" ".join(str(matter.get("MatterTitle") or "").split()), query)
    ]
    history.sort(key=lambda item: (item["passed_date"], item["intro_date"]), reverse=True)
    return history[:20]


def acquire_legistar(session, municipality, acquire):
    client = acquire.get("client") or municipality.get("legistar_client")
    if not client:
        raise AcquisitionError(f"{municipality['slug']} has no legistar_client configured")
    matter = legistar_find_matter(session, client, acquire)
    matter_id = matter["MatterId"]
    file_number = str(matter.get("MatterFile") or "")

    text = "" if acquire.get("prefer_attachment") else legistar_matter_text(session, client, matter_id)
    text_source = "legistar_matter_text" if text else ""
    if len(text) < MIN_MATTER_TEXT_CHARS or INCORPORATES_BY_EXHIBIT.search(text):
        attachment_text, attachment_name = legistar_attachment_text(
            session, client, matter_id, prefer=acquire.get("prefer_attachment", ""),
        )
        incorporated = bool(INCORPORATES_BY_EXHIBIT.search(text))
        if attachment_text and (incorporated or len(attachment_text) > len(text)):
            text, text_source = attachment_text, f"legistar_attachment:{attachment_name}"
    if not text:
        raise AcquisitionError(f"{client} matter {file_number or matter_id} carries no retrievable text")

    return {
        "text": text,
        "acquisition_method": "legistar",
        "text_basis": "enacted_act",
        "text_source": text_source,
        "publisher": f"{municipality['name']} City Council (Legistar legislative record)",
        "source_url": f"{LEGISTAR_BASE}/{client}/matters/{matter_id}",
        "act_file_number": file_number,
        "act_title": " ".join(str(matter.get("MatterTitle") or "").split()),
        "act_type": str(matter.get("MatterTypeName") or ""),
        "act_status": str(matter.get("MatterStatusName") or ""),
        "introduced_date": date_only(matter.get("MatterIntroDate")),
        "enacted_date": date_only(matter.get("MatterPassedDate")) or date_only(matter.get("MatterEnactmentDate")),
        "enactment_number": str(matter.get("MatterEnactmentNumber") or ""),
        "amendment_history": legistar_amendments(
            session, client, acquire.get("amendment_query", ""), exclude_file=file_number,
        ),
    }


# --------------------------------------------------------------------------
# Acquisition: official document
# --------------------------------------------------------------------------

# Typographic characters a PDF renders and a person retypes differently.  A
# marker that fails only because the document has a curly apostrophe is a
# marker that fails for no reason a reader would recognize.
_TYPOGRAPHY = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u00a0": " ", "\u2026": "...",
})


def _normalize_for_match(text):
    return re.sub(r"\s+", " ", text.translate(_TYPOGRAPHY)).casefold()


def _squeeze(text):
    """Drop whitespace entirely, keeping each character's index in the original.

    PDF text extractors break lines in places no reader would: pypdf renders
    Worthington's Ordinance 21-2023 with the first letter of many lines split
    off from the rest, so "SECTION 2." comes out as "SE\nCTION 2.".  Collapsing
    runs of whitespace to one space cannot repair that -- it yields "SE CTION",
    which no marker anybody types will ever match.

    Matching with the whitespace removed does repair it, and cannot introduce a
    false match for a marker of any realistic length.  It is a fallback rather
    than the primary rule because a match that survives whitespace is the
    stronger signal, and keeping it first means an existing marker keeps hitting
    the position it always hit.
    """
    kept, offsets = [], []
    for index, character in enumerate(text.translate(_TYPOGRAPHY)):
        if not character.isspace():
            kept.append(character)
            offsets.append(index)
    return "".join(kept).casefold(), offsets


def _raw_offset(text, normalized_offset):
    """Map an offset in whitespace-collapsed text back onto the original."""
    seen = 0
    previous_space = False
    for index, character in enumerate(text):
        if seen >= normalized_offset:
            return index
        if character.isspace():
            if not previous_space:
                seen += 1
            previous_space = True
        else:
            seen += 1
            previous_space = False
    return len(text)


def _find_span(text, start_marker, end_marker):
    """Locate the marked span, tolerating whitespace the extractor invented.

    Returns raw (start, end) offsets into ``text``, or None for whichever marker
    could not be found -- the caller decides that a missing marker is fatal.
    """
    haystack = _normalize_for_match(text)
    start = haystack.find(_normalize_for_match(start_marker))
    if start >= 0:
        end = len(haystack)
        if end_marker:
            end = haystack.find(_normalize_for_match(end_marker), start + 1)
        if end >= 0:
            return _raw_offset(text, start), _raw_offset(text, end), False

    squeezed, offsets = _squeeze(text)
    start = squeezed.find(_squeeze(start_marker)[0])
    if start < 0:
        return None, None, True
    end = len(squeezed)
    if end_marker:
        end = squeezed.find(_squeeze(end_marker)[0], start + 1)
        if end < 0:
            return offsets[start], None, True
    raw_end = offsets[end] if end < len(offsets) else len(text)
    return offsets[start], raw_end, True


def extract_span(text, extract):
    """Cut one ordinance out of the document that happens to contain it.

    Most of what a city actually publishes is a meeting packet: dozens of pages
    of agenda, minutes, and unrelated legislation with the ordinance somewhere
    in the middle.  Ingesting the packet whole and labelling it "Chapter 1488"
    would misstate what the record is, and it poisons retrieval with pages of
    unrelated municipal business.

    A missing marker is a hard failure.  Silently keeping the whole packet is
    the exact outcome this exists to prevent, and it would be reported as a
    success.
    """
    start_marker = str(extract.get("start", ""))
    end_marker = str(extract.get("end", ""))
    if not start_marker:
        return text, {}
    start, end, squeezed = _find_span(text, start_marker, end_marker)
    if start is None:
        raise AcquisitionError(f"Start marker {start_marker!r} not found in the retrieved document")
    if end is None:
        raise AcquisitionError(f"End marker {end_marker!r} not found after the start marker")
    span = text[start:end].strip()
    if not span:
        raise AcquisitionError("The extracted span is empty")
    record = {
        "extracted": True,
        "start_marker": start_marker,
        "end_marker": end_marker,
        "document_chars": len(text),
        "extracted_chars": len(span),
    }
    if squeezed:
        # Worth recording: the marker only matched once the extractor's invented
        # line breaks were removed, which is a hint the text layer is rough.
        record["matched_without_whitespace"] = True
    return span, record


def _document_payload(content, *, url, content_type, acquire, method, municipality):
    """Turn retrieved bytes into a record, however they were retrieved.

    Shared by the plain-fetch and browser adapters so that OCR, span
    extraction, and provenance stamping cannot drift apart between them.
    """
    extract = acquire.get("extract") or {}
    ocr = acquire.get("ocr") or {}
    text_basis = acquire.get("text_basis", "published_document")
    ocr_record = {}
    if ocr:
        text = ocr_pdf(
            content,
            pages=ocr.get("pages") or extract.get("pages"),
            dpi=int(ocr.get("dpi", 300)),
            language=str(ocr.get("language", "eng")),
        )
        text_basis = "ocr_text"
        ocr_record = {
            "engine": "tesseract",
            "dpi": int(ocr.get("dpi", 300)),
            "pages": ocr.get("pages") or extract.get("pages") or [],
            "language": str(ocr.get("language", "eng")),
        }
    else:
        text = document_text(
            content, url=url, content_type=content_type, pages=extract.get("pages"),
        )
    if not text:
        raise AcquisitionError(f"{url} produced no extractable text")
    text, extraction = extract_span(text, extract)
    return {
        "text": text,
        "extraction": extraction,
        "ocr": ocr_record,

        "acquisition_method": method,
        "text_basis": text_basis,
        "text_source": f"{'ocr' if ocr else method}:{content_type or Path(urlsplit(url).path).suffix}",
        "publisher": acquire.get("publisher", municipality["name"]),
        "source_url": url,
        "raw_sha256": sha256(content),
        "amendment_history": [],
    }


# --------------------------------------------------------------------------
# Acquisition: hand-supplied transcription
# --------------------------------------------------------------------------

def acquire_transcription(_session, municipality, acquire):
    """Text a person supplied, carried with the fact that nobody verified it.

    Some ordinances reach this corpus because a lawyer went and got them.  That
    text is often the only copy available, and refusing it would be worse than
    holding it -- but it has not been read off a publisher's page by anything
    here, and treating it like a retrieved document would launder that.

    So a transcription is stamped ``unverified_transcription``, names who
    supplied it and when, and records the source they assert it came from plus
    the URLs a reader should check it against.  It is searchable and it is
    labelled, which is the honest combination.
    """
    relative = str(acquire.get("file", ""))
    if not relative or ".." in relative.split("/"):
        raise AcquisitionError("A transcription target needs a file inside content/ordinances")
    path = LIBRARY / relative
    if not path.is_file():
        raise AcquisitionError(f"No transcription file at content/ordinances/{relative}")
    raw = path.read_text(encoding="utf-8")
    body = raw.split("---\n", 2)[-1].strip() if raw.startswith("---\n") else raw.strip()
    if not body:
        raise AcquisitionError(f"content/ordinances/{relative} carries no text")
    provided_on = str(acquire.get("provided_on", ""))
    return {
        "text": collapse(body),
        "acquisition_method": "transcription",
        "text_basis": "unverified_transcription",
        "text_source": f"transcription:{relative}",
        "publisher": str(acquire.get("asserted_source", "")) or municipality["name"],
        "source_url": "",
        "raw_sha256": sha256(raw),
        "provided_by": str(acquire.get("provided_by", "")),
        "provided_on": provided_on,
        "asserted_source": str(acquire.get("asserted_source", "")),
        "enacted_date": str(acquire.get("enacted_date", "")),
        "act_file_number": str(acquire.get("act_file_number", "")),
        "amendment_history": [],
    }


def acquire_document(session, municipality, acquire):
    url = acquire.get("url")
    if not url:
        raise AcquisitionError("A document target needs a url")
    response = request(session, url)
    return _document_payload(
        response.content, url=url, content_type=response.headers.get("Content-Type", ""),
        acquire=acquire, method="document", municipality=municipality,
    )


def acquire_browser(_session, municipality, acquire):
    """Drive a real browser to reach a document no URL alone will fetch.

    Some municipal document portals hand the file to JavaScript: the row is
    rendered client-side and the download goes through a token-gated API whose
    response the page turns into a blob.  There is no address to put in a
    config file -- ``apidocprod.egovlink.com/documents/download/490041`` answers
    a bare request with 401, because the token lives in the page.

    So the page is the client.  This is not evasion: the browser does exactly
    what a person clicking Download does, with no credential the site did not
    hand it, and it is used only where the publisher intends the document to be
    downloadable.
    """
    url = acquire.get("url")
    selector = acquire.get("click")
    if not url or not selector:
        raise AcquisitionError("A browser target needs a url and a click selector")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise AcquisitionError("Browser acquisition needs the playwright package") from exc

    wait_ms = int(acquire.get("wait_ms", 5000))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_context(accept_downloads=True).new_page()
            page.goto(url, wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(wait_ms)
            try:
                with page.expect_download(timeout=90000) as pending:
                    # Activated through the DOM rather than a synthetic pointer
                    # event: these rows are often outside the viewport, and a
                    # visibility failure would look like a missing document.
                    page.evaluate(f"document.querySelector({selector!r}).click()")
                download = pending.value
                content = Path(download.path()).read_bytes()
                resolved = download.url
            except Exception as exc:
                raise AcquisitionError(f"No download followed clicking {selector!r} on {url}: {exc}") from exc
        finally:
            browser.close()
    if not content:
        raise AcquisitionError(f"{selector!r} on {url} produced an empty download")
    return {
        **_document_payload(
            content, url=url, content_type=acquire.get("content_type", "application/pdf"),
            acquire=acquire, method="browser", municipality=municipality,
        ),
        # The blob address is per-session and meaningless later; the page and
        # the selector are what actually reproduce this retrieval.
        "browser": {"page_url": url, "selector": selector, "blob_url": resolved[:120]},
    }


ACQUIRERS = {
    "legistar": acquire_legistar,
    "document": acquire_document,
    "browser": acquire_browser,
    "transcription": acquire_transcription,
}

# "We could not get the text" and "there is no text, because the provision is
# not in force" are different answers, and only the second one is useful to an
# advocate.  Recording a repealed or expired provision as pending buries a
# definite answer inside a list of gaps.
NOT_IN_FORCE = "none_in_force"

# How long a record of each kind stays trustworthy without another look.  These
# are review cadences, not expiry dates: a codified chapter can change the day
# after it is read.  Unverified text is rechecked soonest because it is the
# only kind nothing here has ever confirmed.
RECHECK_DAYS = {
    "enacted_act": 180,
    "published_local_rules": 180,
    "published_document": 180,
    "unverified_transcription": 90,
    # Recognized text is a reading of the document, not the document.  It is
    # reviewed on the same cadence as anything else nobody has confirmed.
    "ocr_text": 90,
    "not_acquired": 90,
    # A repeal is settled until something reverses it, so this is a watch for a
    # successor rather than a retry of a failed fetch.
    "no_current_provision": 365,
}


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------

def chunk_text(text: str) -> list[str]:
    chunks, current, words = [], [], 0
    for paragraph in text.split("\n\n"):
        count = len(paragraph.split())
        if current and words + count > MAX_WORDS:
            chunks.append("\n\n".join(current))
            current, words = [], 0
        current.append(paragraph)
        words += count
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def retrieval_hints(municipality, target, topics):
    """Researcher phrasing that the ordinance's own words rarely contain.

    Someone asks "can my client in Lakewood pay to stay?", not "Chapter 516".
    The connector weights hint matches heavily, so the city name and the topic
    vocabulary belong here rather than being left to chance in the text.
    """
    topic = topics.get(target["topic"], {})
    hints = [
        municipality["name"],
        f"{municipality['name']} ordinance",
        f"{municipality['name']} {target['topic'].replace('-', ' ')}",
        target["topic"].replace("-", " "),
        str(topic.get("label", "")),
        municipality.get("county", "") and f"{municipality['county']} County",
        "local ordinance",
        "municipal code",
    ]
    hints.extend(str(value) for value in target.get("retrieval_hints", []) or [])
    return [hint for hint in dict.fromkeys(hints) if hint]


def recheck_after(text_basis):
    """The date this record should be looked at again."""
    days = RECHECK_DAYS.get(text_basis, 180)
    return (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()


def later_amendment_date(history, enacted_date):
    """The newest act in the chain that postdates the one being ingested.

    The chapter search finds the whole chain, including the acts this one
    replaced.  An older act is history, not an amendment, and recording it as
    ``amended_date`` would date the record backwards.
    """
    later = [item["passed_date"] for item in history if item.get("passed_date", "") > (enacted_date or "")]
    return max(later, default="")


def build_record(municipality, target, acquired, topics):
    """One target's ingested text plus everything needed to judge it."""
    text = acquired["text"]
    preemption = dict(target.get("preemption") or {})
    preemption.setdefault("status", "unadjudicated")
    preemption.setdefault(
        "note",
        "R.C. 5321.19 bars local regulation of landlord/tenant rights already "
        "regulated by R.C. Chapter 5321 while preserving local housing, "
        "building, health, and safety codes. Whether this provision is "
        "preempted has not been recorded here.",
    )
    preemption.setdefault("controlling_case", "")
    preemption.setdefault("court_treatment", "")
    preemption.setdefault("confidence", "unreviewed")
    return {
        "key": target["key"],
        "municipality": municipality["slug"],
        "municipality_name": municipality["name"],
        "county": municipality.get("county", ""),
        "topic": target["topic"],
        "topic_label": str(topics.get(target["topic"], {}).get("label", "")),
        "priority": target.get("priority"),
        "citation": target["citation"],
        # Where a provision was first enacted can differ from where it lives
        # now: South Euclid's source-of-income protection arrived as Chapter 552
        # and was later reorganized into Chapter 1408.  A reader chasing the
        # enacting act needs the number it was passed under.
        "enacted_as": str(target.get("enacted_as", "")),
        "title": target["label"],
        "chapter": str(target.get("chapter") or ""),
        "section": str(target.get("section") or ""),
        "code_path": [str(part) for part in target.get("code_path", [])],
        "status": "ingested",
        # Provenance
        "acquisition_method": acquired["acquisition_method"],
        "text_basis": acquired["text_basis"],
        "text_source": acquired.get("text_source", ""),
        "publisher": acquired.get("publisher", ""),
        "source_url": acquired.get("source_url", ""),
        "codifier_url": target.get("codifier_url", municipality.get("codifier_url", "")),
        "codifier": municipality.get("codifier", ""),
        # What kind of document the text came out of.  The Akron 5%/8%
        # discrepancy is the argument for this field: a secondary reproduction
        # and the current code disagreed, and without knowing which is which
        # there is no way to say which one to believe.
        "source_type": str(target.get("source_type", "")),
        "extraction": acquired.get("extraction", {}),
        "ocr": acquired.get("ocr", {}),
        "browser": acquired.get("browser", {}),
        "retrieved_at": now(),
        "recheck_after": recheck_after(acquired["text_basis"]),
        "provided_by": acquired.get("provided_by", ""),
        "provided_on": acquired.get("provided_on", ""),
        "asserted_source": acquired.get("asserted_source", ""),
        "verified": False,
        "raw_sha256": acquired.get("raw_sha256", ""),
        "normalized_text_sha256": sha256(text),
        # Temporal applicability
        "act_file_number": acquired.get("act_file_number", "") or str(target.get("act_file_number", "")),
        "act_title": acquired.get("act_title", ""),
        "act_status": acquired.get("act_status", ""),
        "introduced_date": acquired.get("introduced_date", ""),
        "enacted_date": acquired.get("enacted_date", "") or str(target.get("enacted_date", "")),
        "effective_date": target.get("effective_date", ""),
        "amended_date": later_amendment_date(
            acquired.get("amendment_history", []), acquired.get("enacted_date", ""),
        ),
        "repeal_date": target.get("repeal_date", ""),
        "amendment_history": acquired.get("amendment_history", []),
        # Judgment a reader must make, surfaced rather than answered
        "preemption": preemption,
        "notes": " ".join(str(target.get("notes", "")).split()),
        # Cross references
        "related_statutes": [str(value) for value in target.get("related_statutes", [])],
        "treatise_chunks": [str(value) for value in target.get("treatise_chunks", [])],
        "related_cases": [str(value) for value in target.get("related_cases", [])],
        "verification_urls": [str(value) for value in target.get("verification_urls", [])],
        "retrieval_hints": retrieval_hints(municipality, target, topics),
        "record_path": f"sections/{target['key']}.md",
        "text": text,
    }


def not_in_force_record(municipality, target, topics, acquire):
    """An authority that once existed and does not now.

    This is a finding, not a gap.  The corpus can say plainly that no such
    protection is in force here, which is what someone asking about the city
    actually needs, and it does so without holding the repealed text.
    """
    record = build_record(municipality, target, {
        "text": "",
        "acquisition_method": NOT_IN_FORCE,
        "text_basis": "no_current_provision",
        "publisher": "",
        "source_url": "",
        "amendment_history": [],
    }, topics)
    record.update({
        "status": "no_current_provision",
        "not_in_force_reason": " ".join(str(acquire.get("reason", "")).split()),
        "repeal_date": str(acquire.get("repeal_date", "") or target.get("repeal_date", "")),
        "repealed_by": str(acquire.get("repealed_by", "")),
        "normalized_text_sha256": "",
        "record_path": "",
        "text": "",
    })
    return record


def pending_record(municipality, target, topics, acquire):
    record = build_record(municipality, target, {
        "text": "",
        "acquisition_method": "pending",
        "text_basis": "not_acquired",
        "publisher": "",
        "source_url": "",
        "amendment_history": [],
    }, topics)
    record.update({
        "status": "pending",
        "pending_reason": " ".join(str(acquire.get("reason", "")).split()),
        "normalized_text_sha256": "",
        "record_path": "",
        "text": "",
    })
    return record


def write_record(record, *, municipality_dir, dry_run):
    """Write the section file and its chunks; return the manifest chunk list."""
    text = record["text"]
    chunks = chunk_text(text)
    front_matter = {key: value for key, value in record.items() if key not in {"text", "code_path"}}
    front_matter["code_path"] = record["code_path"]
    heading = f"# {record['citation']} — {record['title']}"
    inventory = []
    for part, body in enumerate(chunks, start=1):
        identifier = f"ord-{record['municipality']}-{record['key']}-{part:02d}"
        filename = f"{identifier}.md"
        chunk_front = {
            **front_matter,
            "chunk_id": identifier,
            "chunk_part": part,
            "chunk_parts_in_section": len(chunks),
            "content_kind": "ordinance-section",
            "jurisdiction": f"{record['municipality_name']}, Ohio",
        }
        inventory.append({
            "id": identifier,
            "file": f"chunks/{filename}",
            "heading": heading_for_chunk(record, part, len(chunks)),
            "path": record["code_path"] or [record["citation"]],
            "content_kind": "ordinance-section",
            "section": record["section"] or record["chapter"],
            "chapter": record["chapter"],
            "citation": record["citation"],
            "url": record["codifier_url"] or record["source_url"],
            "effective_date": record["effective_date"] or record["enacted_date"],
            "retrieval_hints": record["retrieval_hints"],
            "source_path": "",
            "source_sha256": record["normalized_text_sha256"],
            # Carried onto the chunk entry, not left in the section record
            # alone: retrieval reads chunks, and a result that cannot say what
            # basis its text has is a result a reader cannot weigh.
            "text_basis": record["text_basis"],
            "topic": record["topic"],
            "municipality": record["municipality"],
            "act_file_number": record["act_file_number"],
            "enacted_date": record["enacted_date"],
        })
        if not dry_run:
            (municipality_dir / "chunks" / filename).write_text(
                front(chunk_front) + f"{heading}\n\n## Source text\n\n{body}\n", encoding="utf-8",
            )
    if not dry_run:
        keep = {item["file"].split("/", 1)[1] for item in inventory}
        for path in (municipality_dir / "chunks").glob(f"ord-{record['municipality']}-{record['key']}-*.md"):
            if path.name not in keep:
                path.unlink()
        (municipality_dir / record["record_path"]).write_text(
            front(front_matter) + f"{heading}\n\n{text}\n", encoding="utf-8",
        )
    return inventory


def heading_for_chunk(record, part, total):
    """A chunk heading that says which part of a long chapter a reader has."""
    heading = f"{record['citation']} — {record['title']}"
    return heading if total == 1 else f"{heading} (part {part} of {total})"


# --------------------------------------------------------------------------
# Manifests
# --------------------------------------------------------------------------

def municipality_slug(municipality):
    return f"ordinances-{municipality['slug']}"


def load_existing(path):
    if not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {item["key"]: item for item in payload.get("sections", []) if item.get("key")}


def write_manifest(municipality, records, *, municipality_dir, source, dry_run):
    sections = [
        {key: value for key, value in record.items() if key != "text"}
        for record in sorted(records, key=lambda item: (item.get("priority") or 9, item["key"]))
    ]
    chunks = [chunk for record in sections for chunk in record.get("chunks", [])]
    manifest = {
        "schema_version": 1,
        "document_slug": municipality_slug(municipality),
        "document_title": municipality["document_title"],
        "document_version": "",
        "jurisdiction": f"{municipality['name']}, Ohio",
        "content_kind": "ordinance",
        "municipality": municipality["name"],
        "municipality_slug": municipality["slug"],
        "county": municipality.get("county", ""),
        "code_short_name": municipality.get("code_short_name", municipality["document_title"]),
        "codifier": municipality.get("codifier", ""),
        "courts": municipality.get("courts", []),
        "source_name": source["name"],
        "publisher": municipality.get("code_short_name", municipality["document_title"]),
        "source_base_url": municipality.get("codifier_url", ""),
        "generated_at": now(),
        "generator": GENERATOR,
        "preemption_statute": source.get("preemption_statute", ""),
        "update_note": " ".join(str(source.get("update_note", "")).split()),
        "section_count": len([item for item in sections if item["status"] == "ingested"]),
        "pending_count": len([item for item in sections if item["status"] == "pending"]),
        "not_in_force_count": len([item for item in sections if item["status"] == "no_current_provision"]),
        "chunk_count": len(chunks),
        "retrieval_hints": [municipality["name"], f"{municipality['name']} ordinance", "local ordinance"],
        "sections": sections,
        "chunks": chunks,
    }
    if not dry_run:
        (municipality_dir / "manifest.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8",
        )
    return manifest


# --------------------------------------------------------------------------
# Provenance ledger
# --------------------------------------------------------------------------

LEDGER_PATH = LIBRARY / "provenance.yaml"

LEDGER_FIELDS = [
    "municipality_name", "key", "citation", "topic", "status", "acquisition_method",
    "text_basis", "verified", "source_url", "codifier_url", "act_file_number",
    "enacted_as", "enacted_date", "amended_date", "retrieved_at", "recheck_after",
    "source_type", "extraction", "ocr", "browser", "not_in_force_reason", "repealed_by",
    "normalized_text_sha256", "raw_sha256", "provided_by", "provided_on",
    "asserted_source", "pending_reason", "verification_urls",
]


def write_provenance_ledger(*, dry_run):
    """One flat table of where every authority came from and when.

    The per-record front matter already carries provenance, but it is spread
    across ninety files, which is the wrong shape for the question actually
    asked later: what is stale, what was never verified, and what still has no
    text.  This is that question's shape -- one row per authority, sorted, with
    the recheck date computed at ingestion so a refresh can be planned without
    re-reading the corpus.
    """
    rows = []
    for manifest_path in sorted(LIBRARY.glob("*/manifest.yaml")):
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        for section in manifest.get("sections", []) or []:
            row = {field: section.get(field, "") for field in LEDGER_FIELDS}
            row["municipality_name"] = manifest.get("municipality", "")
            rows.append({key: value for key, value in row.items() if value not in ("", [], None)})
    rows.sort(key=lambda item: (item.get("municipality_name", ""), item.get("key", "")))

    counts = {}
    for row in rows:
        counts[row.get("text_basis", "unknown")] = counts.get(row.get("text_basis", "unknown"), 0) + 1
    ledger = {
        "schema_version": 1,
        "generated_at": now(),
        "generator": GENERATOR,
        "note": (
            "Freshness ledger for the local-law corpus. 'recheck_after' is a review "
            "cadence, not an expiry date: a codified chapter can change the day after "
            "it is read. 'verified' means a person confirmed the text against the "
            "publisher; nothing here sets it true."
        ),
        "authority_count": len(rows),
        "by_text_basis": dict(sorted(counts.items())),
        "authorities": rows,
    }
    if not dry_run:
        LEDGER_PATH.write_text(yaml.safe_dump(ledger, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"authorities": len(rows), "by_text_basis": ledger["by_text_basis"]}


# --------------------------------------------------------------------------
# Selection and entry point
# --------------------------------------------------------------------------

def select(scope, args):
    municipalities = scope.get("municipalities", [])
    if args.municipality:
        municipalities = [item for item in municipalities if item["slug"] == args.municipality]
        if not municipalities:
            raise ValueError(f"{args.municipality} is not configured in {SCOPE_PATH}")
    selected = []
    for municipality in municipalities:
        targets = municipality.get("targets", [])
        if args.topic:
            targets = [target for target in targets if target["topic"] == args.topic]
        if args.priority:
            targets = [target for target in targets if str(target.get("priority")) == args.priority]
        if args.target:
            targets = [target for target in targets if target["key"] == args.target]
        if targets:
            selected.append((municipality, targets))
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true", help="Refresh every configured target.")
    selection.add_argument("--municipality", help="One municipality slug, e.g. toledo")
    selection.add_argument("--topic", help="One topic, e.g. pay-to-stay")
    selection.add_argument("--priority", choices=["1", "2", "3"])
    parser.add_argument("--target", help="One target key within the selection, e.g. pay-to-stay")
    parser.add_argument("--force", action="store_true", help="Rewrite records whose normalized text has not changed.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pause", type=float, default=1.0, help="Seconds between remote requests.")
    args = parser.parse_args()

    scope = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8")) or {}
    source = scope.get("source", {})
    source.setdefault("preemption_statute", scope.get("preemption_statute", ""))
    topics = scope.get("topics", {})
    session = requests.Session()

    report = {"ingested": [], "unchanged": [], "pending": [], "failures": [], "dry_run": args.dry_run}
    for municipality, targets in select(scope, args):
        municipality_dir = LIBRARY / municipality["slug"]
        if not args.dry_run:
            (municipality_dir / "chunks").mkdir(parents=True, exist_ok=True)
            (municipality_dir / "sections").mkdir(parents=True, exist_ok=True)
        prior = load_existing(municipality_dir / "manifest.yaml")
        records = dict(prior)

        for target in targets:
            acquire = target.get("acquire") or {"method": "pending", "reason": "No acquisition route configured."}
            method = acquire.get("method", "pending")
            label = f"{municipality['slug']}/{target['key']}"
            if method == NOT_IN_FORCE:
                records[target["key"]] = {
                    **not_in_force_record(municipality, target, topics, acquire), "chunks": [],
                }
                report.setdefault("not_in_force", []).append({
                    "target": label,
                    "repealed": records[target["key"]]["repeal_date"],
                })
                continue
            if method == "pending":
                records[target["key"]] = {**pending_record(municipality, target, topics, acquire), "chunks": []}
                report["pending"].append({"target": label, "reason": records[target["key"]]["pending_reason"]})
                continue
            acquirer = ACQUIRERS.get(method)
            if acquirer is None:
                report["failures"].append({"target": label, "error": f"Unknown acquisition method {method!r}"})
                continue
            try:
                acquired = acquirer(session, municipality, acquire)
                record = build_record(municipality, target, acquired, topics)
            except (AcquisitionError, requests.RequestException, ValueError, KeyError) as exc:
                report["failures"].append({"target": label, "error": str(exc)})
                continue
            finally:
                time.sleep(max(args.pause, 0))

            existing = prior.get(target["key"], {})
            if not args.force and existing.get("normalized_text_sha256") == record["normalized_text_sha256"]:
                # Keep the earlier retrieval stamp: nothing was republished, so
                # claiming a fresh read would overstate what is known.
                records[target["key"]] = existing
                report["unchanged"].append(label)
                continue
            record["chunks"] = write_record(record, municipality_dir=municipality_dir, dry_run=args.dry_run)
            records[target["key"]] = {key: value for key, value in record.items() if key != "text"}
            report["ingested"].append({
                "target": label,
                "act": record["act_file_number"],
                "enacted": record["enacted_date"],
                "chunks": len(record["chunks"]),
                "text_source": record["text_source"],
                "amendments_found": len(record["amendment_history"]),
            })

        # A complete refresh is authoritative for the scope it declares.  A key
        # renamed or removed in scope.yaml would otherwise survive in the
        # manifest as a section nothing maintains any more.
        if args.all:
            configured = {target["key"] for target in municipality.get("targets", [])}
            for key in [key for key in records if key not in configured]:
                retired = records.pop(key)
                if not args.dry_run:
                    for chunk in retired.get("chunks", []):
                        chunk_path = municipality_dir / chunk.get("file", "")
                        if chunk_path.is_file():
                            chunk_path.unlink()
                    record_path = municipality_dir / (retired.get("record_path") or "")
                    if retired.get("record_path") and record_path.is_file():
                        record_path.unlink()
                report.setdefault("retired", []).append(f"{municipality['slug']}/{key}")

        manifest = write_manifest(
            municipality, list(records.values()),
            municipality_dir=municipality_dir, source=source, dry_run=args.dry_run,
        )
        report.setdefault("manifests", []).append({
            "slug": manifest["document_slug"],
            "sections": manifest["section_count"],
            "pending": manifest["pending_count"],
            "chunks": manifest["chunk_count"],
        })

    # The ledger is rebuilt from every manifest, not only the ones touched, so a
    # single-municipality refresh never leaves a partial view of the corpus.
    report["ledger"] = write_provenance_ledger(dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

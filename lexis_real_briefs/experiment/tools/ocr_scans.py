"""OCR the scanned filings in the Lexis delivery with Azure Document Intelligence.

Roughly half of what Lexis delivered is an image with no text layer. Nine of
those are trial-level filings whose .docx wrapper is only a metadata card, so
without OCR the trial stratum of the study is empty; the rest are scans of
briefs we already have as text, but those scans often run far longer than the
Lexis transcription, which means they may carry an appendix or exhibits the
transcription dropped -- the closest thing this corpus has to a case record.

Contract (verified against the resource before this was written, not assumed):

    POST {endpoint}/documentintelligence/documentModels/prebuilt-read:analyze
         ?api-version=2024-11-30
         Ocp-Apim-Subscription-Key: <key>
         Content-Type: application/pdf
         <binary>
    -> 202 with an Operation-Location header
    GET  {Operation-Location}
    -> {"status": "succeeded", "analyzeResult": {"content", "paragraphs", "pages"}}

Results are cached under ocr/ by the *source* SHA-256, so re-running costs
nothing and a changed source cannot silently reuse an old transcription.
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "lexis_real_briefs"
OUT = CORPUS / "experiment"
OCR_DIR = OUT / "ocr"

ENDPOINT = os.environ.get(
    "AZURE_DI_ENDPOINT", "https://workflowdocs.cognitiveservices.azure.com"
).rstrip("/")
API_VERSION = "2024-11-30"
MODEL = "prebuilt-read"
# Recorded with every transcription so a later reader knows what produced it.
OCR_ENGINE = {
    "service": "Azure AI Document Intelligence",
    "model": MODEL,
    "api_version": API_VERSION,
    "endpoint_host": ENDPOINT.split("//")[-1],
}


def key():
    if value := os.environ.get("AZURE_DI_KEY"):
        return value.strip()
    path = Path(os.environ.get("AZURE_DI_KEY_FILE", ""))
    if path and path.is_file():
        return path.read_text().strip()
    raise SystemExit("Set AZURE_DI_KEY or AZURE_DI_KEY_FILE.")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _request(url, *, data=None, method="GET", headers=None):
    request = urllib.request.Request(url, data=data, method=method)
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.status, dict(response.headers), response.read()


def analyze(path, api_key, *, attempts=5):
    """Submit one PDF and poll until the operation finishes."""
    body = Path(path).read_bytes()
    location = None
    for attempt in range(attempts):
        try:
            status, headers, payload = _request(
                f"{ENDPOINT}/documentintelligence/documentModels/{MODEL}:analyze"
                f"?api-version={API_VERSION}",
                data=body,
                method="POST",
                headers={"Ocp-Apim-Subscription-Key": api_key,
                         "Content-Type": "application/pdf"},
            )
            location = headers.get("Operation-Location") or headers.get("operation-location")
            if not location:
                raise RuntimeError(f"no Operation-Location (HTTP {status}): {payload[:200]!r}")
            break
        except urllib.error.HTTPError as error:
            # 429 is the S0 concurrency limit, not a bad request. Back off.
            if error.code not in (429, 503) or attempt == attempts - 1:
                raise RuntimeError(f"submit failed {error.code}: {error.read()[:300]!r}") from error
            time.sleep(2 ** attempt * 3)

    deadline = time.time() + 900
    while time.time() < deadline:
        _, _, payload = _request(location, headers={"Ocp-Apim-Subscription-Key": api_key})
        result = json.loads(payload)
        state = result.get("status")
        if state == "succeeded":
            return result
        if state == "failed":
            raise RuntimeError(f"analysis failed: {json.dumps(result.get('error'))[:300]}")
        time.sleep(3)
    raise RuntimeError("analysis timed out after 15 minutes")


def to_pages(analyze_result):
    """Rebuild page-delimited text from paragraphs, keeping page boundaries.

    Document Intelligence returns `content` as one flat string and `paragraphs`
    with bounding regions. Paragraphs preserve reading order and give a page
    number, which the study's normalization step needs: the plan requires page
    boundaries to survive, and a flat blob loses them.
    """
    pages = {}
    for paragraph in analyze_result.get("paragraphs", []):
        regions = paragraph.get("boundingRegions") or [{}]
        number = regions[0].get("pageNumber", 1)
        pages.setdefault(number, []).append(paragraph.get("content", ""))
    if not pages:  # no paragraphs: fall back to lines
        for page in analyze_result.get("pages", []):
            pages[page["pageNumber"]] = [line.get("content", "") for line in page.get("lines", [])]
    return [{"page": number, "text": "\n".join(pages[number])} for number in sorted(pages)]


def process(path, api_key, *, force=False):
    digest = sha256_file(path)
    cache = OCR_DIR / f"{digest}.json"
    if cache.exists() and not force:
        return json.loads(cache.read_text()), True

    started = time.time()
    result = analyze(path, api_key)
    analyze_result = result["analyzeResult"]
    pages = to_pages(analyze_result)
    record = {
        "source_file": Path(path).name,
        "source_sha256": digest,
        "source_bytes": Path(path).stat().st_size,
        "engine": OCR_ENGINE | {"reported_api_version": analyze_result.get("apiVersion"),
                                "reported_model": analyze_result.get("modelId")},
        "transcribed_on": time.strftime("%Y-%m-%d"),
        "page_count": len(analyze_result.get("pages", [])),
        "char_count": len(analyze_result.get("content", "")),
        "seconds": round(time.time() - started, 1),
        "pages": pages,
    }
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(record, indent=1) + "\n")
    return record, False


def targets(only_pdf_only_wrappers):
    inventory = json.loads((OUT / "inventory.json").read_text())
    chosen = []
    for record in inventory:
        if only_pdf_only_wrappers and not record["pdf_only_wrapper"]:
            continue
        for attachment in record["attachments"]:
            if attachment["text_layer"]:
                continue  # already has real text; OCR would add nothing
            chosen.append({
                "path": CORPUS / attachment["file"],
                "pages": attachment["pages"],
                "case_name": record["case_name"],
                "wrapper_file": record["wrapper_file"],
                "pdf_only_wrapper": record["pdf_only_wrapper"],
            })
    return sorted(chosen, key=lambda t: t["pages"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-only-wrappers", action="store_true",
                        help="only the filings whose .docx is a metadata card")
    parser.add_argument("--workers", type=int, default=3,
                        help="concurrent analyses; S0 throttles above a few")
    parser.add_argument("--force", action="store_true", help="ignore the cache")
    args = parser.parse_args()

    api_key = key()
    work = targets(args.pdf_only_wrappers)
    print(f"{len(work)} scans, {sum(t['pages'] for t in work)} pages")

    done, failed, cached = [], [], 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, t["path"], api_key, force=args.force): t for t in work}
        for future in concurrent.futures.as_completed(futures):
            target = futures[future]
            try:
                record, was_cached = future.result()
            except Exception as error:  # noqa: BLE001 - report and continue
                failed.append((target, str(error)))
                print(f"  FAIL {target['path'].name[:52]:<52} {error}"[:150])
                continue
            cached += was_cached
            done.append((target, record))
            tag = "cached" if was_cached else f"{record['seconds']:>5.1f}s"
            print(f"  ok   {target['path'].name[:52]:<52} {record['page_count']:>4}p "
                  f"{record['char_count']:>7}c {tag}")

    index = [{
        "source_file": target["path"].name,
        "source_sha256": record["source_sha256"],
        "wrapper_file": target["wrapper_file"],
        "case_name": target["case_name"],
        "pdf_only_wrapper": target["pdf_only_wrapper"],
        "pages": record["page_count"],
        "chars": record["char_count"],
        "cache": f"ocr/{record['source_sha256']}.json",
    } for target, record in sorted(done, key=lambda pair: pair[0]["path"].name)]
    (OUT / "ocr_index.json").write_text(json.dumps(index, indent=2) + "\n")

    print(f"\n{len(done)} succeeded ({cached} from cache), {len(failed)} failed")
    print(f"characters recovered: {sum(r['char_count'] for _, r in done):,}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

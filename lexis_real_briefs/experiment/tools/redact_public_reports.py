"""Strip corpus text from `report.public.json` files that were written without it.

`export_public.py` is the right place to redact, and it now does. This exists
for the files written before it did: 1.1 MB of verbatim treatise text reached
the public repository inside `challenges[].legal_sources[].snippet`, under a
`public_export` note claiming the corpus had been removed.

Regenerating them is not an option for most: the `report.json` they came from
is gitignored, and many of those runs are months old on machines that no longer
hold them. So this rewrites the public file in place, applying exactly the
redaction `export_public.py` now applies, and leaves every other byte alone.

The same function is what rewrites the files in git history, so the scrubbed
history and a fresh export agree.

    python tools/redact_public_reports.py --check      # report, change nothing
    python tools/redact_public_reports.py
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_public import strip_source_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "lexis_real_briefs" / "experiment" / "results"

NOTE = (
    "verbatim excerpts of third-party legal corpora, whether the research stage "
    "retrieved them into `retrieval` or the authority check quoted them into a "
    "source's `snippet`; not ours to redistribute and not evidence for any "
    "reported figure. Each source keeps its title, citation, url and provider, so "
    "the authority can still be looked up."
)


def redact_bytes(raw):
    """Redact one file's bytes. Returns ``(new_bytes, characters_removed)``.

    Left byte-identical when there is nothing to remove, so a rewrite touches
    only the files that actually carried corpus text.
    """
    try:
        report = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return raw, 0
    if not isinstance(report, dict):
        return raw, 0
    removed = strip_source_text(report)
    if not removed:
        return raw, 0
    export = report.get("public_export")
    if isinstance(export, dict):
        fields = list(export.get("removed_fields") or [])
        marker = "snippet (on every retrieved source)"
        if marker not in fields:
            fields.append(marker)
        export["removed_fields"] = fields
        export["why"] = NOTE
        # Said plainly rather than quietly corrected: a reader comparing this
        # file to an older clone of it is entitled to know why they differ.
        export["redacted_after_publication"] = (
            "This file was published with the source snippets still in it. They were "
            "removed afterwards by tools/redact_public_reports.py; nothing else changed."
        )
    return json.dumps(report, indent=2, default=str).encode("utf-8"), removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default=str(RESULTS))
    parser.add_argument("--check", action="store_true", help="Report and write nothing.")
    args = parser.parse_args()

    touched = clean = total = 0
    for path in sorted(Path(args.results).glob("**/report.public.json")):
        raw = path.read_bytes()
        new, removed = redact_bytes(raw)
        if not removed:
            clean += 1
            continue
        touched += 1
        total += removed
        print(f"  {removed:>9,} chars  {path.relative_to(args.results)}")
        if not args.check:
            path.write_bytes(new)
    verb = "would remove" if args.check else "removed"
    print(f"\n{touched} file(s) carried source text, {clean} already clean.")
    print(f"{verb} {total:,} characters ({total / 1e6:.2f} MB).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

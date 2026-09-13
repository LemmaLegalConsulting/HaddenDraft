"""Answer "are the pair identical apart from the intended change?" mechanically.

This was one of four questions put to a human reviewer and it should not have
been: a diff answers it, and spending a lawyer's attention on it wastes the
scarcest resource in the study.

What is reported is measured, not inferred:

  edit regions     changed spans, clustering character-level opcodes that sit
                   within 200 characters of each other. Character diffing
                   fragments one rewritten sentence into a dozen opcodes; a
                   genuine second edit elsewhere in a 15,000-character brief is
                   nowhere near its neighbour.
  span             where the change sits, and how wide
  removed heading  whether the deleted text opened with a section label, which
                   is a fact about the excerpt and the one thing a diff alone
                   does not put in front of you

An earlier version of this file also tried to detect orphaned section letters
and cross-references dangling into deleted text. It produced three false
positives and one false negative on eight fixtures: these filings embed
deposition transcripts whose "Q." and "A." lines are indistinguishable from
section labels by pattern, and "Exhibits B and C" reads as a reference to a
deleted section B. A detector that wrong is worse than no detector, so those
checks are gone. The structural consequence it was meant to catch -- F008's
headings running A, C after its section B was deleted -- is recorded by hand in
REGISTER.md and in the fixture's own `note_on_size`, where a reader will see it.
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "lexis_real_briefs" / "experiment" / "fixtures"

# Far enough apart that two changes cannot be one rewritten passage.
CLUSTER_GAP = 200
_OPENS_WITH_LABEL = re.compile(r"^\s*((?:[IVX]{1,5}|[A-Z]|\d{1,2})\.)\s+\S")


def edit_regions(control, mutant):
    matcher = difflib.SequenceMatcher(None, control, mutant, autojunk=False)
    changes = [op for op in matcher.get_opcodes() if op[0] != "equal"]
    regions = []
    for tag, i1, i2, j1, j2 in changes:
        if regions and i1 - regions[-1][1] <= CLUSTER_GAP:
            regions[-1][1] = i2
        else:
            regions.append([i1, i2])
    return regions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out")
    args = parser.parse_args()

    rows = []
    for home in sorted(FIXTURES.iterdir()):
        if not home.is_dir():
            continue
        manifest = json.loads((home / "fixture.json").read_text())
        control = (home / "normalized" / "brief.txt").read_text()
        mutant = (home / "mutant" / "brief.txt").read_text()
        mutation = manifest["mutation"]
        removed = mutation["target_location"]["control_excerpt"]

        regions = edit_regions(control, mutant)
        label = _OPENS_WITH_LABEL.match(removed)
        rows.append({
            "fixture_id": manifest["fixture_id"],
            "edit_regions": len(regions),
            "span_chars": (regions[0][1] - regions[0][0]) if len(regions) == 1 else None,
            "brief_chars": len(control),
            "one_edit_and_nothing_else": len(regions) == 1,
            "removed_text_opened_with_section_label": label.group(1) if label else None,
            "author_caveat": mutation.get("note_on_size", "").strip() or None,
        })

    print(f"{'fixture':<9} {'regions':>8} {'span':>7} {'of':>7}  one edit and nothing else?")
    for row in rows:
        mark = "yes" if row["one_edit_and_nothing_else"] else "NO"
        extra = ""
        if row["removed_text_opened_with_section_label"]:
            extra = f"   deleted text began '{row['removed_text_opened_with_section_label']}'"
        print(f"{row['fixture_id']:<9} {row['edit_regions']:>8} "
              f"{str(row['span_chars'] or '-'):>7} {row['brief_chars']:>7}  {mark}{extra}")
    clean = sum(1 for r in rows if r["one_edit_and_nothing_else"])
    print(f"\n{clean} of {len(rows)} pairs differ in exactly one contiguous place.")
    flagged = [r for r in rows if r["removed_text_opened_with_section_label"]]
    if flagged:
        print("\nDeleting a labelled section leaves its siblings renumbered in the reader's "
              "eye.\nWorth a glance, on:")
        for row in flagged:
            print(f"  {row['fixture_id']}: removed a section opening '"
                  f"{row['removed_text_opened_with_section_label']}'"
                  + (f"\n     author's caveat: {row['author_caveat'][:150]}" if row["author_caveat"] else ""))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, indent=2) + "\n")
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

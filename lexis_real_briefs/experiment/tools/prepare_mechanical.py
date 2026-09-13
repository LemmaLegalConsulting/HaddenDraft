"""Lay out the mechanical tier for a human to edit.

The subtle tier's instantiation -- which passage, what replacement -- was chosen
by a model, and that is the one part of the study with no outside check. This
tier removes the model from instantiation entirely: the briefs are assigned here
by structure, and a person picks the passage and writes the edit.

For each fixture this writes a directory holding

    control.txt   the unmodified filing. Never edit this.
    mutant.txt    an identical copy. Edit this one.
    flaw.yaml     the assigned defect type, and one blank line for what you did.
    WHERE.md      where in the brief the relevant material sits, so the editor
                  is not hunting -- locations only, never a suggested edit.

Nothing here proposes the change. Pointing at the paragraph is orientation;
choosing the sentence and writing the replacement is the point of the exercise.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "lexis_real_briefs" / "experiment"
PREVIEW = EXPERIMENT / "normalized_preview"
OUT = EXPERIMENT / "mechanical"

# Assigned by structure: each brief already contains the raw material the flaw
# needs, so the edit is a change to what is there rather than an insertion.
PLAN = [
    {
        "id": "M01", "type": "relief_scope", "stem": "BRIEF OF APPELLEE WWSD",
        "case": "WWSD v. Woods", "court": "Ohio App. 10th Dist.",
        "covered_by": "the Gym advertises a 'remedy_scope' challenge category",
        "defect": "Make the relief asked for reach further than the argument supports.",
        "where": [("the prayer", r"WHEREFORE, Appellee respectfully requests")],
    },
    {
        "id": "M02", "type": "relief_scope", "stem": "Answer Brief Of Appellee Land Title",
        "case": "Sheridan v. Sheridan", "court": "Ohio App. 8th Dist.",
        "covered_by": "the Gym advertises a 'remedy_scope' challenge category",
        "defect": "Make the relief asked for reach further than the argument supports.",
        "where": [("the prayer", r"respectfully (requests|submits)")],
    },
    {
        "id": "M03", "type": "party_role", "stem": "Appellee's Answer Brief",
        "case": "Anderson v. Mitchell", "court": "Ohio App. 8th Dist.",
        "covered_by": "nothing; no rule or category looks for this",
        "defect": "Reverse the party's own role in one sentence, so an appellee "
                  "asks for the relief an appellant would want.",
        "where": [("the conclusion", r"respectfully requests this court affirm")],
    },
    {
        "id": "M04", "type": "enumeration", "stem": "LENDER SALONE'S MEMORANDUM IN RESPONSE",
        "case": "Salone v. Stovall", "court": "Ohio Supreme Court",
        "covered_by": "nothing; no rule or category looks for this",
        "defect": "Promise a number of reasons and deliver fewer.",
        "where": [("the promise", r"at least four reasons"), ("the list", r"\bFirst,")],
    },
    {
        "id": "M05", "type": "date_contradiction", "stem": "BRIEF OF DEFENDANT_APPELLEE WESTPORT",
        "case": "Press v. Westport Ins.", "court": "Ohio App.",
        "covered_by": "nothing; record_audit compares brief to record, not brief to itself",
        "defect": "Make a date in one part of the brief contradict the same date elsewhere.",
        "where": [("facts", r"accident on July 15, 2002"), ("argument", r"date of loss of July 15, 2002")],
    },
    {
        "id": "M06", "type": "arithmetic", "stem": "Brief of Plaintiff-Appellants",
        "case": "Solomon v. Harwood", "court": "Ohio App. 8th Dist.",
        "covered_by": "nothing; no rule or category looks for this",
        "defect": "Make itemised figures fail to add up to the total the brief states, "
                  "or state a total the items contradict.",
        "where": [("the damages award", r"compensatory damages of \$")],
    },
    # M07-M09 raise relief_scope to five. It is the only class where a miss is a
    # failure on the Gym's own terms, and at n=2 the best attainable result was
    # p=0.25 -- an unreachable bar for the study's sharpest claim. Postures vary
    # deliberately: one appellant seeking reversal, two appellees seeking
    # affirmance, so the defect is not always the same shape.
    {
        "id": "M07", "type": "relief_scope", "stem": "CORRECTED BRIEF OF APPELLANT",
        "case": "Carano v. Schottenstein", "court": "Ohio App. 10th Dist. (appellant)",
        "covered_by": "the Gym advertises a 'remedy_scope' challenge category",
        "defect": "Make the relief asked for reach further than the argument supports.",
        "where": [("the prayer", r"respectfully request that the Tenth District")],
    },
    {
        "id": "M08", "type": "relief_scope", "stem": "BRIEF OF APPELLEE.txt",
        "case": "Williams v. Deutsche Bank", "court": "Ohio App. 8th Dist. (appellee)",
        "covered_by": "the Gym advertises a 'remedy_scope' challenge category",
        "defect": "Make the relief asked for reach further than the argument supports.",
        "where": [("the prayer", r"respectfully requests that this Honorable Court affirm")],
    },
    {
        "id": "M09", "type": "relief_scope", "stem": "DEFENDANT-APPELLEES' APPELLATE BRIEF",
        "case": "Presser v. RCP Mayfield", "court": "Ohio App. 8th Dist. (appellee)",
        "covered_by": "the Gym advertises a 'remedy_scope' challenge category",
        "defect": "Make the relief asked for reach further than the argument supports.",
        "where": [("the prayer", r"respectfully requests that this court affirm the rulings")],
    },
]


def find(stem):
    if stem.endswith(".txt"):
        exact = PREVIEW / stem
        return exact if exact.exists() else None
    hits = [p for p in PREVIEW.glob("*.txt")
            if p.stem.startswith(stem[:45]) and not p.stem.endswith(".record-01")]
    return hits[0] if hits else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    import re

    index = []
    for item in PLAN:
        source = find(item["stem"])
        if source is None:
            print(f"  {item['id']}: SOURCE NOT FOUND for {item['stem'][:40]}")
            continue
        home = OUT / item["id"]
        if home.exists():
            # Never touch a fixture someone may already have edited.
            print(f"  {item['id']}  exists; left alone")
            index.append({"id": item["id"], "type": item["type"], "case": item["case"],
                          "source": source.name, "chars": len(source.read_text()),
                          "covered_by": item["covered_by"]})
            continue
        home.mkdir()
        text = source.read_text()
        (home / "control.txt").write_text(text)
        (home / "mutant.txt").write_text(text)

        lines = [f"# {item['id']} — {item['case']}", "",
                 f"**Defect to introduce:** {item['defect']}", "",
                 f"**Type:** `{item['type']}`  ", f"**Court:** {item['court']}  ",
                 f"**Length:** {len(text):,} characters  ",
                 f"**Already covered by a Gym rule?** {item['covered_by']}", "",
                 "## Where the relevant material is",
                 "",
                 "Locations only. Which sentence to change, and how, is yours.", ""]
        for label, pattern in item["where"]:
            match = re.search(pattern, text, re.I)
            if not match:
                lines.append(f"- **{label}** — pattern not found; search by hand")
                continue
            start = max(0, match.start() - 120)
            end = min(len(text), match.end() + 260)
            lines += [f"- **{label}**, around character {match.start():,}:", "",
                      "  > " + text[start:end].replace("\n", " ").strip(), ""]
        lines += ["## What to do", "",
                  "1. Edit `mutant.txt` only. Leave `control.txt` untouched.",
                  "2. Change **one thing**. Nothing else — not a typo, not spacing.",
                  "3. The defect must be visible to a careful reader who knows no housing law.",
                  "4. Write one sentence in `flaw.yaml` saying what is now wrong.", ""]
        (home / "WHERE.md").write_text("\n".join(lines))

        (home / "flaw.yaml").write_text(
            f"# {item['id']} — {item['case']}\n"
            f"id: {item['id']}\n"
            f"type: {item['type']}\n"
            f"case: \"{item['case']}\"\n"
            f"court: \"{item['court']}\"\n"
            f"source_file: \"{source.name}\"\n"
            "\n"
            "# One sentence: what is now wrong with mutant.txt, stated so that someone\n"
            "# who has not seen control.txt could check it against the brief alone.\n"
            "defect: \"\"\n"
            "\n"
            "# Optional: anything a reader should know about the edit.\n"
            "note: \"\"\n"
            "\n"
            "# Set to yes when you have finished editing mutant.txt.\n"
            "ready: no\n"
        )
        index.append({"id": item["id"], "type": item["type"], "case": item["case"],
                      "source": source.name, "chars": len(text),
                      "covered_by": item["covered_by"]})
        print(f"  {item['id']}  {item['type']:<20} {item['case'][:28]:<28} {len(text):>7,} chars")

    (OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"\n{len(index)} fixtures laid out in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

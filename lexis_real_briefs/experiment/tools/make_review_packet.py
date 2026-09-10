"""Build the blind reviewer packet -- protocol steps 5 and 6.

The reviewer sees the control, the mutant, the passage that differs, the gold
vulnerability being claimed, and the record. The reviewer does not see any Gym
output, because the question being asked is whether the fixture is sound, not
whether the Gym did well on it. A reviewer who has seen the results cannot
un-see them, and a fixture adjudicated after the fact is not a held-out fixture.

Output, per fixture:

    review/F007/
      00-READ-ME-FIRST.md      the four questions and what to look at
      01-control.txt           the unmodified filing
      02-mutant.txt            the altered filing
      03-the-change.diff       the only difference, in context
      04-the-claim.md          what the mutation is asserted to have done
      05-record/               the attachments, identical in both conditions
    review/ADJUDICATION.yaml   one block per fixture for the reviewer to fill in

Nothing here is derived from a run. Generating it is safe at any time; reading
it after seeing results is not.
"""

import difflib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "lexis_real_briefs" / "experiment"
FIXTURES = OUT / "fixtures"
REVIEW = OUT / "review"

QUESTIONS = [
    ("pair_identical_except_intended_change",
     "Are the control and the mutant identical except for the intended change?",
     "Read 03-the-change.diff. Anything else that differs -- a heading that no "
     "longer follows its neighbour, a renumbered section, a dangling cross-"
     "reference -- is a second change and disqualifies the fixture."),
    ("control_free_of_target_defect",
     "Is the control free of the targeted defect?",
     "If the unmodified filing already has this problem, the mutation did not "
     "introduce it and the pair cannot demonstrate sensitivity."),
    ("mutant_contains_target_defect",
     "Does the mutant actually contain the targeted defect?",
     "Read 04-the-claim.md against the mutant and, where there is one, the "
     "record. The claim has to be true, not just plausible."),
    ("material_enough_to_raise",
     "Is the defect material enough that competent opposing counsel could "
     "reasonably raise it?",
     "Not 'would a machine notice it' -- would a lawyer on the other side use "
     "it. A defect nobody would argue is not a useful test."),
]


def context_diff(control, mutant):
    return "".join(difflib.unified_diff(
        control.splitlines(keepends=True), mutant.splitlines(keepends=True),
        fromfile="control (as filed)", tofile="mutant (one change)", n=3,
    ))


def read_me(manifest):
    mutation, document = manifest["mutation"], manifest["document"]
    record = manifest["files"]["attachments"]
    lines = [
        f"# {manifest['fixture_id']} — reviewer packet",
        "",
        f"**{document['title']}**  ",
        f"{document['court']} · filed {document['filed']} · {document['side']}  ",
        f"Case family `{manifest['case_family_id']}` · stratum `{manifest['stratum']}`",
        "",
        "> You are reviewing the **fixture**, not the Argument Gym. No Gym output",
        "> appears in this packet, and you should not seek any out before you answer.",
        "> If you have already seen results for this fixture, say so on the",
        "> adjudication form instead of answering.",
        "",
        "## What is in front of you",
        "",
        "| File | What it is |",
        "|---|---|",
        "| `01-control.txt` | the filing as filed, normalized but not edited |",
        "| `02-mutant.txt` | the same filing with one change |",
        "| `03-the-change.diff` | that change, in context — read this first |",
        "| `04-the-claim.md` | what the change is asserted to have done, and why |",
    ]
    if record:
        lines.append(f"| `05-record/` | the {len(record)} record document(s) filed with it, "
                     "**byte-identical in both conditions** |")
    lines += [
        "",
        f"The change is **{mutation['characters_changed']} characters** of a "
        f"{mutation['control_chars']}-character filing "
        f"({mutation['fraction_of_brief_changed']:.2%}), in {mutation['section']}.",
        "",
        "## The four questions",
        "",
    ]
    for index, (_, question, guidance) in enumerate(QUESTIONS, start=1):
        lines += [f"**{index}. {question}**", "", f"> {guidance}", ""]
    lines += [
        "Answer all four in `review/ADJUDICATION.yaml`. **Only yes / yes / yes / yes",
        "admits this fixture to the held-out benchmark.** A `no` is not a failure —",
        "it is the packet doing its job, and the fixture moves to the development set.",
        "",
        "## What you are not being asked",
        "",
        "- whether the mutation is the *best* one available in this filing",
        "- whether the control is a good brief",
        "- whether the Gym will catch it",
        "",
        "---",
        "",
        f"*Mutations drafted by a language model (Claude Opus 5) on "
        f"{manifest['provenance']['generator']['authored_on']}; no attorney has reviewed "
        f"them. Control text: {manifest['provenance']['text']['control_text_source']}.*",
    ]
    return "\n".join(lines) + "\n"


def the_claim(manifest):
    mutation = manifest["mutation"]
    location = mutation["target_location"]
    lines = [
        f"# {manifest['fixture_id']} — what the change is asserted to have done",
        "",
        f"**Class:** `{mutation['type']}` / `{mutation['subtype']}`  ",
        f"**Operation:** {mutation['operation']} in {mutation['section']}  ",
        f"**Claimed materiality:** {mutation['materiality']}",
        "",
        "## Before",
        "", "```", location["control_excerpt"].strip(), "```", "",
        "## After",
        "", "```", (location["mutant_excerpt"].strip() or "(deleted)"), "```", "",
        "## The vulnerability this is asserted to create",
        "", mutation["gold_vulnerability"].strip(), "",
        "## Why this was thought realistic",
        "", mutation["why_this_is_realistic"].strip(), "",
        "## What the change was intended to leave alone",
        "", mutation["description"].strip(), "",
    ]
    if mutation.get("note_on_size"):
        lines += ["## A caution the author flagged", "", mutation["note_on_size"].strip(), ""]
    if manifest["files"]["attachments"]:
        lines += ["## The record", ""]
        for note in manifest["files"]["attachment_notes"]:
            lines.append(f"- `{note['file']}` — {note['note']} ({note['chars']:,} characters)")
        lines += ["", "The record is identical in both conditions. If the claim above turns on "
                  "what the record does or does not establish, check it there."]
    return "\n".join(lines) + "\n"


def main():
    if REVIEW.exists():
        shutil.rmtree(REVIEW)
    REVIEW.mkdir(parents=True)

    adjudication = ["# Reviewer adjudication — protocol steps 5 and 6.",
                    "#",
                    "# Fill in one block per fixture. Answer yes / no / unsure.",
                    "# Only yes/yes/yes/yes admits a fixture to the held-out benchmark.",
                    "#",
                    "# 'saw_results_first' exists so contamination is recorded rather than",
                    "# hidden. Answering yes there does not waste the fixture; it moves it to",
                    "# the development set, which is where a contaminated fixture belongs.",
                    ""]

    manifests = []
    for home in sorted(FIXTURES.iterdir()):
        if not home.is_dir():
            continue
        manifest = json.loads((home / "fixture.json").read_text())
        manifests.append(manifest)
        control = (home / "normalized" / "brief.txt").read_text()
        mutant = (home / "mutant" / "brief.txt").read_text()

        packet = REVIEW / manifest["fixture_id"]
        packet.mkdir()
        (packet / "00-READ-ME-FIRST.md").write_text(read_me(manifest))
        (packet / "01-control.txt").write_text(control)
        (packet / "02-mutant.txt").write_text(mutant)
        (packet / "03-the-change.diff").write_text(context_diff(control, mutant))
        (packet / "04-the-claim.md").write_text(the_claim(manifest))
        attachments = sorted((home / "normalized" / "attachments").glob("*"))
        if attachments:
            (packet / "05-record").mkdir()
            for attachment in attachments:
                shutil.copy2(attachment, packet / "05-record" / attachment.name)

        mutation = manifest["mutation"]
        adjudication += [
            f"- fixture_id: {manifest['fixture_id']}",
            f"  # {manifest['case_family_id']} — {mutation['type']}, "
            f"{mutation['characters_changed']} chars changed",
            "  reviewer: \"\"                       # your name",
            "  reviewed_on: \"\"                    # YYYY-MM-DD",
            "  saw_results_first: no              # yes | no",
        ]
        for key, question, _ in QUESTIONS:
            adjudication += [f"  # {question}", f"  {key}: \"\"                # yes | no | unsure"]
        adjudication += [
            "  notes: \"\"                          # anything the yes/no does not carry",
            "  # If any answer is no or unsure, say what a better mutation here would be:",
            "  suggested_alternative: \"\"",
            "",
        ]

    (REVIEW / "ADJUDICATION.yaml").write_text("\n".join(adjudication))

    index = ["# Reviewer packets", "",
             "One directory per fixture. Start with `00-READ-ME-FIRST.md` inside each,",
             "record answers in `ADJUDICATION.yaml`.", "",
             "**No Gym output appears anywhere in this directory, by design.**", "",
             "| Fixture | Case | Court | Mutation | Changed | Record |",
             "|---|---|---|---|---|---|"]
    for manifest in manifests:
        mutation = manifest["mutation"]
        index.append(
            f"| `{manifest['fixture_id']}` | {manifest['case_family_id']} "
            f"| {manifest['document']['court']} | {mutation['type']} "
            f"| {mutation['characters_changed']} of {mutation['control_chars']:,} "
            f"({mutation['fraction_of_brief_changed']:.2%}) "
            f"| {'yes' if manifest['files']['attachments'] else '—'} |")
    (REVIEW / "README.md").write_text("\n".join(index) + "\n")

    print(f"wrote {len(manifests)} reviewer packets to {REVIEW}")
    for manifest in manifests:
        n = len(manifest["files"]["attachments"])
        print(f"  {manifest['fixture_id']}  {manifest['mutation']['type']:<24} "
              f"{'record: %d doc' % n if n else 'no record':<14} {manifest['case_family_id'][:34]}")


if __name__ == "__main__":
    main()

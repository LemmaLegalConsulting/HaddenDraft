"""Freeze the hand-edited mechanical tier into fixtures the runner can read.

Same manifest shape as the subtle tier, so run_experiment.py needs only to be
pointed at a different directory. The differences are recorded rather than
smoothed over: these mutants were written by a person, the defect descriptions
are theirs, and the `gold_vulnerability` is their sentence, not a model's.
"""

import difflib
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "lexis_real_briefs" / "experiment"
SOURCE = EXPERIMENT / "mechanical"
OUT = EXPERIMENT / "fixtures-mechanical"

# Which classes the Gym has vocabulary for. This decides what a miss means and
# is carried into every manifest so the two cannot be pooled by accident.
ADVERTISED = {"relief_scope": "remedy_scope is one of the seven challenge "
                              "categories named in the opponent's JSON schema"}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def regions(control, mutant):
    c, m = control.split("\n"), mutant.split("\n")
    return [op for op in difflib.SequenceMatcher(None, c, m, autojunk=False).get_opcodes()
            if op[0] != "equal"]


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    built = []
    for home in sorted(SOURCE.glob("M0*")):
        flaw = yaml.safe_load((home / "flaw.yaml").read_text())
        control = (home / "control.txt").read_text()
        mutant = (home / "mutant.txt").read_text()
        if control == mutant:
            print(f"  {flaw['id']}: control and mutant are identical; skipped")
            continue
        blocks = regions(control, mutant)

        target = OUT / flaw["id"]
        (target / "normalized" / "attachments").mkdir(parents=True)
        (target / "mutant" / "attachments").mkdir(parents=True)
        (target / "normalized" / "brief.txt").write_text(control)
        (target / "mutant" / "brief.txt").write_text(mutant)

        manifest = {
            "fixture_id": flaw["id"],
            "case_family_id": flaw["case"].lower().replace(" ", "-").replace(".", ""),
            "stratum": "mechanical",
            "document": {
                "title": flaw["case"], "court": flaw["court"], "jurisdiction": "Ohio",
                "pleading_type": "appellate_brief", "side": "", "filed": "",
            },
            "files": {"source": f"mechanical/{flaw['id']}/control.txt",
                      "source_scan": None,
                      "control": "normalized/brief.txt", "mutant": "mutant/brief.txt",
                      "attachments": [], "attachment_notes": []},
            "mutation": {
                "type": flaw["type"],
                "subtype": f"hand_authored_{flaw['type']}",
                "operation": "edit",
                "section": "see target_location",
                "target_location": {
                    "section": "", "control_excerpt": "", "mutant_excerpt": "",
                },
                "gold_vulnerability": str(flaw["defect"]).strip(),
                "description": str(flaw["defect"]).strip(),
                "why_this_is_realistic":
                    "A defect a careful reader confirms from the brief alone, with no "
                    "legal knowledge. The mechanical tier is a positive control: it "
                    "establishes whether anything is detected at all.",
                "note_on_size": str(flaw.get("note", "")).strip() or None,
                "expected_direction": "mutant_worse",
                "materiality": "high",
                "edit_regions": len(blocks),
                "characters_changed": abs(len(mutant) - len(control)),
                "control_chars": len(control),
                "mutant_chars": len(mutant),
                "fraction_of_brief_changed": round(
                    abs(len(mutant) - len(control)) / max(1, len(control)), 5),
                "gym_has_vocabulary_for_this": ADVERTISED.get(flaw["type"]),
            },
            "gold": {
                "control_has_target_defect": False,
                "mutant_has_target_defect": True,
                "expected_direction": "mutant_worse",
                "materiality": "high",
                "verified_by": ["researcher (authored by hand)"],
                "verification_status": "authored_by_researcher",
                "verification_note":
                    "Written by the researcher, not by a model. The subtle tier's "
                    "instantiation was model-authored and is what the automated "
                    "matching then scores against; this tier breaks that loop.",
            },
            "provenance": {
                "source_sha256": sha(control),
                "source_scan_sha256": None,
                "control_sha256": sha(control),
                "mutant_sha256": sha(mutant),
                "attachment_sha256": {},
                "normalization_version": "1.0",
                "text": {"control_text_source": "lexis_docx",
                         "source_file": flaw["source_file"],
                         "normalization_log": None, "ocr": None,
                         "scan_split_rule": None},
                "mutation_version": "mechanical-1.0",
                "generator": {
                    "mutations_authored_by": "researcher, by hand",
                    "generator_role": "chose the passage and wrote the edit",
                    "model_involvement": "assigned briefs to defect classes by "
                                         "structure and built scaffolding; did not "
                                         "choose the passage or write the edit",
                    "authored_on": "2026-09-12",
                },
                "built_on": date.today().isoformat(),
            },
        }
        (target / "fixture.json").write_text(json.dumps(manifest, indent=2) + "\n")
        built.append(manifest)
        flag = "advertised" if manifest["mutation"]["gym_has_vocabulary_for_this"] else "no vocabulary"
        print(f"  {flaw['id']}  {flaw['type']:<20} {len(blocks)} region(s)  "
              f"{manifest['mutation']['characters_changed']:>5} chars  {flag}")

    (OUT / "index.json").write_text(json.dumps(
        [{"fixture_id": m["fixture_id"], "type": m["mutation"]["type"],
          "advertised": bool(m["mutation"]["gym_has_vocabulary_for_this"])}
         for m in built], indent=2) + "\n")
    print(f"\n{len(built)} mechanical fixtures frozen in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""SUPERSEDED by blind_adjudication.py. Kept only to read runs already scored with it.

This tool's worksheet groups challenges under a `control:` and a `mutant:`
heading, which tells the adjudicator which condition produced what. That is
exactly the cue the study needs removed: a person deciding, forty times in a
row, whether a challenge "names the registered vulnerability" will hold the
draft they know is flawed to a different standard than the one they know is not.

Use `blind_adjudication.py` instead. It pools challenges per fixture across every
run, strips condition, cell and model, shuffles under a recorded seed, and keeps
the mapping in a separate key file. It computes the same four-cell outcome.

--- original docstring follows ---

Turn raw runs into the registered four-cell paired outcome. Two stages.

    --emit   build an adjudication worksheet: for each fixture, the registered
             gold vulnerability beside every challenge the Gym raised in each
             condition, with a blank for the adjudicator's decision.

    --score  read the completed worksheet and compute the table.

The split is the point. The primary outcome depends on a judgment -- did this
challenge name the registered vulnerability, or merely land near it -- and a
scorer that made that call by keyword would be marking its own homework in a
way no reader could check. So the worksheet carries the evidence and a person
carries the decision.

The matching rule, from REGISTER.md §6: a challenge matches when it names the
underlying proposition in `gold_vulnerability`. Exact category wording is not
required -- the Gym may correctly call a missing element a missing factual
support -- and a challenge that merely notices something is missing without
naming the proposition is not a match.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "lexis_real_briefs" / "experiment"
FIXTURES = EXPERIMENT / "fixtures"

OUTCOMES = {
    (0, 1): ("discriminating", "the mutation caused the finding"),
    (0, 0): ("missed", "the introduced defect was not detected"),
    (1, 1): ("non_discriminating", "already flagged in the unmodified brief, so this "
                                   "pair shows nothing about sensitivity"),
    (1, 0): ("reversed", "the mutation suppressed a finding -- investigate"),
}


def load_runs(directory):
    report = json.loads((Path(directory) / "report.json").read_text())
    runs = {}
    for result in report["results"]:
        runs[(result["fixture_id"], result["condition"])] = result
    return report["manifest"], runs


def challenge_block(result):
    lines = []
    for challenge in result.get("challenges", []):
        target = challenge.get("target") or {}
        lines.append({
            "ordinal": challenge["ordinal"],
            "category": challenge.get("category", ""),
            "severity": challenge.get("severity", ""),
            "confidence": challenge.get("confidence", ""),
            "judge_verdict": challenge.get("judge_verdict", ""),
            "anchored_at": (target.get("excerpt") or "")[:160],
            "opponent_argument": (challenge.get("opponent_argument") or "")[:900],
            "why_it_matters": (challenge.get("why_it_matters") or "")[:400],
        })
    return lines


def emit(directory, out_path):
    manifest, runs = load_runs(directory)
    fixtures = [json.loads((home / "fixture.json").read_text())
                for home in sorted(FIXTURES.iterdir()) if home.is_dir()]

    document = [
        "# Adjudication worksheet — run "
        f"{manifest['created_at'][:19]}, model {manifest['model']} ({manifest['mode']})",
        "#",
        "# For each fixture and each condition, decide whether ANY challenge named the",
        "# registered vulnerability. Set `target_detected` to yes or no, and when yes",
        "# put the challenge's ordinal in `matched_ordinal`.",
        "#",
        "# A match names the underlying proposition. It does not have to use the",
        "# fixture's category word, and it does not count if it merely notices that",
        "# something is missing without saying what.",
        "#",
        "# Leave `adjudicated_by` blank at your peril: the table reports who decided.",
        "",
        f"run_directory: {Path(directory).relative_to(ROOT)}",
        f"model: {manifest['model']}",
        f"mode: {manifest['mode']}",
        "adjudicated_by: \"\"",
        "adjudicated_on: \"\"",
        "",
        "fixtures:",
    ]

    for fixture in fixtures:
        fid = fixture["fixture_id"]
        mutation = fixture["mutation"]
        document += [
            f"  - fixture_id: {fid}",
            f"    # {fixture['case_family_id']} | {mutation['type']} | "
            f"{mutation['characters_changed']} chars changed",
            "    #",
            "    # THE REGISTERED VULNERABILITY (what a match must name):",
        ]
        for line in mutation["gold_vulnerability"].strip().split("\n"):
            document.append(f"    #   {line.strip()}")
        document.append("    #")

        for condition in ("control", "mutant"):
            result = runs.get((fid, condition))
            document.append(f"    {condition}:")
            if result is None or result.get("status") != "complete":
                document += [f"      status: {result.get('status') if result else 'absent'}",
                             "      target_detected: \"\"    # run did not complete",
                             "      matched_ordinal: null", "      note: \"\"", ""]
                continue
            challenges = challenge_block(result)
            document.append(f"      # verdict: {result.get('verdict', '')[:110]}")
            document.append(f"      # {len(challenges)} challenge(s) raised:")
            for item in challenges:
                document.append(
                    f"      #  [{item['ordinal']}] ({item['category']}/"
                    f"{item['severity']}/judge:{item['judge_verdict']}) "
                    f"{item['opponent_argument'][:260].strip()}")
                if item["anchored_at"]:
                    document.append(f"      #       anchored at: {item['anchored_at'][:110].strip()}")
            if not challenges:
                document.append("      #  (none)")
            document += [
                "      target_detected: \"\"      # yes | no",
                "      matched_ordinal:          # the ordinal, when yes",
                "      match_confidence: \"\"     # high | medium | low",
                "      note: \"\"",
                "",
            ]
        document += [
            "    other_challenges_valid: \"\"   # optional: how many of the rest were sound",
            "    notes: \"\"",
            "",
        ]

    Path(out_path).write_text("\n".join(document))
    print(f"wrote adjudication worksheet to {out_path}")
    print(f"  {len(fixtures)} fixtures, {len(runs)} runs, model {manifest['model']}")
    incomplete = [k for k, v in runs.items() if v.get("status") != "complete"]
    if incomplete:
        print(f"  {len(incomplete)} run(s) incomplete: {incomplete}")


def score(worksheet_path, out_path):
    filled = yaml.safe_load(Path(worksheet_path).read_text())
    rows, unanswered = [], []

    for entry in filled["fixtures"]:
        answers = {}
        for condition in ("control", "mutant"):
            value = str((entry.get(condition) or {}).get("target_detected", "")).strip().lower()
            if value not in ("yes", "no"):
                unanswered.append(f"{entry['fixture_id']}/{condition}")
                answers[condition] = None
            else:
                answers[condition] = 1 if value == "yes" else 0
        if None in answers.values():
            continue
        outcome, meaning = OUTCOMES[(answers["control"], answers["mutant"])]
        rows.append({
            "fixture_id": entry["fixture_id"],
            "control": answers["control"],
            "mutant": answers["mutant"],
            "outcome": outcome,
            "meaning": meaning,
            "matched_ordinal_mutant": (entry.get("mutant") or {}).get("matched_ordinal"),
            "match_confidence_mutant": (entry.get("mutant") or {}).get("match_confidence", ""),
        })

    counts = {name: 0 for name, _ in OUTCOMES.values()}
    for row in rows:
        counts[row["outcome"]] += 1

    result = {
        "run_directory": filled.get("run_directory"),
        "model": filled.get("model"),
        "mode": filled.get("mode"),
        "adjudicated_by": filled.get("adjudicated_by") or "(unrecorded)",
        "adjudicated_on": filled.get("adjudicated_on") or "(unrecorded)",
        "scored_fixtures": len(rows),
        "unanswered": unanswered,
        "counts": counts,
        "rows": rows,
        "note": "Counts, not a rate: n is too small for a proportion, and the "
                "non_discriminating cell is not a failure of the Gym.",
    }
    Path(out_path).write_text(json.dumps(result, indent=2) + "\n")

    print(f"{'fixture':<9} {'control':>8} {'mutant':>7}  outcome")
    for row in rows:
        print(f"{row['fixture_id']:<9} {row['control']:>8} {row['mutant']:>7}  {row['outcome']}")
    print()
    for name, count in counts.items():
        print(f"  {name:<20} {count}")
    if unanswered:
        print(f"\n  unanswered: {', '.join(unanswered)}")
    print(f"\nwrote {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--emit", action="store_true")
    group.add_argument("--score", action="store_true")
    parser.add_argument("--worksheet")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    worksheet = Path(args.worksheet) if args.worksheet else run_dir / "ADJUDICATION.yaml"
    if args.emit:
        emit(run_dir, worksheet)
    else:
        score(worksheet, run_dir / "outcome.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

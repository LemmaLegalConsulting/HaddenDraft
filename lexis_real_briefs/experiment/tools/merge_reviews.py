"""Combine the files reviewers send back, and say where they disagree.

Each reviewer works alone and returns one JSON file. This unblinds them against
the key, computes the registered four-cell paired outcome per reviewer, and --
the part that only exists because there is more than one reviewer -- reports
where two of them looked at the same challenge and reached different answers.

Disagreement is a result, not a problem to average away. If reviewers split on
whether a challenge names the planted defect, that fixture's gold label is
ambiguous, and the protocol's admission rule should probably keep it out of the
held-out set regardless of what the Gym did.
"""

import argparse
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "lexis_real_briefs" / "experiment"

OUTCOMES = {
    (0, 1): "discriminating", (0, 0): "missed",
    (1, 1): "non_discriminating", (1, 0): "reversed",
}
QUESTIONS = ["identical", "control_clean", "mutant_has", "material"]


def load_returns(paths):
    out = []
    for path in paths:
        data = json.loads(Path(path).read_text())
        if data.get("tool") != "brief-defect-review":
            raise SystemExit(f"{path}: not a review file from this tool")
        out.append(data)
    return out


def four_cell(answers, key):
    """Per fixture: was the planted defect named in each condition?"""
    detected = defaultdict(lambda: {"control": False, "mutant": False})
    seen = defaultdict(lambda: {"control": 0, "mutant": 0})
    for cid, value in answers.items():
        entry = key.get(cid)
        if not entry:
            continue
        seen[entry["fixture_id"]][entry["condition"]] += 1
        if value == "yes":
            detected[entry["fixture_id"]][entry["condition"]] = True
    rows = []
    for fixture in sorted(seen):
        both = seen[fixture]["control"] and seen[fixture]["mutant"]
        control = int(detected[fixture]["control"])
        mutant = int(detected[fixture]["mutant"])
        rows.append({
            "fixture_id": fixture, "control": control, "mutant": mutant,
            "outcome": OUTCOMES[(control, mutant)] if both else "incomplete",
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("returns", nargs="+", help="the JSON files reviewers sent back")
    parser.add_argument("--key", default=str(EXPERIMENT / "adjudication-baseline" / "KEY.json"))
    parser.add_argument("--out", default=str(EXPERIMENT / "results" / "review-outcome.json"))
    args = parser.parse_args()

    key = json.loads(Path(args.key).read_text())
    returns = load_returns(args.returns)

    print("== WHAT CAME BACK ==")
    for data in returns:
        counts = data.get("counts", {})
        print(f"  {data['reviewer']:<24} {counts.get('challenges_scored', 0)}/"
              f"{counts.get('challenges_total', 0)} challenges, "
              f"{counts.get('fixtures_reviewed', 0)}/{counts.get('fixtures_total', 0)} fixtures checked")

    print("\n== FIXTURE CHECK: does each planted defect hold up? ==")
    print(f"{'fixture':<9} " + " ".join(f"{d['reviewer'][:11]:>12}" for d in returns) + "   admitted?")
    fixtures = sorted({f for d in returns for f in d.get("fixture_reviews", {})})
    admitted = []
    for fixture in fixtures:
        cells, all_yes = [], True
        for data in returns:
            review = (data.get("fixture_reviews") or {}).get(fixture, {})
            answered = [review.get(q) for q in QUESTIONS]
            if not all(answered):
                cells.append("--"); all_yes = False
            else:
                yes = sum(1 for a in answered if a == "yes")
                cells.append(f"{yes}/4"); all_yes &= (yes == 4)
        if all_yes:
            admitted.append(fixture)
        print(f"{fixture:<9} " + " ".join(f"{c:>12}" for c in cells)
              + f"   {'yes' if all_yes else 'NO'}")
    print(f"\n  Only yes/yes/yes/yes from every reviewer admits a fixture to the "
          f"held-out set.\n  Admitted: {', '.join(admitted) if admitted else 'none'}")

    print("\n== FOUR-CELL OUTCOME, PER REVIEWER ==")
    per_reviewer = {}
    for data in returns:
        rows = four_cell(data.get("challenge_answers", {}), key)
        per_reviewer[data["reviewer"]] = rows
        counts = defaultdict(int)
        for row in rows:
            counts[row["outcome"]] += 1
        print(f"  {data['reviewer']:<24} " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    print("\n== WHERE REVIEWERS DISAGREED ==")
    disputes = []
    if len(returns) >= 2:
        for left, right in itertools.combinations(returns, 2):
            a, b = left.get("challenge_answers", {}), right.get("challenge_answers", {})
            shared = set(a) & set(b)
            differ = sorted(c for c in shared if a[c] != b[c])
            agree = len(shared) - len(differ)
            print(f"  {left['reviewer']} vs {right['reviewer']}: "
                  f"{agree}/{len(shared)} agreed"
                  + (f" ({agree / len(shared):.0%})" if shared else ""))
            for cid in differ:
                entry = key.get(cid, {})
                disputes.append({"challenge": cid, "fixture": entry.get("fixture_id"),
                                 left["reviewer"]: a[cid], right["reviewer"]: b[cid]})
        by_fixture = defaultdict(int)
        for dispute in disputes:
            by_fixture[dispute["fixture"]] += 1
        if by_fixture:
            print("\n  disputed challenges by fixture: "
                  + ", ".join(f"{k}={v}" for k, v in sorted(by_fixture.items())))
            print("  A fixture with several disputes has an ambiguous gold label; "
                  "consider\n  keeping it out of the held-out set whatever the Gym did.")
    else:
        print("  (only one reviewer returned a file)")

    Path(args.out).write_text(json.dumps({
        "reviewers": [d["reviewer"] for d in returns],
        "admitted_fixtures": admitted,
        "four_cell_by_reviewer": per_reviewer,
        "disputes": disputes,
    }, indent=2) + "\n")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

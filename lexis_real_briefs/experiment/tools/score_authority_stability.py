"""Score repeated authority-support matched pairs from private or public reports."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from score_rule_floor_stability import load_result, result_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-dir", required=True, type=Path)
    parser.add_argument("--run", action="append", required=True, type=Path)
    args = parser.parse_args()

    fixtures = [
        json.loads(path.read_text())
        for path in sorted(args.fixtures_dir.glob("*/fixture.json"))
    ]
    outcomes: dict[tuple[str, str], list[str]] = defaultdict(list)
    rows = []
    for run in args.run:
        counts = Counter()
        for fixture in fixtures:
            fixture_id = fixture["fixture_id"]
            target_id = fixture["gold"]["preview_target_id"]
            dispositions = {}
            for condition in ("control", "mutant"):
                result = load_result(
                    result_path(run, fixture_id, condition), condition
                )
                matches = [
                    test for test in result.get("correctness_tests", [])
                    if test.get("checkId") == "authority_support"
                    and test.get("targetId") == target_id
                ]
                disposition = (
                    matches[0].get("disposition") if len(matches) == 1
                    else f"matches={len(matches)}"
                )
                dispositions[condition] = disposition
                outcomes[(fixture_id, condition)].append(disposition)
                counts["degraded"] += bool(result.get("degraded"))

            control = dispositions["control"]
            mutant = dispositions["mutant"]
            counts["detected"] += mutant == "must_fix"
            counts["specific"] += control != "must_fix"
            counts["exact_pass"] += control == "pass"
            counts["paired"] += control != "must_fix" and mutant == "must_fix"
            counts["unresolved"] += control == "review" and mutant == "review"
            counts["reversed"] += control == "must_fix" and mutant != "must_fix"
        rows.append(counts)

    denominator = len(fixtures)
    print("run\tdetected\tspecific\texact_pass\tpaired\tunresolved\treversed\tdegraded")
    for index, counts in enumerate(rows, 1):
        print(
            f"{index}\t{counts['detected']}/{denominator}\t"
            f"{counts['specific']}/{denominator}\t"
            f"{counts['exact_pass']}/{denominator}\t"
            f"{counts['paired']}/{denominator}\t"
            f"{counts['unresolved']}/{denominator}\t"
            f"{counts['reversed']}/{denominator}\t{counts['degraded']}"
        )

    stable = sum(len(set(values)) == 1 for values in outcomes.values())
    print(f"\ntarget-condition identities stable: {stable}/{len(outcomes)}")
    for (fixture_id, condition), values in sorted(outcomes.items()):
        if len(set(values)) > 1:
            print(f"VARIABLE\t{fixture_id}\t{condition}\t{','.join(values)}")


if __name__ == "__main__":
    main()

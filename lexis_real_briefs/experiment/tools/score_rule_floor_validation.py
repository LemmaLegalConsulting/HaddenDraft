"""Score stable rule-element targets in a completed matched-pair run."""

import argparse
import json
from pathlib import Path


def load_target(result, target_id):
    matches = [
        test for test in result.get("correctness_tests", [])
        if test.get("checkId") == "rule_elements" and test.get("targetId") == target_id
    ]
    if len(matches) != 1:
        return f"matches={len(matches)}", []
    extras = [
        test.get("targetId") for test in result.get("correctness_tests", [])
        if test.get("disposition") == "must_fix" and test.get("targetId") != target_id
    ]
    return matches[0].get("disposition"), extras


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--fixtures-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for home in sorted(args.fixtures_dir.iterdir()):
        fixture_path = home / "fixture.json"
        if not fixture_path.exists():
            continue
        fixture = json.loads(fixture_path.read_text())
        target = fixture["mutation"]["expected_target_id"]
        row = {"fixture": fixture["fixture_id"], "target": target}
        for condition in ("control", "mutant"):
            result = json.loads(
                (args.results / f"{fixture['fixture_id']}-{condition}" / "result.json").read_text()
            )
            disposition, extras = load_target(result, target)
            row[condition] = disposition
            row[f"{condition}_extra_must_fix"] = extras
            row[f"{condition}_degraded"] = bool(result.get("degraded"))
        rows.append(row)

    print("fixture\tcontrol\tmutant\textra_must_fix(control/mutant)\tdegraded")
    for row in rows:
        print(
            f"{row['fixture']}\t{row['control']}\t{row['mutant']}\t"
            f"{len(row['control_extra_must_fix'])}/{len(row['mutant_extra_must_fix'])}\t"
            f"{row['control_degraded'] or row['mutant_degraded']}"
        )
    exact = sum(row["control"] == "pass" and row["mutant"] == "must_fix" for row in rows)
    detected = sum(row["mutant"] == "must_fix" for row in rows)
    specific = sum(row["control"] == "pass" for row in rows)
    degraded = sum(row["control_degraded"] or row["mutant_degraded"] for row in rows)
    print(f"\nexact paired gate: {exact}/{len(rows)}")
    print(f"mutation detection: {detected}/{len(rows)}")
    print(f"clean target specificity: {specific}/{len(rows)}")
    print(f"degraded pairs: {degraded}/{len(rows)}")


if __name__ == "__main__":
    main()

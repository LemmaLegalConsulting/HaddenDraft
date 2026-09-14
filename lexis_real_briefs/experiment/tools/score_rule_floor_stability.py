"""Compare stable rule-element identities across repeated matched-pair runs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def result_path(run: Path, fixture_id: str, condition: str) -> Path:
    private = run / "shards" / fixture_id / f"{fixture_id}-{condition}" / "result.json"
    if private.is_file():
        return private
    return run / "shards" / fixture_id / "report.public.json"


def load_result(path: Path, condition: str) -> dict:
    payload = json.loads(path.read_text())
    if "results" not in payload:
        return payload
    matches = [
        result for result in payload["results"]
        if result.get("condition") == condition
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one {condition} result in {path}; found {len(matches)}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-dir", required=True, type=Path)
    parser.add_argument("--run", action="append", required=True, type=Path)
    parser.add_argument(
        "--replacement",
        action="append",
        default=[],
        metavar="RUN_INDEX:FIXTURE:CONDITION:RESULT_JSON",
        help="Replace one technically degraded result; RUN_INDEX is one-based.",
    )
    args = parser.parse_args()

    replacements: dict[tuple[int, str, str], Path] = {}
    for value in args.replacement:
        run_index, fixture_id, condition, path = value.split(":", 3)
        replacements[(int(run_index) - 1, fixture_id, condition)] = Path(path)

    fixtures = []
    for home in sorted(args.fixtures_dir.iterdir()):
        if (home / "fixture.json").is_file():
            fixtures.append(json.loads((home / "fixture.json").read_text()))

    outcomes: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    extras: dict[tuple[str, str], list[str]] = defaultdict(list)
    per_run = []
    original_degraded = 0
    scored_degraded = 0
    for run_index, run in enumerate(args.run):
        metrics = Counter()
        for fixture in fixtures:
            fixture_id = fixture["fixture_id"]
            target_id = fixture["mutation"]["expected_target_id"]
            condition_results = {}
            for condition in ("control", "mutant"):
                original = load_result(
                    result_path(run, fixture_id, condition), condition
                )
                original_degraded += bool(original.get("degraded"))
                path = replacements.get(
                    (run_index, fixture_id, condition),
                    result_path(run, fixture_id, condition),
                )
                result = load_result(path, condition)
                scored_degraded += bool(result.get("degraded"))
                tests = {
                    test["targetId"]: test["disposition"]
                    for test in result.get("correctness_tests", [])
                    if test.get("checkId") == "rule_elements"
                }
                disposition = tests.get(target_id, "missing")
                condition_results[condition] = disposition
                outcomes[(fixture_id, target_id, condition)].append(disposition)
                for extra_target, extra_disposition in tests.items():
                    if extra_target != target_id:
                        extras[(fixture_id, extra_target)].append(extra_disposition)
                # Preserve an explicit value when a target did not appear in a run.
                prior_targets = {
                    target for observed_fixture, target in extras
                    if observed_fixture == fixture_id and target != target_id
                }
                for prior_target in prior_targets - tests.keys():
                    extras[(fixture_id, prior_target)].append("missing")

            control = condition_results["control"]
            mutant = condition_results["mutant"]
            metrics["detected"] += mutant == "must_fix"
            metrics["specific"] += control != "must_fix"
            metrics["exact_pass"] += control == "pass"
            metrics["paired"] += control != "must_fix" and mutant == "must_fix"
            metrics["reversed"] += control == "must_fix" and mutant != "must_fix"

            for condition in ("control", "mutant"):
                path = replacements.get(
                    (run_index, fixture_id, condition),
                    result_path(run, fixture_id, condition),
                )
                result = load_result(path, condition)
                metrics[f"extra_{condition}"] += sum(
                    test.get("disposition") == "must_fix"
                    and test.get("checkId") == "rule_elements"
                    and test.get("targetId") != target_id
                    for test in result.get("correctness_tests", [])
                )
        per_run.append(dict(metrics))

    denominator = len(fixtures)
    print("run\tdetected\tspecific\texact_pass\tpaired\treversed\textra_control\textra_mutant")
    for index, metrics in enumerate(per_run, 1):
        print(
            f"{index}\t{metrics['detected']}/{denominator}\t"
            f"{metrics['specific']}/{denominator}\t"
            f"{metrics['exact_pass']}/{denominator}\t"
            f"{metrics['paired']}/{denominator}\t"
            f"{metrics['reversed']}/{denominator}\t{metrics['extra_control']}\t"
            f"{metrics['extra_mutant']}"
        )

    print("\naverages")
    for key in ("detected", "specific", "exact_pass", "paired", "reversed", "extra_control", "extra_mutant"):
        print(f"{key}: {sum(row[key] for row in per_run) / len(per_run):.2f}")

    stable_targets = sum(len(set(values)) == 1 for values in outcomes.values())
    print(f"\nregistered target-condition identities stable: {stable_targets}/{len(outcomes)}")
    for (fixture_id, target_id, condition), values in sorted(outcomes.items()):
        if len(set(values)) > 1:
            print(f"VARIABLE TARGET\t{fixture_id}\t{condition}\t{target_id}\t{','.join(values)}")

    print("\nextra control identities (must_fix recurrence across runs)")
    for (fixture_id, target_id), values in sorted(extras.items()):
        # Only report identities that were MUST_FIX in at least one control.
        control_values = []
        for run_index, run in enumerate(args.run):
            fixture = next(item for item in fixtures if item["fixture_id"] == fixture_id)
            expected = fixture["mutation"]["expected_target_id"]
            path = replacements.get(
                (run_index, fixture_id, "control"),
                result_path(run, fixture_id, "control"),
            )
            result = load_result(path, "control")
            tests = {
                test["targetId"]: test["disposition"]
                for test in result.get("correctness_tests", [])
                if test.get("checkId") == "rule_elements" and test.get("targetId") != expected
            }
            control_values.append(tests.get(target_id, "missing"))
        count = control_values.count("must_fix")
        if count:
            print(
                f"{fixture_id}\t{target_id}\t{count}/{len(args.run)}\t"
                f"{','.join(control_values)}"
            )

    print(f"\noriginal results degraded: {original_degraded}")
    print(f"scored results still degraded: {scored_degraded}")


if __name__ == "__main__":
    main()

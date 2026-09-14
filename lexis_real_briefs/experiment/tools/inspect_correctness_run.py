#!/usr/bin/env python3
"""Print a compact, human-reviewable audit of saved correctness runs."""

import argparse
import json
from pathlib import Path


def short(value, limit=180):
    value = " ".join(str(value or "").split()).replace("|", "\\|")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def candidate_payload(messages):
    user = "\n".join(
        str(message.get("content") or "")
        for message in messages or []
        if message.get("role") == "user"
    )
    marker = "Candidate challenges and the only evidence you may use:\n"
    if marker not in user:
        return []
    serialized = user.split(marker, 1)[1].split("\n\nReturn ", 1)[0]
    try:
        payload = json.loads(serialized)
    except (TypeError, ValueError):
        return []
    return payload if isinstance(payload, list) else []


def response_payload(value):
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("```"):
            value = value.split("\n", 1)[1] if "\n" in value else ""
            value = value.rsplit("```", 1)[0].strip()
    try:
        payload = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def judge_audits(result_path):
    audits = []
    for call_path in sorted(result_path.parent.glob("call-*.json")):
        call = json.loads(call_path.read_text(encoding="utf-8"))
        if call.get("prompt_key") != "argument_gym.correctness_judge":
            continue
        candidates = candidate_payload(call.get("messages"))
        expected = {item.get("candidateId") for item in candidates}
        rulings = response_payload(call.get("response")).get("rulings") or []
        returned = {item.get("candidateId") for item in rulings if isinstance(item, dict)}
        blank_reasons = sum(not short(item.get("reason")) for item in rulings if isinstance(item, dict))
        adverse_without_evidence = sum(
            str(item.get("disposition") or "").casefold()
            in {"must_fix", "review", "sustain", "sustained", "reserve", "reserved"}
            and not item.get("evidenceRefs")
            for item in rulings
            if isinstance(item, dict)
        )
        audits.append(
            {
                "path": call_path,
                "model": call.get("model", ""),
                "expected": len(expected),
                "returned": len(returned),
                "missing": sorted(expected - returned),
                "extra": sorted(returned - expected),
                "blankReasons": blank_reasons,
                "adverseWithoutEvidence": adverse_without_evidence,
                "seconds": call.get("elapsed_seconds"),
            }
        )
    return audits


def prompt_audit(result_path, context_window, output_reserve):
    rows = []
    for call_path in sorted(result_path.parent.glob("call-*.json")):
        call = json.loads(call_path.read_text(encoding="utf-8"))
        chars = sum(len(str(message.get("content") or "")) for message in call.get("messages") or [])
        conservative_tokens = (chars + 2) // 3
        rows.append(
            {
                "path": call_path,
                "prompt": call.get("prompt_key", ""),
                "chars": chars,
                "tokens": conservative_tokens,
                "safe": conservative_tokens + output_reserve <= context_window,
            }
        )
    return sorted(rows, key=lambda row: row["tokens"], reverse=True)


def print_result(result_path, context_window, output_reserve):
    result = json.loads(result_path.read_text(encoding="utf-8"))
    label = f"{result.get('fixture_id', '?')} / {result.get('condition', '?')}"
    print(f"## {label}\n")
    print(f"- Result: `{result_path}`")
    print(f"- Status: `{result.get('status')}`")
    print(f"- Assessment: {short(result.get('assessment'), 500)}")
    if result.get("degraded"):
        print(f"- **DEGRADED:** {short(result['degraded'].get('reason'), 500)}")
    print("\n### Checks\n")
    print("| Check | Status | Reason |")
    print("| --- | --- | --- |")
    for check in result.get("checks_run") or []:
        if check.get("category") == "correctness":
            print(f"| {check.get('id')} | {check.get('status')} | {short(check.get('reason'))} |")

    tests = result.get("correctness_tests") or []
    visible = [
        test
        for test in tests
        if test.get("disposition") != "pass" and test.get("userVisible", True)
    ]
    print("\n### Visible findings\n")
    if not visible:
        print("No visible MUST_FIX or REVIEW findings.")
    else:
        print("| Disposition | Test target | Claim | Problem | Judge reason | Evidence |")
        print("| --- | --- | --- | --- | --- | --- |")
        for test in visible:
            identity = f"{test.get('checkId')} / {test.get('targetId')}"
            evidence = ", ".join(
                str(ref)
                for ref in [*(test.get("briefEvidence") or []), *(test.get("externalEvidence") or [])]
            )
            print(
                f"| {test.get('disposition')} | {identity} | {short(test.get('claim'))} | "
                f"{short(test.get('problem'))} | {short(test.get('reason'))} | {short(evidence)} |"
            )

    print("\n### Judge contract audit\n")
    audits = judge_audits(result_path)
    if not audits:
        print("No correctness-Judge calls were saved.")
    else:
        print("| Transcript | Model | Expected/returned | Missing | Extra | Blank reasons | Adverse without evidence | Seconds |")
        print("| --- | --- | ---: | --- | --- | ---: | ---: | ---: |")
        for audit in audits:
            print(
                f"| `{audit['path']}` | {audit['model']} | {audit['expected']}/{audit['returned']} | "
                f"{short(', '.join(audit['missing']))} | {short(', '.join(audit['extra']))} | "
                f"{audit['blankReasons']} | {audit['adverseWithoutEvidence']} | {audit['seconds']} |"
            )

    print("\n### Context-window audit\n")
    print(
        f"Conservative estimate: 3 characters/token, {output_reserve:,}-token output reserve, "
        f"{context_window:,}-token context window."
    )
    print("\n| Transcript | Prompt | Input chars | Estimated tokens | Fits with reserve? |")
    print("| --- | --- | ---: | ---: | --- |")
    for row in prompt_audit(result_path, context_window, output_reserve)[:8]:
        print(
            f"| `{row['path']}` | {row['prompt']} | {row['chars']:,} | "
            f"{row['tokens']:,} | {'yes' if row['safe'] else '**NO**'} |"
        )
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="An experiment directory or one result.json file")
    parser.add_argument("--context-window", type=int, default=128_000)
    parser.add_argument("--output-reserve", type=int, default=16_000)
    args = parser.parse_args()
    path = Path(args.path).resolve()
    if path.is_file():
        results = [path]
    elif (path / "result.json").is_file():
        results = [path / "result.json"]
    else:
        # Sequential runs place results one level below the run directory;
        # parallel runs add an isolated fixture-shard level.
        results = sorted(path.rglob("result.json"))
    if not results:
        parser.error("No result.json files found")
    print("# Argument Gym manual review\n")
    for result in results:
        print_result(result, args.context_window, args.output_reserve)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Qualify a Judge model quickly by replaying saved correctness candidates."""

import argparse
import json
import os
from pathlib import Path
import sys
from time import monotonic


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.test.utils import override_settings  # noqa: E402

from apps.ai.openai_client import OpenAICompatibleClient  # noqa: E402
from apps.argument_gym import correctness  # noqa: E402


def candidates_from_call(path):
    call = json.loads(path.read_text(encoding="utf-8"))
    user = "\n".join(
        str(message.get("content") or "")
        for message in call.get("messages") or []
        if message.get("role") == "user"
    )
    marker = "Candidate challenges and the only evidence you may use:\n"
    serialized = user.split(marker, 1)[1].split("\n\nReturn ", 1)[0]
    candidates = json.loads(serialized)
    if not isinstance(candidates, list):
        raise ValueError("Saved Judge prompt does not contain a candidate list")
    return candidates


class CapturingPinnedClient:
    def __init__(self, *, model, api_key=None, base_url=None, reasoning="medium"):
        self.model = model
        self.reasoning = reasoning or None
        self.client = OpenAICompatibleClient(api_key=api_key, base_url=base_url)
        self.calls = []

    def complete(self, *, system, user, temperature=0, **_kwargs):
        row = {"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        started = monotonic()
        try:
            response = self.client.complete(
                system=system,
                user=user,
                temperature=temperature,
                model=self.model,
                reasoning_level=self.reasoning,
            )
            row.update(status="complete", response=response)
            return response
        except Exception as exc:  # Stage records the unavailable result; preserve why here.
            row.update(status="failed", errorType=type(exc).__name__, error=str(exc)[:500])
            raise
        finally:
            row["elapsedSeconds"] = round(monotonic() - started, 3)
            self.calls.append(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_call", help="Saved correctness-Judge call-*.json")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, help="New JSON report path")
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env", help="Environment variable holding a nondefault provider key")
    parser.add_argument("--reasoning", default="medium", help="Empty string omits reasoning_effort")
    args = parser.parse_args()

    source = Path(args.source_call).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        parser.error("Output already exists")
    candidates = candidates_from_call(source)[args.offset : args.offset + args.limit]
    api_key = os.environ.get(args.api_key_env, "") if args.api_key_env else None
    if args.api_key_env and not api_key:
        parser.error(f"{args.api_key_env} is not set")
    client = CapturingPinnedClient(
        model=args.model,
        api_key=api_key,
        base_url=args.base_url,
        reasoning=args.reasoning,
    )
    with override_settings(AI_DRAFTING_ENABLED=True):
        rulings, traces = correctness.judge_stage(candidates, jurisdiction="Ohio", llm_client=client)
    expected = {candidate["candidateId"] for candidate in candidates}
    returned = {ruling["candidateId"] for ruling in rulings}
    report = {
        "sourceCall": str(source),
        "model": args.model,
        "expected": len(expected),
        "returned": len(returned),
        "missing": sorted(expected - returned),
        "extra": sorted(returned - expected),
        "blankReasons": sum(not ruling.get("judgeReason") for ruling in rulings),
        "adverseWithoutEvidence": sum(
            ruling.get("disposition") in {correctness.MUST_FIX, correctness.REVIEW}
            and not ruling.get("evidenceRefs")
            for ruling in rulings
        ),
        "traces": traces,
        "rulings": rulings,
        "calls": client.calls,
    }
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        f"{args.model}: {len(returned)}/{len(expected)} rulings; "
        f"blank reasons={report['blankReasons']}; adverse without evidence={report['adverseWithoutEvidence']}"
    )
    print(f"Saved {output}")
    return 0 if len(returned) == len(expected) and not report["blankReasons"] and not report["adverseWithoutEvidence"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

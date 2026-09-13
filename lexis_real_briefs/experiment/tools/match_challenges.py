"""Decide, by model, whether each challenge names the registered vulnerability.

This replaces the human adjudication §6 asked for; §8b records what that costs
and why it is done this way. Three matchers from three families, none under
test, each blind to everything the human worksheet blinded: the condition, the
cell, the models that wrote and judged the challenge, and the brief itself. All
it sees is one fixture's registered vulnerability and one challenge's text.

Majority of three decides. Agreement among them is reported before any detection
figure, because if they split materially the detection result is soft and the
honest conclusion is that the corpus cannot settle the question without the
human pass that was skipped.
"""

import argparse
import concurrent.futures
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.ai.openai_client import OpenAICompatibleClient  # noqa: E402

EXPERIMENT = ROOT / "lexis_real_briefs" / "experiment"
FIXTURES = EXPERIMENT / "fixtures"
# Frontier tier, three families, none under test. An earlier set (kimi-k2.6,
# grok-4.1-fast-reasoning, llama-4-maverick) was replaced because disagreement
# among non-frontier matchers cannot be told apart from incapacity.
MATCHERS = ["glm-5-3", "grok-4-6", "kimi-k3"]

SYSTEM = (
    "You decide whether a criticism of a legal brief names one specific, stated "
    "vulnerability. You are not judging whether the criticism is good, whether the "
    "brief is good, or whether the criticism is correct about the law. One question "
    "only: does it name THAT vulnerability?\n"
    "It counts as naming it if it identifies the same underlying proposition, in any "
    "wording. It does NOT count if it merely observes that something is missing, "
    "weak or unsupported without saying what, or if it names a different problem in "
    "the same passage. Return strict JSON only."
)
USER = (
    "THE VULNERABILITY:\n{gold}\n\n"
    "THE CRITICISM:\n{argument}\n{why}\n\n"
    'Return {{"match": true or false, "why": "at most fifteen words"}}'
)


def ask(client, model, gold, challenge, *, attempts=3):
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER.format(
            gold=gold.strip(),
            argument=challenge["argument"].strip(),
            why=("Why it matters: " + challenge["why"].strip()) if challenge.get("why") else "",
        )},
    ]
    for attempt in range(attempts):
        try:
            raw = client.complete_messages(messages=messages, model=model,
                                           reasoning_level="medium", temperature=0)
            text = raw if isinstance(raw, str) else json.dumps(raw)
            start, end = text.find("{"), text.rfind("}")
            payload = json.loads(text[start:end + 1])
            return bool(payload.get("match")), str(payload.get("why", ""))[:120]
        except Exception:  # noqa: BLE001 - a matcher that will not answer is recorded as such
            if attempt == attempts - 1:
                return None, "matcher did not return a usable answer"
            time.sleep(2 ** attempt)
    return None, ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", default=str(EXPERIMENT / "adjudication-all"),
                        help="directory holding WORKSHEET.md and KEY.json")
    parser.add_argument("--out", default=str(EXPERIMENT / "results" / "matching.json"))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--matcher", action="append")
    parser.add_argument("--fixtures-dir", help="fixture tree holding the gold labels")
    args = parser.parse_args()

    matchers = args.matcher or MATCHERS
    fixtures = Path(args.fixtures_dir).resolve() if args.fixtures_dir else FIXTURES
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_review_app import challenges_from_worksheet

    pool = challenges_from_worksheet(Path(args.pool) / "WORKSHEET.md")
    golds = {}
    for home in sorted(fixtures.iterdir()):
        if home.is_dir():
            manifest = json.loads((home / "fixture.json").read_text())
            golds[manifest["fixture_id"]] = manifest["mutation"]["gold_vulnerability"]

    jobs = [(fixture, challenge, model)
            for fixture, items in sorted(pool.items())
            for challenge in items for model in matchers]
    if not jobs:
        raise SystemExit("No challenges parsed from the worksheet; check --pool and --fixtures-dir.")
    print(f"{sum(len(v) for v in pool.values())} challenges x {len(matchers)} matchers "
          f"= {len(jobs)} decisions")

    client = OpenAICompatibleClient()
    results = defaultdict(dict)
    reasons = defaultdict(dict)
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool_exec:
        futures = {
            pool_exec.submit(ask, client, model, golds[fixture], challenge): (fixture, challenge["id"], model)
            for fixture, challenge, model in jobs
        }
        for future in concurrent.futures.as_completed(futures):
            fixture, cid, model = futures[future]
            verdict, why = future.result()
            results[cid][model] = verdict
            reasons[cid][model] = why
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)

    rows = []
    for fixture, items in sorted(pool.items()):
        for challenge in items:
            votes = results[challenge["id"]]
            yes = sum(1 for v in votes.values() if v is True)
            no = sum(1 for v in votes.values() if v is False)
            rows.append({
                "id": challenge["id"], "fixture_id": fixture,
                "category": challenge["category"],
                "votes": votes, "reasons": reasons[challenge["id"]],
                "yes": yes, "no": no,
                "unanimous": (yes == 0 or no == 0) and (yes + no) == len(matchers),
                "match": yes > no,
                "argument": challenge["argument"][:400],
            })

    Path(args.out).write_text(json.dumps(
        {"matchers": matchers, "decisions": rows}, indent=2) + "\n")

    print("\n== MATCHER AGREEMENT (reported before any detection figure) ==")
    unanimous = sum(1 for r in rows if r["unanimous"])
    print(f"  unanimous on {unanimous}/{len(rows)} challenges ({unanimous / len(rows):.0%})")
    for model in matchers:
        says_yes = sum(1 for r in rows if r["votes"].get(model) is True)
        failed = sum(1 for r in rows if r["votes"].get(model) is None)
        print(f"    {model:<26} match on {says_yes:>3}/{len(rows)}"
              + (f", {failed} no answer" if failed else ""))
    pairs = Counter()
    for r in rows:
        for i, a in enumerate(matchers):
            for b in matchers[i + 1:]:
                if r["votes"].get(a) is not None and r["votes"].get(b) is not None:
                    pairs[(a, b, r["votes"][a] == r["votes"][b])] += 1
    print("  pairwise:")
    for a, b in [(matchers[i], matchers[j]) for i in range(len(matchers)) for j in range(i + 1, len(matchers))]:
        agree, disagree = pairs[(a, b, True)], pairs[(a, b, False)]
        total = agree + disagree
        if total:
            print(f"    {a} vs {b}: {agree}/{total} ({agree / total:.0%})")
    print(f"\n  majority says match on {sum(1 for r in rows if r['match'])}/{len(rows)}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

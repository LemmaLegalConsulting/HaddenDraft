"""The pre-specified 2x2 measures. Nothing here required a human judgment.

Survival, what falls out, top-3 stability and verdict distribution are all
properties of the Gym's own behaviour: the opponent proposed N attacks, the
judge kept M of them, ranked them by importance and labelled each with a
verdict. None of that needs an adjudicator, which is why it is computed here
and target detection is not (see blind_adjudication.py).

The contrasts are the ones REGISTER-2x2.md fixed before any cell ran:

    judge effect, attack held fixed   gpt-gpt vs gpt-ds  |  ds-ds vs ds-gpt
    same-family effect               diagonal vs off-diagonal
    sequencing effect                gpt-ds vs ds-gpt

Everything is additionally split by condition, because a judge that drops more
in the altered draft than the unmodified one is a different finding from one
that drops more everywhere.
"""

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CELLS = ["gpt-gpt", "ds-ds", "gpt-ds", "ds-gpt"]
SAME_FAMILY = {"gpt-gpt", "ds-ds"}


def report_for(directory):
    """The full report where it exists, else the shareable export.

    A clone of this repository has only `report.public.json` -- the full record
    carries 63 MB of third-party corpus text that is not ours to publish. Every
    figure in the paper is computable from either.
    """
    for name in ("report.json", "report.public.json"):
        candidate = Path(directory) / name
        if candidate.exists():
            return candidate
    return None


def load(run_dirs):
    """Completed runs, deduplicated by (cell, fixture, condition).

    A run can be re-executed after a technical failure -- the registered
    stopping rule allows that and only that -- so the same (cell, fixture,
    condition) may appear in an original directory and again in a re-run
    directory. The later completed one wins; failed and degraded runs are
    dropped, so a re-run that succeeded replaces an original that did not.
    """
    latest = {}
    for directory in run_dirs:
        report_path = report_for(directory)
        if report_path is None:
            continue
        report = json.loads(report_path.read_text())
        cell = report["manifest"].get("cell", "single-model")
        created = report["manifest"].get("created_at", "")
        for result in report["results"]:
            if result.get("status") != "complete":
                continue
            key = (cell, result["fixture_id"], result["condition"])
            run_dir = Path(directory) / f"{result['fixture_id']}-{result['condition']}"
            if key not in latest or created >= latest[key][0]:
                latest[key] = (created, {**result, "cell": cell, "_dir": run_dir})
    return [row for _, row in latest.values()]


def attacks_given_to_judge(run_dir):
    """The attack list the judge actually received, read out of its own prompt.

    Two things make the opponent's output the wrong denominator. The pipeline
    appends checklist-derived attacks to the opponent's before the judge sees
    them, and the judge is given the union. And an attack the judge never
    mentions is treated as not kept -- `assessment_by_attack.get(id, {}).get(
    "keep", False)` -- so silence is a drop.

    Both are invisible from the response alone, so the prompt is parsed: the
    attack list is the longest JSON array in it whose objects carry an attack's
    distinctive keys.
    """
    for path in sorted(Path(run_dir).glob("call-*.json")):
        call = json.loads(path.read_text())
        if call.get("role") != "judge" or call.get("status") != "complete":
            continue
        user = "\n".join(m["content"] for m in call["messages"] if m["role"] == "user")
        best = []
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\[", user):
            try:
                value, _ = decoder.raw_decode(user[match.start():])
            except ValueError:
                continue
            if (isinstance(value, list) and value and isinstance(value[0], dict)
                    and {"id", "whyItMatters"} <= set(value[0]) and len(value) > len(best)):
                best = value
        return best
    return []


def survival(runs, results_root=None):
    """What the judge was given, what it answered on, and what it kept.

    Three numbers, not two, because there are two distinct ways an attack dies:
    the judge says keep=false, or the judge does not mention it at all. Rolling
    them together flatters a model that simply answers on fewer attacks.
    """
    rows = []
    for run in runs:
        # Stored by the public export; parsed from the transcripts when they are
        # present. A clone has the former and not the latter.
        given_n = run.get("attacks_given_to_judge")
        if given_n is None:
            run_dir = run.get("_dir")
            given_n = len(attacks_given_to_judge(run_dir)) if run_dir else 0
        assessments = run.get("judge_assessments")
        if not given_n or not isinstance(assessments, list):
            continue
        assessed = len(assessments)
        kept = sum(1 for a in assessments if isinstance(a, dict) and a.get("keep"))
        rows.append({
            "cell": run["cell"], "fixture_id": run["fixture_id"],
            "condition": run["condition"],
            "given": given_n,
            "opponent_authored": run.get("attacks_proposed_count") or 0,
            "assessed": assessed,
            "unassessed": max(0, given_n - assessed),
            "kept": kept,
            "dropped_explicitly": max(0, assessed - kept),
            "rate": kept / given_n,
            "answered_rate": assessed / given_n,
            "challenges": run.get("challenge_count", 0),
        })
    return rows


def fell_out(runs):
    """What the judge dropped, by category and by the importance it assigned."""
    dropped, kept = defaultdict(Counter), defaultdict(Counter)
    importances = defaultdict(lambda: {"kept": [], "dropped": []})
    for run in runs:
        assessments = run.get("judge_assessments")
        attacks = run.get("attacks_proposed")
        if not isinstance(assessments, list) or not isinstance(attacks, list):
            continue
        category_by_id = {a.get("id"): a.get("category", "?") for a in attacks if isinstance(a, dict)}
        for assessment in assessments:
            if not isinstance(assessment, dict):
                continue
            bucket = kept if assessment.get("keep") else dropped
            # An assessed id the opponent never proposed is a checklist-derived
            # attack: the pipeline appends those before the judge sees them.
            bucket[run["cell"]][category_by_id.get(assessment.get("attackId"), "checklist")] += 1
            side = "kept" if assessment.get("keep") else "dropped"
            try:
                importances[run["cell"]][side].append(int(assessment.get("importance", 50)))
            except (TypeError, ValueError):
                pass
    return dropped, kept, importances


def verdicts(runs):
    counts = defaultdict(Counter)
    for run in runs:
        for challenge in run.get("challenges", []):
            counts[run["cell"]][challenge.get("judge_verdict") or "(none)"] += 1
    return counts


def top3(runs):
    """The three highest-importance challenges per run, and cross-cell overlap.

    Compared by category plus the unit the challenge is anchored to, because the
    same issue written by two models will not share wording but will share what
    it is about and where in the brief it lives.
    """
    by_document = defaultdict(dict)
    for run in runs:
        ranked = sorted(run.get("challenges", []),
                        key=lambda c: c.get("importance", 0), reverse=True)[:3]
        signature = {
            (c.get("category", ""), ((c.get("target") or {}).get("unitId") or ""))
            for c in ranked
        }
        by_document[(run["fixture_id"], run["condition"])][run["cell"]] = signature

    overlaps = []
    for document, per_cell in sorted(by_document.items()):
        for left in CELLS:
            for right in CELLS:
                if left >= right or left not in per_cell or right not in per_cell:
                    continue
                a, b = per_cell[left], per_cell[right]
                union = a | b
                overlaps.append({
                    "fixture_id": document[0], "condition": document[1],
                    "pair": f"{left} vs {right}",
                    "shared": len(a & b), "union": len(union),
                    "jaccard": (len(a & b) / len(union)) if union else None,
                })
    return by_document, overlaps


def mean(values):
    return round(statistics.fmean(values), 3) if values else None


def report(runs):
    print(f"{len(runs)} completed runs across {len({r['cell'] for r in runs})} cells\n")

    rows = survival(runs)
    print("== SURVIVAL: attacks the judge was given -> answered on -> kept ==")
    print(f"{'cell':<9} {'cond':<8} {'n':>3} {'given':>6} {'assessed':>9} {'unans':>6} "
          f"{'dropped':>8} {'kept':>6} {'keep%':>7} {'answer%':>8}")
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["cell"], row["condition"])].append(row)
    for (cell, condition), group in sorted(grouped.items()):
        print(f"{cell:<9} {condition:<8} {len(group):>3} "
              f"{sum(g['given'] for g in group):>6} {sum(g['assessed'] for g in group):>9} "
              f"{sum(g['unassessed'] for g in group):>6} "
              f"{sum(g['dropped_explicitly'] for g in group):>8} "
              f"{sum(g['kept'] for g in group):>6} "
              f"{mean([g['rate'] for g in group]):>7} {mean([g['answered_rate'] for g in group]):>8}")
    print("\n  'unans' = attacks the judge never mentioned. The pipeline treats an")
    print("  unmentioned attack as not kept, so silence is a drop -- counted separately")
    print("  because a model that answers on fewer attacks would otherwise look selective.")

    print("\n-- registered contrasts (mean survival rate) --")
    def rate_for(predicate):
        selected = [r["rate"] for r in rows if predicate(r)]
        return mean(selected), len(selected)
    for label, predicate in [
        ("gpt attacks, gpt judge   (same)", lambda r: r["cell"] == "gpt-gpt"),
        ("gpt attacks, ds judge    (cross)", lambda r: r["cell"] == "gpt-ds"),
        ("ds attacks, ds judge     (same)", lambda r: r["cell"] == "ds-ds"),
        ("ds attacks, gpt judge    (cross)", lambda r: r["cell"] == "ds-gpt"),
        ("all same-family", lambda r: r["cell"] in SAME_FAMILY),
        ("all cross-family", lambda r: r["cell"] not in SAME_FAMILY),
    ]:
        value, n = rate_for(predicate)
        print(f"  {label:<34} {value}  (n={n})")

    print("\n-- marginals: which model, in which seat --")
    for label, predicate in [
        ("judge = gpt-5.6-sol", lambda r: r["cell"] in ("gpt-gpt", "ds-gpt")),
        ("judge = deepseek-v4-pro", lambda r: r["cell"] in ("gpt-ds", "ds-ds")),
        ("attacker = gpt-5.6-sol", lambda r: r["cell"] in ("gpt-gpt", "gpt-ds")),
        ("attacker = deepseek-v4-pro", lambda r: r["cell"] in ("ds-ds", "ds-gpt")),
    ]:
        selected = [r for r in rows if predicate(r)]
        print(f"  {label:<28} keep%={mean([r['rate'] for r in selected])}  "
              f"answered%={mean([r['answered_rate'] for r in selected])}  (n={len(selected)})")

    dropped, kept, importances = fell_out(runs)
    print("\n== WHAT FALLS OUT: dropped attacks by category ==")
    for cell in CELLS:
        if not dropped[cell] and not kept[cell]:
            continue
        total_dropped = sum(dropped[cell].values())
        total_kept = sum(kept[cell].values())
        print(f"  {cell:<9} dropped {total_dropped:>3}, kept {total_kept:>3}   "
              f"mean importance kept={mean(importances[cell]['kept'])} "
              f"dropped={mean(importances[cell]['dropped'])}")
        for category, count in dropped[cell].most_common(5):
            print(f"      dropped {category:<24} {count}")

    print("\n== JUDGE VERDICTS on kept challenges ==")
    counts = verdicts(runs)
    labels = sorted({v for c in counts.values() for v in c})
    print(f"{'cell':<9} " + " ".join(f"{v:>12}" for v in labels))
    for cell in CELLS:
        if cell not in counts:
            continue
        print(f"{cell:<9} " + " ".join(f"{counts[cell][v]:>12}" for v in labels))

    _, overlaps = top3(runs)
    print("\n== TOP-3 STABILITY across cells (category + anchored unit) ==")
    by_pair = defaultdict(list)
    for row in overlaps:
        if row["jaccard"] is not None:
            by_pair[row["pair"]].append(row["jaccard"])
    for pair, values in sorted(by_pair.items()):
        left, right = pair.split(" vs ")
        marker = "shared judge" if left.split("-")[1] == right.split("-")[1] else (
                 "shared attacker" if left.split("-")[0] == right.split("-")[0] else "")
        print(f"  {pair:<22} mean Jaccard {mean(values):<6} over {len(values)} documents  {marker}")

    print("\nCounts, not rates with intervals: eight fixtures per cell.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", nargs="+", required=True)
    parser.add_argument("--json-out")
    args = parser.parse_args()
    runs = load(args.run_dir)
    if not runs:
        print("No completed runs found.")
        return 1
    report(runs)
    if args.json_out:
        dropped, kept, importances = fell_out(runs)
        Path(args.json_out).write_text(json.dumps({
            "survival": survival(runs),
            "dropped_by_category": {k: dict(v) for k, v in dropped.items()},
            "kept_by_category": {k: dict(v) for k, v in kept.items()},
            "verdicts": {k: dict(v) for k, v in verdicts(runs).items()},
            "top3_overlaps": top3(runs)[1],
        }, indent=2))
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

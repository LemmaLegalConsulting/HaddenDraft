"""Pool challenges across cells and conditions, strip the labels, shuffle.

Whether a challenge "names the registered vulnerability" is a judgment. In the
2x2 that judgment has to be made across eight runs of the same fixture that
differ by condition and by model, and an adjudicator who can see which run
produced a challenge may, without meaning to, hold the flawed draft to a
different standard than the unflawed one, or one model's prose to a different
standard than another's.

So the worksheet reveals the fixture -- it must, because the gold vulnerability
is what the judgment is against -- and nothing else. Condition, cell, attack
model and judge model are stripped; the pool is shuffled under a recorded seed;
each challenge carries an opaque id. The map back to the run lives in a separate
key file that the scoring step reads and the adjudicator does not.

Judge-produced fields are stripped too, not only the run labels: severity,
confidence, importance and the judge's own verdict are outputs of the very model
whose identity is being hidden, and leaving them in would hand the adjudicator a
fingerprint. What remains is the opponent's argument, why it matters, the
category, and where in the brief it was anchored.

This does not make the source unguessable -- prose style survives any amount of
label-stripping. It removes the systematic cue, which is what biases a long
sequence of judgments.

    --emit   build WORKSHEET.md + worksheet.yaml + KEY.json (keep the key closed)
    --score  unblind the completed worksheet and write per-run detection
"""

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse_2x2 import report_for  # noqa: E402

OUTCOMES = {
    (0, 1): ("discriminating", "the mutation caused the finding"),
    (0, 0): ("missed", "the introduced defect was not detected"),
    (1, 1): ("non_discriminating", "already flagged in the unmodified brief"),
    (1, 0): ("reversed", "the mutation suppressed a finding -- investigate"),
}

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "lexis_real_briefs" / "experiment"
FIXTURES = EXPERIMENT / "fixtures"

# Stripped because they are judge outputs and would fingerprint the judge model.
JUDGE_FIELDS = ("severity", "confidence", "importance", "judge_verdict", "judge_assessment")


def opaque_id(run_key, ordinal, seed):
    digest = hashlib.sha256(f"{seed}|{run_key}|{ordinal}".encode()).hexdigest()
    return f"C{digest[:10]}"


def replicate_of(directory):
    """A replicate tag from the directory name, so deliberate repeats are kept.

    Deduplication exists for one reason: a run re-executed after a technical
    failure should replace the failed one. It must not collapse the four
    deliberate replicates of every cell into one, which is what happened the
    first time this pooled -- 422 challenges instead of 1,711, putting the whole
    detection measure on a single run after the stability work showed a single
    run can sit at the extreme of its range.
    """
    match = re.search(r"-(rep\d+)-", Path(directory).name)
    return match.group(1) if match else ""


def collect_dropped(run_dirs, seed):
    """Attacks the opponent raised and the judge threw out.

    A challenge row exists only for an attack the judge kept, so scoring on
    challenges alone conflates two different failures: the opponent never saw
    the defect, and the opponent saw it but the judge killed it. Those are a
    generation failure and a judgment failure, and the pipeline's own numbers
    say they are not rare -- across the mechanical tier the judge discarded
    1,064 attacks that carried usable text.

    Pooled and blinded exactly as the kept challenges are, so the two can be
    matched under the same conditions and combined into a three-level outcome:
    not identified, identified and discarded, identified and upheld.
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
            rep = replicate_of(directory)
            key = (rep, cell, result["fixture_id"], result["condition"])
            if key not in latest or created >= latest[key][0]:
                latest[key] = (created, cell, result, rep)

    pool, key = {}, {}
    for _, cell, result, rep in latest.values():
        attacks = result.get("attacks_proposed") or []
        assessments = result.get("judge_assessments") or []
        upheld = {a.get("attackId") for a in assessments
                  if isinstance(a, dict) and a.get("keep")}
        run_key = f"{rep}|{cell}|{result['fixture_id']}|{result['condition']}"
        for attack in attacks:
            if not isinstance(attack, dict) or attack.get("id") in upheld:
                continue
            argument = (attack.get("argument") or "").strip()
            if not argument:
                continue
            cid = opaque_id(run_key + "|dropped", attack["id"], seed)
            pool.setdefault(result["fixture_id"], []).append({
                "id": cid,
                "category": attack.get("category", ""),
                "argument": argument,
                "why_it_matters": (attack.get("whyItMatters") or "").strip(),
                "anchored_at": "",
            })
            key[cid] = {
                "fixture_id": result["fixture_id"], "condition": result["condition"],
                "cell": cell, "replicate": rep, "attack_model": result.get("attack_model"),
                "judge_model": result.get("judge_model"),
                "ordinal": attack["id"], "run_id": result.get("run_id"),
                "stage": "proposed_then_discarded",
            }
    rng = random.Random(seed)
    for fixture_id in pool:
        rng.shuffle(pool[fixture_id])
    return pool, key


def collect(run_dirs, seed):
    """Every challenge from every run, grouped by fixture, shuffled, anonymised."""
    # Deduplicated the same way the analysis is: a re-run after a technical
    # failure replaces the original, so a challenge is pooled once.
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
            rep = replicate_of(directory)
            entry_key = (rep, cell, result["fixture_id"], result["condition"])
            if entry_key not in latest or created >= latest[entry_key][0]:
                latest[entry_key] = (created, cell, result, rep)

    pool, key = {}, {}
    for _, cell, result, rep in latest.values():
        if True:
            run_key = f"{rep}|{cell}|{result['fixture_id']}|{result['condition']}"
            for challenge in result.get("challenges", []):
                cid = opaque_id(run_key, challenge["ordinal"], seed)
                target = challenge.get("target") or {}
                pool.setdefault(result["fixture_id"], []).append({
                    "id": cid,
                    "category": challenge.get("category", ""),
                    "argument": (challenge.get("opponent_argument") or "").strip(),
                    "why_it_matters": (challenge.get("why_it_matters") or "").strip(),
                    "anchored_at": (target.get("excerpt") or "").strip()[:200],
                })
                key[cid] = {
                    "fixture_id": result["fixture_id"],
                    "condition": result["condition"],
                    "cell": cell, "replicate": rep,
                    "attack_model": result.get("attack_model"),
                    "judge_model": result.get("judge_model"),
                    "ordinal": challenge["ordinal"],
                    "run_id": result.get("run_id"),
                    **{field: challenge.get(field) for field in JUDGE_FIELDS
                       if field in challenge},
                }
    rng = random.Random(seed)
    for fixture_id in pool:
        rng.shuffle(pool[fixture_id])
    return pool, key


def emit(run_dirs, out_dir, seed, dropped=False):
    pool, key = (collect_dropped if dropped else collect)(run_dirs, seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifests = {home.name: json.loads((home / "fixture.json").read_text())
                 for home in sorted(FIXTURES.iterdir()) if home.is_dir()}

    readable = [
        "# Blind adjudication worksheet",
        "",
        "For each fixture below you are given its **registered vulnerability** and a",
        "shuffled pool of every challenge raised against that fixture across every run.",
        "",
        "**You are not told** which condition (unmodified or altered) produced a",
        "challenge, which models wrote or judged it, or what the judge thought of it.",
        "That is deliberate: those labels are what bias a long run of judgments.",
        "",
        "For each challenge, decide one thing: **does it name the registered",
        "vulnerability?** Naming the underlying proposition is enough — it does not have",
        "to use the same words, and it does not count if it merely notices that",
        "something is missing without saying what.",
        "",
        "Record answers in `worksheet.yaml`. Do not open `KEY.json`.",
        "",
    ]
    sheet = {"seed": seed, "adjudicated_by": "", "adjudicated_on": "", "answers": {}}

    for fixture_id, challenges in sorted(pool.items()):
        mutation = manifests[fixture_id]["mutation"]
        readable += [
            "---", "",
            f"## {fixture_id} — {len(challenges)} challenges pooled",
            "",
            "**The registered vulnerability:**", "",
            "> " + mutation["gold_vulnerability"].strip().replace("\n", "\n> "),
            "",
        ]
        if mutation["type"] == "record_support":
            readable += [
                "*This fixture's claim turns on the attached record. The record is in*",
                f"*`fixtures/{fixture_id}/normalized/attachments/`.*", "",
            ]
        for item in challenges:
            readable += [
                f"### `{item['id']}`  ({item['category']})",
                "",
                item["argument"] or "*(no argument text)*",
                "",
            ]
            if item["why_it_matters"]:
                readable.append(f"*Why it matters:* {item['why_it_matters']}")
                readable.append("")
            if item["anchored_at"]:
                readable.append(f"*Anchored at:* `{item['anchored_at'][:160]}`")
                readable.append("")
            sheet["answers"][item["id"]] = ""

        readable.append("")

    (out_dir / "WORKSHEET.md").write_text("\n".join(readable))
    (out_dir / "worksheet.yaml").write_text(
        "# Answer each with: yes | no | unsure\n"
        "# yes = this challenge names the registered vulnerability for its fixture.\n"
        f"seed: {seed}\n"
        "adjudicated_by: \"\"\n"
        "adjudicated_on: \"\"\n"
        "answers:\n"
        + "".join(f"  {cid}: \"\"\n" for cid in sheet["answers"])
    )
    (out_dir / "KEY.json").write_text(json.dumps(key, indent=2))

    print(f"wrote blind worksheet to {out_dir}")
    print(f"  fixtures: {len(pool)}   challenges pooled: {sum(len(v) for v in pool.values())}")
    for fixture_id, challenges in sorted(pool.items()):
        print(f"    {fixture_id}: {len(challenges)}")
    print(f"  seed {seed}; KEY.json written separately — do not read it while adjudicating")


def score(worksheet_path, key_path, out_path):
    filled = yaml.safe_load(Path(worksheet_path).read_text())
    key = json.loads(Path(key_path).read_text())
    answers = filled.get("answers") or {}

    runs, unanswered = {}, []
    for cid, entry in key.items():
        answer = str(answers.get(cid, "")).strip().lower()
        if answer not in ("yes", "no", "unsure"):
            unanswered.append(cid)
            continue
        run_key = (entry["cell"], entry["fixture_id"], entry["condition"])
        row = runs.setdefault(run_key, {
            "cell": entry["cell"], "fixture_id": entry["fixture_id"],
            "condition": entry["condition"], "attack_model": entry["attack_model"],
            "judge_model": entry["judge_model"], "challenges": 0,
            "target_detected": False, "matched": [],
        })
        row["challenges"] += 1
        if answer == "yes":
            row["target_detected"] = True
            row["matched"].append({"id": cid, "ordinal": entry["ordinal"]})

    # The parent study's four-cell paired outcome, per cell. A pair needs both
    # of its runs adjudicated; a fixture with only one is left out and named.
    paired, incomplete = [], []
    by_pair = {}
    for row in runs.values():
        by_pair.setdefault((row["cell"], row["fixture_id"]), {})[row["condition"]] = row
    for (cell, fixture_id), sides in sorted(by_pair.items()):
        if "control" not in sides or "mutant" not in sides:
            incomplete.append(f"{cell}/{fixture_id}")
            continue
        control = int(sides["control"]["target_detected"])
        mutant = int(sides["mutant"]["target_detected"])
        outcome, meaning = OUTCOMES[(control, mutant)]
        paired.append({
            "cell": cell, "fixture_id": fixture_id,
            "control": control, "mutant": mutant,
            "outcome": outcome, "meaning": meaning,
            "attack_model": sides["mutant"]["attack_model"],
            "judge_model": sides["mutant"]["judge_model"],
        })

    counts = {}
    for row in paired:
        counts.setdefault(row["cell"], {name: 0 for name, _ in OUTCOMES.values()})
        counts[row["cell"]][row["outcome"]] += 1

    result = {
        "adjudicated_by": filled.get("adjudicated_by") or "(unrecorded)",
        "adjudicated_on": filled.get("adjudicated_on") or "(unrecorded)",
        "seed": filled.get("seed"),
        "unanswered": unanswered,
        "pairs_incomplete": incomplete,
        "four_cell_counts_by_cell": counts,
        "pairs": paired,
        "runs": sorted(runs.values(), key=lambda r: (r["cell"], r["fixture_id"], r["condition"])),
        "note": "Counts, not rates. non_discriminating is not a failure of the Gym: "
                "it means the defect was already flagged in the unmodified brief, so "
                "that pair shows nothing about sensitivity.",
    }
    Path(out_path).write_text(json.dumps(result, indent=2) + "\n")
    print(f"unblinded {len(runs)} runs -> {out_path}\n")
    print(f"{'cell':<10} {'fixture':<8} {'control':>8} {'mutant':>7}  outcome")
    for row in paired:
        print(f"{row['cell']:<10} {row['fixture_id']:<8} {row['control']:>8} "
              f"{row['mutant']:>7}  {row['outcome']}")
    for cell, cell_counts in sorted(counts.items()):
        print(f"\n  {cell}: " + ", ".join(f"{k}={v}" for k, v in cell_counts.items()))
    if incomplete:
        print(f"\n  incomplete pairs: {', '.join(incomplete)}")
    if unanswered:
        print(f"  {len(unanswered)} challenge(s) unanswered")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", nargs="+", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--emit", action="store_true")
    group.add_argument("--score", action="store_true")
    parser.add_argument("--out-dir", default=str(EXPERIMENT / "adjudication-2x2"))
    parser.add_argument("--seed", type=int, default=20260909)
    parser.add_argument("--fixtures-dir", help="fixture tree; defaults to the subtle tier")
    parser.add_argument("--dropped", action="store_true",
                        help="pool the attacks the judge discarded, not the kept challenges")
    args = parser.parse_args()

    global FIXTURES
    if args.fixtures_dir:
        FIXTURES = Path(args.fixtures_dir).resolve()
    out_dir = Path(args.out_dir)
    if args.emit:
        emit(args.run_dir, out_dir, args.seed, dropped=args.dropped)
    else:
        score(out_dir / "worksheet.yaml", out_dir / "KEY.json", out_dir / "detection.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

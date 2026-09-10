"""How much do the headline numbers move between identical runs?

Temperature is 0 and every input is byte-identical across replicates, so
anything that differs is provider-side nondeterminism. That is not a nuisance
to be averaged away: if a finding moves more between two identical runs than it
does between two cells, the finding is noise and the 2x2 needs error bars before
anything is claimed from it.

Each replicate is an independent measurement of the same cell. Reported as
mean, spread and range across replicates, alongside the between-cell spread the
finding rests on -- the comparison that decides whether the finding survives.
"""

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse_2x2 import load, survival, verdicts  # noqa: E402

CELLS = ["baseline", "gpt-gpt", "ds-ds", "gpt-ds", "ds-gpt"]


def spread(values):
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicate", nargs="+", required=True,
                        help="one glob per replicate, e.g. 'results/2026-09-09b-*'")
    args = parser.parse_args()

    per_replicate = []
    for index, pattern in enumerate(args.replicate):
        dirs = sorted(Path(".").glob(pattern))
        runs = load([str(d) for d in dirs])
        rows = survival(runs)
        by_cell = defaultdict(list)
        for row in rows:
            by_cell[row["cell"]].append(row)
        per_replicate.append({
            "label": f"R{index + 1}",
            "runs": len(runs),
            "keep": {c: statistics.fmean([r["rate"] for r in v]) for c, v in by_cell.items()},
            "answer": {c: statistics.fmean([r["answered_rate"] for r in v]) for c, v in by_cell.items()},
            "keep_mut": {c: statistics.fmean([r["rate"] for r in v if r["condition"] == "mutant"])
                         for c, v in by_cell.items()},
        })

    print(f"{len(per_replicate)} independent measurements of each cell "
          f"({sum(r['runs'] for r in per_replicate)} runs total)\n")

    for measure, title in [("keep", "KEEP RATE"), ("answer", "ANSWER RATE"),
                           ("keep_mut", "KEEP RATE, ALTERED BRIEFS ONLY")]:
        print(f"== {title} ==")
        header = "".join(f"{r['label']:>8}" for r in per_replicate)
        print(f"{'cell':<10}{header} {'mean':>8} {'sd':>7} {'range':>15}")
        cell_means = {}
        for cell in CELLS:
            values = [r[measure].get(cell) for r in per_replicate if cell in r[measure]]
            if not values:
                continue
            cell_means[cell] = statistics.fmean(values)
            cells = "".join(f"{v:>8.3f}" for v in values)
            print(f"{cell:<10}{cells} {statistics.fmean(values):>8.3f} {spread(values):>7.3f} "
                  f"{min(values):>7.3f}-{max(values):<7.3f}")
        within = statistics.fmean([
            spread([r[measure][c] for r in per_replicate if c in r[measure]])
            for c in cell_means
        ])
        between = spread(list(cell_means.values()))
        verdict = ("signal: cells differ by more than runs do" if between > 2 * within
                   else "CAUTION: between-cell differences are within run-to-run noise")
        print(f"\n  within-cell sd (run to run) : {within:.3f}")
        print(f"  between-cell sd             : {between:.3f}   ratio {between / within:.1f}x")
        print(f"  -> {verdict}\n")

    # Two ratios, because "own-family preference" is ambiguous and the two
    # readings gave opposite answers on the first run. Holding the JUDGE fixed
    # asks whether that judge favours its own family's attacks -- the
    # self-preference question. Holding the ATTACKER fixed asks whether those
    # attacks fare better before their own family -- which also moves when one
    # judge is simply harsher than the other.
    def ratio(numerator, denominator):
        return [(r["keep"][numerator] / r["keep"][denominator])
                if r["keep"].get(denominator) else float("nan") for r in per_replicate]

    def line(label, values):
        finite = [v for v in values if v == v]
        tail = (f"  mean {statistics.fmean(finite):.2f}, "
                f"range {min(finite):.2f}-{max(finite):.2f}") if finite else ""
        print(f"{label:<46}" + "".join(f"{v:>8.2f}" for v in values) + tail)

    print("== SELF-PREFERENCE: judge fixed, attacker varied ==")
    print(f"{'':<46}" + "".join(f"{r['label']:>8}" for r in per_replicate))
    line("gpt-5.6-sol judge: own attacks / other", ratio("gpt-gpt", "ds-gpt"))
    line("deepseek judge: own attacks / other", ratio("ds-ds", "gpt-ds"))
    print("  Above 1 = this judge keeps more of its own family's attacks.\n")

    print("== ATTACK FATE: attacker fixed, judge varied ==")
    print(f"{'':<46}" + "".join(f"{r['label']:>8}" for r in per_replicate))
    line("gpt-5.6-sol attacks: own judge / other", ratio("gpt-gpt", "gpt-ds"))
    line("deepseek attacks: own judge / other", ratio("ds-ds", "ds-gpt"))
    print("  Above 1 = these attacks survive better before their own family.\n")

    print("== OTHER HEADLINES ==")
    print(f"{'':<46}" + "".join(f"{r['label']:>8}" for r in per_replicate))
    line("sequencing: gpt-ds / ds-gpt", ratio("gpt-ds", "ds-gpt"))
    values = [r["keep_mut"].get("ds-gpt", float("nan")) for r in per_replicate]
    print(f"{'ds-gpt keep rate, altered briefs':<46}" + "".join(f"{v:>8.3f}" for v in values)
          + f"  mean {statistics.fmean(values):.3f}, range {min(values):.3f}-{max(values):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

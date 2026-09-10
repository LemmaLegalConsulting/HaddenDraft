"""Emit the results tables as LaTeX, across all four replicates.

Generated rather than hand-written so the paper cannot drift from the runs.
Every figure traces to a report.json under the replicate globs passed in.

Each cell was measured four times under identical inputs at temperature 0, so
every number here is a mean over four independent measurements and carries its
spread. The first version of this file reported single-run point estimates and
three of them were the extreme of their range; that is the reason for the
`\\pm` columns and for Table~\\ref{tab:stability}, which exists to say when a
between-cell difference is larger than the difference between two identical runs
and when it is not.

Requires booktabs.
"""

import argparse
import collections
import itertools
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse_2x2 import fell_out, load, survival, verdicts  # noqa: E402

CELLS = ["baseline", "gpt-gpt", "ds-ds", "gpt-ds", "ds-gpt"]
TWOBY2 = ["gpt-gpt", "ds-ds", "gpt-ds", "ds-gpt"]
LABEL = {
    "baseline": r"\textsc{base}",
    "gpt-gpt": r"\textsc{g}$\rightarrow$\textsc{g}",
    "ds-ds": r"\textsc{d}$\rightarrow$\textsc{d}",
    "gpt-ds": r"\textsc{g}$\rightarrow$\textsc{d}",
    "ds-gpt": r"\textsc{d}$\rightarrow$\textsc{g}",
}


def mean(v):
    return statistics.fmean(v) if v else float("nan")


def sd(v):
    return statistics.stdev(v) if len(v) > 1 else 0.0


def pm(values, places=3):
    """mean $\\pm$ sd, the form every headline number takes here."""
    if not values:
        return "--"
    return rf"{mean(values):.{places}f}\,$\pm$\,{sd(values):.{places}f}"


def top3_signature(run):
    top = sorted(run.get("challenges", []), key=lambda c: c.get("importance", 0), reverse=True)[:3]
    return {(c.get("category", ""), ((c.get("target") or {}).get("unitId") or "")) for c in top}


def jaccard(a, b):
    union = a | b
    return len(a & b) / len(union) if union else None


def table(caption, label, spec, header, rows, note=None):
    out = [r"\begin{table}[t]", r"\centering", r"\small",
           rf"\caption{{{caption}}}", rf"\label{{{label}}}",
           rf"\begin{{tabular}}{{{spec}}}", r"\toprule"]
    out += header + [r"\midrule"] + rows + [r"\bottomrule", r"\end{tabular}"]
    if note:
        out.append(rf"\vspace{{2pt}}\footnotesize {note}")
    out += [r"\end{table}", ""]
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicate", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--compact", action="store_true",
                        help="one single-column table with the findings that carry the paper")
    args = parser.parse_args()

    reps = []
    for pattern in args.replicate:
        dirs = sorted(Path(".").glob(pattern))
        runs = load([str(d) for d in dirs])
        reps.append({"runs": runs, "survival": survival(runs),
                     "sig": {(r["cell"], r["fixture_id"], r["condition"]): top3_signature(r)
                             for r in runs}})
    n_reps = len(reps)
    all_runs = [r for rep in reps for r in rep["runs"]]

    def per_rep(cell, field, condition=None):
        """One value per replicate: that replicate's mean for this cell."""
        out = []
        for rep in reps:
            rows = [r for r in rep["survival"] if r["cell"] == cell
                    and (condition is None or r["condition"] == condition)]
            if rows:
                out.append(mean([r[field] for r in rows]))
        return out

    # ---- compact: one table, one column, the findings that carry the paper ----
    if args.compact:
        def rate(cell, field="rate", condition=None):
            return per_rep(cell, field, condition)

        def ratio_series(num, den):
            return [mean(per_rep(num, "rate")[i:i+1]) / mean(per_rep(den, "rate")[i:i+1])
                    for i in range(n_reps)]

        def band(series):
            return rf"{mean(series):.2f}\,[{min(series):.2f}--{max(series):.2f}]"

        judge_gpt, judge_ds = [], []
        for rep in reps:
            judge_gpt.append(mean([r["answered_rate"] for r in rep["survival"]
                                   if r["cell"] in ("gpt-gpt", "ds-gpt")]))
            judge_ds.append(mean([r["answered_rate"] for r in rep["survival"]
                                  if r["cell"] in ("gpt-ds", "ds-ds")]))

        within_j, between_j = [], []
        for i, j in itertools.combinations(range(n_reps), 2):
            for key in reps[i]["sig"]:
                if key in reps[j]["sig"]:
                    v = jaccard(reps[i]["sig"][key], reps[j]["sig"][key])
                    if v is not None:
                        within_j.append(v)
        for rep in reps:
            for fixture, condition in {(f, c) for (_, f, c) in rep["sig"]}:
                for left, right in itertools.combinations(TWOBY2, 2):
                    a, b = rep["sig"].get((left, fixture, condition)), rep["sig"].get((right, fixture, condition))
                    if a is not None and b is not None:
                        v = jaccard(a, b)
                        if v is not None:
                            between_j.append(v)

        n_docs = max((len([r for r in reps[0]["survival"] if r["cell"] == c]) for c in TWOBY2),
                     default=0)
        keep_sd = mean([sd(per_rep(c, "rate")) for c in TWOBY2])
        keep_between = sd([mean(per_rep(c, "rate")) for c in TWOBY2])

        sec = lambda s: rf"\multicolumn{{2}}{{@{{}}l}}{{\itshape {s}}} \\"
        rows = [
            sec("Attacks kept, by pairing"),
            rf"\quad \textsc{{g}}$\rightarrow$\textsc{{g}} & {pm(rate('gpt-gpt'))} \\",
            rf"\quad \textsc{{d}}$\rightarrow$\textsc{{d}} & {pm(rate('ds-ds'))} \\",
            rf"\quad \textsc{{g}}$\rightarrow$\textsc{{d}} & {pm(rate('gpt-ds'))} \\",
            rf"\quad \textsc{{d}}$\rightarrow$\textsc{{g}} & {pm(rate('ds-gpt'))} \\",
            r"\addlinespace",
            sec("Attacks the judge answered on"),
            rf"\quad \textsc{{gpt-5.6-sol}} & {pm(judge_gpt)} \\",
            rf"\quad \textsc{{deepseek-v4-pro}} & {pm(judge_ds)} \\",
            r"\addlinespace",
            sec("Self-preference: own attacks / other"),
            rf"\quad \textsc{{gpt-5.6-sol}} judge & {band(ratio_series('gpt-gpt', 'ds-gpt'))} \\",
            rf"\quad \textsc{{deepseek-v4-pro}} judge & {band(ratio_series('ds-ds', 'gpt-ds'))} \\",
            r"\addlinespace",
            sec("Top-3 agreement (Jaccard)"),
            rf"\quad same pairing, re-run & {mean(within_j):.3f} \\",
            rf"\quad different pairing & {mean(between_j):.3f} \\",
            r"\addlinespace",
            sec("Keep rate: variation"),
            rf"\quad between two identical runs & {keep_sd:.3f} \\",
            rf"\quad between pairings & {keep_between:.3f} \\",
        ]
        out = table(
            rf"Cross-model judging: {n_reps} identical runs of {n_docs} documents "
            r"per pairing. \textsc{g}~=~\textsc{gpt-5.6-sol}, "
            r"\textsc{d}~=~\textsc{deepseek-v4-pro}; \textsc{x}$\rightarrow$\textsc{y} "
            r"is attacker~\textsc{x}, judge~\textsc{y}. Rates are mean~$\pm$~s.d.\ "
            r"across runs; ratios are mean~[range].",
            "tab:results", "@{}lr@{}",
            [r"& Mean \\"], rows,
            note=r"An unanswered attack is dropped by the pipeline, so the answer rate "
                 r"is a rejection rate in disguise. The top-3 rows are the study's "
                 r"negative result: re-running one pairing disagrees with itself as "
                 r"much as two pairings disagree with each other.")
        header = [
            "% Generated by tools/latex_tables.py --compact -- do not edit by hand.",
            f"% {n_reps} replicates, {len(all_runs)} runs. Single-column width.",
            r"% Requires: \usepackage{booktabs}",
            "",
        ]
        Path(args.out).write_text("\n".join(header + out))
        print(f"wrote {args.out}  (1 table, single-column)")
        return 0

    body = [
        "% Generated by tools/latex_tables.py -- do not edit by hand.",
        f"% {n_reps} independent measurements of every cell, {len(all_runs)} runs.",
        r"% Requires: \usepackage{booktabs}",
        "%",
        r"% G = gpt-5.6-sol, D = deepseek-v4-pro, BASE = gpt-5.4-mini (also the",
        r"% model every non-treatment stage runs on, held constant across cells).",
        r"% X$\rightarrow$Y means attacker X, judge Y.",
        "",
    ]

    # ---- 1. survival ------------------------------------------------------
    rows = []
    for cell in CELLS:
        keep_c, keep_m = per_rep(cell, "rate", "control"), per_rep(cell, "rate", "mutant")
        ans = per_rep(cell, "answered_rate")
        if not keep_c:
            continue
        rows.append(f"{LABEL[cell]} & {pm(keep_c)} & {pm(keep_m)} & {pm(per_rep(cell,'rate'))} & {pm(ans)} \\\\")
    body += table(
        rf"Attack survival, mean $\pm$ s.d.\ over {n_reps} identical runs. "
        r"\emph{Answered} is the share of attacks the judge returned any assessment on; "
        r"the pipeline treats an unanswered attack as rejected, so silence is a rejection.",
        "tab:survival", "lcccc",
        [r"Cell & Keep, control & Keep, altered & Keep, all & Answered \\"],
        rows)

    # ---- 2. marginals by seat --------------------------------------------
    seats = [
        (r"Judge \textsc{gpt-5.6-sol}", ["gpt-gpt", "ds-gpt"]),
        (r"Judge \textsc{deepseek-v4-pro}", ["gpt-ds", "ds-ds"]),
        (r"Attacker \textsc{gpt-5.6-sol}", ["gpt-gpt", "gpt-ds"]),
        (r"Attacker \textsc{deepseek-v4-pro}", ["ds-ds", "ds-gpt"]),
    ]
    rows = []
    for name, cells in seats:
        keep, ans = [], []
        for rep in reps:
            sel = [r for r in rep["survival"] if r["cell"] in cells]
            keep.append(mean([r["rate"] for r in sel]))
            ans.append(mean([r["answered_rate"] for r in sel]))
        rows.append(f"{name} & {pm(keep)} & {pm(ans)} \\\\")
        if name.startswith("Judge") and "deepseek" in name:
            rows.append(r"\addlinespace")
    body += table(
        r"Marginals by seat. The judges differ far more in how much they "
        r"\emph{answer} than in how much they keep, and the answer rates are the "
        r"most stable quantities in the study.",
        "tab:marginals", "lcc",
        [r"Seat & Keep rate & Answer rate \\"], rows)

    # ---- 3. the two own-family ratios ------------------------------------
    def ratio_series(num, den):
        return [mean(per_rep(num, "rate")[i:i+1]) / mean(per_rep(den, "rate")[i:i+1])
                for i in range(n_reps)]

    ratios = [
        (r"\textsc{g} judge: own attacks / other", "gpt-gpt", "ds-gpt"),
        (r"\textsc{d} judge: own attacks / other", "ds-ds", "gpt-ds"),
        (r"\textsc{g} attacks: own judge / other", "gpt-gpt", "gpt-ds"),
        (r"\textsc{d} attacks: own judge / other", "ds-ds", "ds-gpt"),
    ]
    rows = []
    for index, (name, num, den) in enumerate(ratios):
        series = ratio_series(num, den)
        cols = " & ".join(f"{v:.2f}" for v in series)
        rows.append(f"{name} & {cols} & {mean(series):.2f} & {min(series):.2f}--{max(series):.2f} \\\\")
        if index == 1:
            rows.append(r"\addlinespace")
    body += table(
        r"Own-family preference, both readings. Holding the \emph{judge} fixed asks "
        r"whether a judge favours its own family's attacks; holding the "
        r"\emph{attacker} fixed asks whether those attacks fare better before their "
        r"own family, which also moves when one judge is simply harsher. Only "
        r"\textsc{gpt-5.6-sol} shows self-preference; \textsc{deepseek-v4-pro} shows "
        r"none, sitting at or below parity in every run.",
        "tab:ownfamily", "l" + "c" * n_reps + "cc",
        [r"Ratio & " + " & ".join(f"R{i+1}" for i in range(n_reps)) + r" & Mean & Range \\"],
        rows,
        note=r"Above 1 favours the own-family pairing. Each column is one complete "
             r"re-run of all 16 documents in each cell.")

    # ---- 4. stability -----------------------------------------------------
    rows = []
    for field, name in [("rate", "Keep rate"), ("answered_rate", "Answer rate")]:
        cell_means, withins = {}, []
        for cell in TWOBY2:
            series = per_rep(cell, field)
            cell_means[cell] = mean(series)
            withins.append(sd(series))
        within, between = mean(withins), sd(list(cell_means.values()))
        rows.append(f"{name} & {within:.3f} & {between:.3f} & {between/within:.1f}$\\times$ \\\\")
    # top-3, both directions
    within_j, between_j = [], []
    for i, j in itertools.combinations(range(n_reps), 2):
        for key in reps[i]["sig"]:
            if key in reps[j]["sig"]:
                v = jaccard(reps[i]["sig"][key], reps[j]["sig"][key])
                if v is not None:
                    within_j.append(v)
    for rep in reps:
        docs = {(f, c) for (_, f, c) in rep["sig"]}
        for fixture, condition in docs:
            for left, right in itertools.combinations(TWOBY2, 2):
                a, b = rep["sig"].get((left, fixture, condition)), rep["sig"].get((right, fixture, condition))
                if a is not None and b is not None:
                    v = jaccard(a, b)
                    if v is not None:
                        between_j.append(v)
    body += table(
        r"Is a between-cell difference bigger than the difference between two "
        r"identical runs? For the rates, yes. For the top three challenges, no.",
        "tab:stability", "lccc",
        [r"Measure & Within-cell & Between-cell & Ratio \\"],
        rows,
        note=r"Within-cell is the s.d.\ across the four identical runs of one cell, "
             r"averaged over cells; between-cell is the s.d.\ of the four cell means.")

    # ---- 5. top-3 agreement ----------------------------------------------
    rows = [
        rf"Same cell, different run & {mean(within_j):.3f} & {len(within_j)} \\",
        rf"Different cell, same run & {mean(between_j):.3f} & {len(between_j)} \\",
    ]
    body += table(
        r"Agreement on the three highest-importance challenges, by category and "
        r"anchored unit. Re-running one configuration disagrees with itself about "
        r"as much as two different configurations disagree with each other: the "
        r"top three are unstable, and that instability is not attributable to the "
        r"choice of models.",
        "tab:top3", "lcc",
        [r"Comparison & Mean Jaccard & $n$ \\"], rows,
        note=r"A Jaccard of 0.14 on a three-element set is roughly one shared item "
             r"in two documents.")

    # ---- 6. what falls out ------------------------------------------------
    dropped, kept, importances = collections.Counter(), collections.Counter(), {}
    drop_cat = collections.defaultdict(collections.Counter)
    imp = collections.defaultdict(lambda: {"kept": [], "dropped": []})
    for rep in reps:
        d, k, i = fell_out(rep["runs"])
        for cell in CELLS:
            dropped[cell] += sum(d[cell].values())
            kept[cell] += sum(k[cell].values())
            drop_cat[cell] += d[cell]
            imp[cell]["kept"] += i[cell]["kept"]
            imp[cell]["dropped"] += i[cell]["dropped"]
    rows = []
    for cell in CELLS:
        if not dropped[cell] and not kept[cell]:
            continue
        top = drop_cat[cell].most_common(1)
        top_label = f"{top[0][0].replace('_', chr(92) + '_')} ({top[0][1]})" if top else "--"
        rows.append(f"{LABEL[cell]} & {dropped[cell]} & {kept[cell]} & "
                    f"{mean(imp[cell]['kept']):.1f} & {mean(imp[cell]['dropped']):.1f} & {top_label} \\\\")
    body += table(
        rf"Attacks dropped by the judge, pooled over all {n_reps} runs, with the "
        r"judge's own importance scores. Every judge separates cleanly between what "
        r"it keeps and what it drops, so none is discarding at random.",
        "tab:fallout", "lrrrrl",
        [r"Cell & Dropped & Kept & \multicolumn{2}{c}{Mean importance} & Most-dropped \\",
         r" & & & Kept & Dropped & category \\"], rows)

    # ---- 7. verdicts ------------------------------------------------------
    pooled = collections.defaultdict(collections.Counter)
    for rep in reps:
        for cell, counts in verdicts(rep["runs"]).items():
            pooled[cell] += counts
    labels = ["serious", "answerable", "weak", "misplaced"]
    rows = [f"{LABEL[c]} & " + " & ".join(str(pooled[c][l]) for l in labels) + r" \\"
            for c in CELLS if c in pooled]
    body += table(
        rf"Judge verdicts on kept challenges, pooled over {n_reps} runs.",
        "tab:verdicts", "lrrrr",
        ["Cell & " + " & ".join(l.capitalize() for l in labels) + r" \\"], rows)

    # ---- 8. latency -------------------------------------------------------
    by_key = collections.defaultdict(list)
    for pattern in args.replicate:
        for directory in sorted(Path(".").glob(pattern)):
            for path in directory.glob("F00*/call-*.json"):
                call = json.loads(path.read_text())
                if call.get("status") == "complete" and call.get("elapsed_seconds") is not None:
                    role = "other" if call["role"] == "base" else call["role"]
                    by_key[(call["model"], role)].append(call["elapsed_seconds"])
    rows = []
    for (model, role), values in sorted(by_key.items()):
        values.sort()
        p90 = values[max(0, int(len(values) * 0.9) - 1)]
        rows.append(rf"\textsc{{{model}}} & {role} & {len(values)} & "
                    rf"{statistics.median(values):.1f} & {p90:.1f} & {max(values):.1f} \\")
    body += table(
        r"Per-call latency in seconds, pooled over every run. "
        r"\textsc{deepseek-v4-pro} is markedly slower on the opponent stage, the "
        r"largest prompt in the pipeline, and has a long tail.",
        "tab:latency", "llrrrr",
        [r"Model & Stage & $n$ & Median & p90 & Max \\"], rows)

    Path(args.out).write_text("\n".join(body))
    print(f"wrote {args.out}")
    print(f"  {n_reps} replicates, {len(all_runs)} runs, 8 tables")
    print(f"  top-3 Jaccard: within-cell {mean(within_j):.3f} (n={len(within_j)}), "
          f"between-cell {mean(between_j):.3f} (n={len(between_j)})")


if __name__ == "__main__":
    sys.exit(main())

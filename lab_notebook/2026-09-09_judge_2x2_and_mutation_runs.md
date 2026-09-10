# Run log: mutation baseline + cross-model judge 2×2 (2026-09-09)

**Registries** `lexis-mutation-2026-09` (REGISTER.md) and `lexis-judge-2x2-2026-09`
(REGISTER-2x2.md), both pre-registered before execution.
**Runs** 320 = 4 independent replicates × 5 model configurations × 8 fixtures × 2 conditions.
**Outcome** 318 complete, 2 degraded (transient provider faults, excluded).
**Status** the measures below need no adjudication and are final. Target
detection is **not** reported: it awaits blind human adjudication.

Corpus, fixtures and gold labels: `lexis_real_briefs/experiment/` (gitignored).

---

## 1. What ran

| Cell | Opponent stage | Judge stage | Every other stage |
|---|---|---|---|
| `baseline` | gpt-5.4-mini | gpt-5.4-mini | gpt-5.4-mini |
| `gpt-gpt` | gpt-5.6-sol | gpt-5.6-sol | gpt-5.4-mini |
| `ds-ds` | deepseek-v4-pro | deepseek-v4-pro | gpt-5.4-mini |
| `gpt-ds` | gpt-5.6-sol | deepseek-v4-pro | gpt-5.4-mini |
| `ds-gpt` | deepseek-v4-pro | gpt-5.6-sol | gpt-5.4-mini |

Temperature 0, reasoning `medium`, file-backed prompts, identical fixture bytes
by SHA-256, identical retrieval sources. Per-stage routing via
`tools/routing.py`, which reads the prompt key the runner already records; the
Gym is not modified to support it.

## 2. Three Gym defects were fixed before these runs

The first execution attempt was discarded entirely. Everything below is from the
repaired code (`backend/apps/argument_gym/`, tests in
`test_malformed_model_output.py`, 265 tests pass).

1. **`unhashable type: 'list'`** — every parser rejected an unrecognised
   `unitId` by testing set membership *before* type, so a model answering with a
   list killed the run with an error naming no field. One run died of it. Fixed
   with a `known(value, allowed)` helper applied at all seven membership sites.
2. **The record cap** — a hard-coded 6,000 characters per material, applied
   after every brief-side budget was satisfied, meant a 72,407-character exhibit
   bundle reached the model as 8% of itself. Replaced by
   `ARGUMENT_GYM_RECORD_BUDGET_CHARS` (default 150,000, shared across materials
   with a 6,000 floor), sized so the local corpus is read whole. The materials
   stage now records what it truncated.
3. **The exhibit boundary** — an inline "…See attached Exhibit 2." in a page's
   opening lines was read as the start of the attachments, reporting a 2-page
   brief for a 13-page filed motion. A page's opening must now look like a cover
   sheet, not a sentence.

All three reported success while degrading. That is the pattern worth carrying
forward from this corpus.

## 3. Survival: what the judge was given, answered on, and kept

The denominator is the attack list parsed out of the **judge's own prompt**, not
the opponent's output. Two things make the opponent's output wrong: the pipeline
appends checklist-derived attacks before the judge sees them, and an attack the
judge never mentions is treated as not kept — so silence is a drop and must not
be counted as selectivity.

| Cell | Cond | Given | Assessed | Unanswered | Dropped | Kept | keep% | answer% |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `baseline` | control | 49 | 46 | 3 | 8 | 38 | 0.792 | 0.958 |
| `baseline` | mutant | 47 | 47 | 0 | 15 | 32 | 0.682 | 1.000 |
| `gpt-gpt` | control | 79 | 79 | 0 | 37 | 42 | 0.544 | 1.000 |
| `gpt-gpt` | mutant | 79 | 79 | 0 | 48 | 31 | 0.385 | 1.000 |
| `ds-ds` | control | 65 | 35 | 30 | 0 | 35 | 0.590 | 0.590 |
| `ds-ds` | mutant | 63 | 46 | 17 | 7 | 39 | 0.632 | 0.763 |
| `gpt-ds` | control | 84 | 48 | 36 | 5 | 43 | 0.513 | 0.603 |
| `gpt-ds` | mutant | 75 | 49 | 26 | 3 | 46 | 0.608 | 0.655 |
| `ds-gpt` | control | 67 | 67 | 0 | 47 | 20 | 0.323 | 1.000 |
| `ds-gpt` | mutant | 58 | 58 | 0 | 50 | 8 | 0.122 | 1.000 |

### 3a. The two judges do different jobs

| Judge | keep% | **answer%** |
|---|---:|---:|
| gpt-5.6-sol | 0.343 | **1.000** |
| deepseek-v4-pro | 0.586 | **0.652** |

`deepseek-v4-pro` silently omits roughly a third of the attacks it is given.
When it does answer it rejects almost nothing: 7 explicit rejections in `ds-ds`
against 85 in `gpt-gpt`. Its apparent leniency is therefore mostly non-response,
not approval — a distinction the first version of this measure lost.

### 3b. Own-family preference is one-sided

"Own-family preference" has two readings, and the first version of this entry
conflated them. Holding the **judge** fixed asks whether that judge favours its
own family's attacks — the self-preference question. Holding the **attacker**
fixed asks whether those attacks fare better before their own family, which also
moves when one judge is simply harsher than the other.

Mean over four runs, with range:

| Ratio | R1 | R2 | R3 | R4 | Mean | Range |
|---|---:|---:|---:|---:|---:|---|
| gpt-5.6-sol judge: own attacks / other | 2.09 | 1.66 | 1.94 | 1.18 | **1.72** | 1.18–2.09 |
| deepseek judge: own attacks / other | 1.09 | 0.98 | 1.00 | 0.82 | **0.97** | 0.82–1.09 |
| gpt-5.6-sol attacks: own judge / other | 0.83 | 0.80 | 0.83 | 0.77 | 0.81 | 0.77–0.83 |
| deepseek attacks: own judge / other | 2.75 | 2.04 | 2.35 | 1.26 | 2.10 | 1.26–2.75 |

**Only gpt-5.6-sol shows self-preference**, and it is consistent in direction
though not in size. deepseek-v4-pro shows none: it sits at or below parity in
three of four runs. DeepSeek's attacks collapsing before a GPT judge is mostly
that judge being harsh, not DeepSeek's judge being generous.

**Sequencing:** `gpt-ds` keeps 0.581 ± 0.022, `ds-gpt` 0.285 ± 0.075 — a mean
ratio of 2.12 (range 1.54–2.52). Same two families, opposite seats.

**A correction.** The single-run version of this entry reported 2.75× for
gpt-5.6-sol's self-preference and 0.122 for the `ds-gpt` altered-brief keep
rate. Both were the extreme of their four-run range; the means are 1.72 and
0.220. The directions survive replication, the magnitudes do not, and no figure
from a single run should be quoted without its spread.

**What this still cannot settle:** whether gpt-5.6-sol's preference is
self-preference or discrimination — DeepSeek's attacks may simply be weaker.

### 3c. Condition effect

gpt-5.6-sol as judge keeps **fewer** attacks against the altered draft
(`gpt-gpt` 0.544→0.385; `ds-gpt` 0.323→0.122). deepseek-v4-pro as judge keeps
**more** (`ds-ds` 0.590→0.632; `gpt-ds` 0.513→0.608). The baseline also drops
(0.792→0.682). Directionally consistent within each judge, n=8 per cell.

## 4. What falls out

| Cell | Dropped | Kept | Mean importance kept | dropped |
|---|---:|---:|---:|---:|
| `baseline` | 23 | 70 | 71.7 | 12.1 |
| `gpt-gpt` | 85 | 73 | 76.8 | 23.4 |
| `ds-ds` | 7 | 74 | 74.5 | 8.6 |
| `gpt-ds` | 8 | 89 | 81.9 | 11.9 |
| `ds-gpt` | 97 | 28 | 80.9 | 27.8 |

Every judge separates cleanly on its own importance scale — kept attacks score
6–9× higher than dropped ones — so none is discarding at random.

Dropped categories, most common first:

- `baseline`: checklist 10, record_conflict 4, missing_element 2, remedy_scope 2, framing 2, legal_authority 2, factual_support 1
- `gpt-gpt`: missing_element 21, checklist 20, factual_support 12, legal_authority 12, framing 9, remedy_scope 7, procedural 4
- `ds-ds`: missing_element 2, framing 1, factual_support 1, legal_authority 1, procedural 1, record_conflict 1
- `gpt-ds`: factual_support 3, framing 3, missing_element 1, checklist 1
- `ds-gpt`: **legal_authority 35**, factual_support 19, checklist 16, missing_element 10, procedural 8, framing 4, remedy_scope 3, record_conflict 2

`ds-gpt` is the striking one: gpt-5.6-sol throws out DeepSeek's authority
arguments more than any other category, 35 of 97 drops.

## 5. Judge verdicts on kept challenges

| Cell | serious | answerable | weak | misplaced | none |
|---|---:|---:|---:|---:|---:|
| `baseline` | 23 | 30 | 18 | 2 | 0 |
| `gpt-gpt` | 36 | 34 | 5 | 1 | 0 |
| `ds-ds` | 44 | 19 | 11 | 1 | 1 |
| `gpt-ds` | **74** | 13 | 3 | 0 | 1 |
| `ds-gpt` | 13 | 19 | 16 | 3 | 0 |

`gpt-ds` calls 74 of 91 kept challenges "serious"; `ds-gpt` calls 13 of 51 so.
The same brief, the same fixtures, opposite seats.

## 6. Top-3 stability — the finding reversed under replication

The single-run version of this entry concluded that "which three issues an
advocate sees first is mostly determined by the model pairing." Replication
shows that is wrong, because it had no noise floor to compare against.

| Comparison | Mean Jaccard | n |
|---|---:|---:|
| **Same cell, different run** | **0.143** | 474 |
| Different cell, same run | 0.103 | 378 |

Re-running one configuration disagrees with itself about as much as two
different configurations disagree with each other. The top three are unstable,
and the instability is **not** attributable to the choice of models — it is
mostly run-to-run nondeterminism at temperature 0.

That is a stronger product finding than the one it replaces, and a worse one: an
advocate running the Gym twice on the same brief, with the same models, sees a
substantially different set of top priorities. A Jaccard of 0.14 on a
three-element set is roughly one shared item in two documents.

The general lesson is Table `tab:stability`'s reason for existing: a
between-condition difference means nothing until it is compared against the
difference between two identical runs. The keep and answer rates clear that bar
by 4–5×; the top three does not clear it at all.

## 7. Run-to-run stability

Four independent measurements of every cell, identical inputs, temperature 0.

| Measure | Within-cell s.d. | Between-cell s.d. | Ratio |
|---|---:|---:|---:|
| Keep rate | 0.038 | 0.152 | 4.0× |
| Answer rate | 0.034 | 0.160 | 4.7× |
| Top-3 agreement | — | — | **does not clear** (§6) |

Most and least stable quantities in the study:

- **Answer rate**: gpt-5.6-sol 1.000 ± 0.000 across all four runs; ds-gpt the
  same. deepseek-as-judge 0.692 ± 0.079. The 100% figures are exact in every run.
- **`ds-gpt` on altered briefs**: 0.220 ± 0.121, range 0.122–0.391. By far the
  least stable cell, and the one the sequencing finding leans on hardest. Any
  claim resting on it needs the error bar shown.

The two degraded runs were both in replicate 2 and both transient: a DeepSeek
`content_filter` on the F005 control judge call, and an HTTP 500 from
gpt-5.6-sol on the F004 control judge call. Both were caught by the degraded
guard rather than absorbed into the deterministic fallback and counted.

## 8. Cost

| Model | Stage | n | Median | p90 | Max |
|---|---|---:|---:|---:|---:|
| deepseek-v4-pro | opponent | 32 | 89.8s | 162.7s | 351.8s |
| deepseek-v4-pro | judge | 32 | 58.9s | 95.4s | 133.8s |
| gpt-5.6-sol | opponent | 32 | 51.7s | 60.0s | 62.6s |
| gpt-5.6-sol | judge | 32 | 50.2s | 63.7s | 77.3s |
| gpt-5.4-mini | opponent | 16 | 38.1s | 46.6s | 51.2s |
| gpt-5.4-mini | judge | 16 | 28.0s | 33.5s | 35.0s |
| gpt-5.4-mini | all other | 864 | 9.0s | 28.9s | 113.1s |

DeepSeek is ~1.7× slower than gpt-5.6-sol on the same opponent prompts and has a
much longer tail. If the families prove comparable on quality, this is a real
differentiator.

An infrastructure note: `gpt-5.6-sol` was deployed at capacity 10 (10,000 TPM)
while a single opponent or judge call here is 26,000–34,000 tokens, so no call
could fit. Raised to 250 with `az` on the user's instruction. The first launch,
made before this was understood, produced 429s that the pipeline absorbed into
its deterministic fallback while still reporting `complete`; those runs are in
`results/superseded-pre-fix/` and none is used.

## 9. Per-fixture challenge counts (control/mutant), first replicate

| Fixture | baseline | gpt-gpt | ds-ds | gpt-ds | ds-gpt |
|---|---|---|---|---|---|
| F001 | 5/3 | 5/3 | 3/4 | 3/6 | 5/3 |
| F002 | 5/5 | 6/6 | 6/6 | 7/7 | 3/3 |
| F003 | 3/3 | 7/3 | 3/3 | 4/5 | 3/3 |
| F004 | 6/7 | 5/5 | 6/5 | 7/7 | 4/3 |
| F005 | 5/5 | 5/6 | 4/7 | 7/7 | 3/3 |
| F006 | 6/4 | 6/4 | 4/7 | 6/7 | 3/3 |
| F007 | 5/5 | 3/3 | 3/5 | 3/5 | 3/3 |
| F008 | 3/3 | 6/3 | 7/3 | 7/3 | 3/3 |

## 10. What is deliberately not here

**Target detection**, and therefore the parent study's four-cell paired outcome.
Deciding whether a challenge names the registered vulnerability is a judgment,
and it is made across ten runs of each fixture differing by condition *and* by
model. The pooled blind worksheet (`adjudication-all/`, 367 challenges over 8
fixtures, seed 20260909) strips condition, cell, attacker, judge and every
judge-produced field, shuffles, and keeps the mapping in a separate key file.
Until it is answered by a person, nothing in this log speaks to whether the Gym
detects an introduced defect.

The fixtures themselves are also still unadjudicated: the mutations were drafted
by a language model (Claude Opus 5) and no attorney has answered the four
reviewer questions in `experiment/review/`.

## 11. Reproduction

```bash
S=lexis_real_briefs/experiment
for spec in baseline:gpt-5.4-mini:gpt-5.4-mini gpt-gpt:gpt-5.6-sol:gpt-5.6-sol \
            ds-ds:deepseek-v4-pro:deepseek-v4-pro gpt-ds:gpt-5.6-sol:deepseek-v4-pro \
            ds-gpt:deepseek-v4-pro:gpt-5.6-sol; do
  n=${spec%%:*}; r=${spec#*:}
  .venv/bin/python $S/tools/run_experiment.py --output-dir $S/results/2026-09-09b-$n \
    --live --cell $n --base-model gpt-5.4-mini \
    --attack-model "${r%%:*}" --judge-model "${r##*:}"
done
.venv/bin/python $S/tools/analyse_2x2.py --run-dir $S/results/2026-09-09b-{gpt-gpt,ds-ds,gpt-ds,ds-gpt}
.venv/bin/python $S/tools/blind_adjudication.py --emit --run-dir $S/results/2026-09-09b-*
```

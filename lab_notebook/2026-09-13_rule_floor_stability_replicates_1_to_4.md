# Rule-elements floor stability: replicates 1--4

Date: 2026-09-13

Branch: `feature-argument-gym-correctness-mode`

Frozen fixture corpus:
`lexis_real_briefs/experiment/fixtures-rule-floor-attorney-reviewed-20260913/`

## Question and frozen protocol

This follow-up tested whether the registered rule-element dispositions and the
seven additional control `MUST_FIX` findings from replicate 1 recur under
unchanged execution. Replicate 1 was retained as the first of four runs; three
new repetitions used the same fixtures, prompts, rule profiles, models, and
settings. No tuning occurred between runs.

- Check: `rule_elements` only.
- Opponent/base: `gpt-5.6-terra`, medium reasoning.
- Judge: `mistral-large-3` (different model family).
- Parallelism: ten isolated pair workers; control and mutant sequential within
  each worker.
- CourtListener: disabled in parallel children.
- Stable comparison unit: `checkId + targetId`, never generated prose.

Replicate 2's R002 mutant and replicate 4's R010 mutant each returned
`IncompleteJudgeBatch`. Both original failures were retained. Each failed
condition was replaced for substantive scoring by the corresponding condition
from one separately named, unchanged technical retry. The completed control
from each original pair remained the scored control. Thus 2/80 original
document runs (2.5%) degraded and required retry; all retry results completed.

## Results

| Replicate | Detection | Matched specificity | Exact control PASS | Paired success | Reversed | Extra control MF | Extra mutant MF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 10/10 | 10/10 | 8/10 | 10/10 | 0/10 | 7 | 6 |
| 2 | 10/10 | 9/10 | 9/10 | 9/10 | 0/10 | 8 | 6 |
| 3 | 8/10 | 10/10 | 9/10 | 8/10 | 0/10 | 4 | 7 |
| 4 | 9/10 | 10/10 | 9/10 | 9/10 | 0/10 | 7 | 8 |
| **Mean** | **9.25/10** | **9.75/10** | **8.75/10** | **9.00/10** | **0/10** | **6.50** | **6.75** |

Across the 40 pair repetitions, the checker detected 37/40 planted omissions,
kept the matched control target below `MUST_FIX` in 39/40, and satisfied both
conditions in 36/40. There were no reversed pairs. Sixteen of twenty registered
target-condition identities had the same three-way disposition on all four
runs. Collapsing `PASS` and `REVIEW` into the correctness floor's non-error
class raises exact identity stability to 17/20. Seven of ten pairs satisfied the
registered binary outcome on every run.

Variable registered identities were:

- R003 mutant: `MUST_FIX, MUST_FIX, REVIEW, MUST_FIX`;
- R005 mutant: `MUST_FIX, MUST_FIX, REVIEW, REVIEW`;
- R007 control: `REVIEW, PASS, PASS, PASS`; and
- R009 control: `REVIEW, MUST_FIX, REVIEW, REVIEW`.

The R007 variation does not cross the `MUST_FIX` floor. R003 and R005 show
false-negative instability at the floor; R009 shows false-positive instability.

## Recurrence of replicate 1's seven additional control findings

| Extra stable identity | `MUST_FIX` recurrence |
| --- | ---: |
| R001 / `notice_served` | 4/4 |
| R003 / `covered_breach` | 3/4 |
| R003 / `specific_act` | 4/4 |
| R003 / `termination_date` | 4/4 |
| R008 / `applicable_timing` | 3/4 |
| R008 / `covered_program` | 3/4 |
| R010 / `nonpayment_ground` | 3/4 |
| **Total recurrence** | **24/28 (85.7%)** |

These seven findings are therefore mostly systematic outputs, not independent
one-run noise. Recurrence does not establish legal correctness: they may be
valid additional omissions, overly demanding rule profiles, or globally
incomplete synthetic controls. That distinction requires substantive attorney
adjudication of the stable identities. R009 also produced two new extra
`MUST_FIX` findings in only one repetition (`grievance_advisement` and
`public_housing`), consistent with a correlated over-strict audit in that run.

## Interpretation

The experiment supports a strong but qualified floor claim: on these ten
attorney-approved synthetic pairs, the system usually detects the planted
element omission and almost always avoids a `MUST_FIX` at the same target in the
control. It does not yet support claiming deterministic outcomes. The observed
weakness is primarily boundary movement between `REVIEW` and `MUST_FIX`, plus a
2.5% original-run structured Judge failure rate that the harness correctly
marked degraded instead of silently scoring.

For reporting, keep registered target performance separate from global
cleanliness. Before treating the mean 6.5 extra control findings as false
positive noise, adjudicate their nine union identities; the seven originally
observed identities were highly recurrent and are more likely to expose
systematic fixture/profile scope than stochastic generation.

## Reproduction artifacts

Raw run directories are named
`heldout-rule-floor-llama-sol-attorney-reviewed-rep1-20260913` through `rep4`,
with separately named R002 and R010 technical-retry directories. The comparison
command is implemented in
`lexis_real_briefs/experiment/tools/score_rule_floor_stability.py`; it accepts
explicit per-condition replacement paths so degraded originals remain
auditable.

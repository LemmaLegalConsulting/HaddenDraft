# Held-out correctness experiment handoff

Date: 2026-09-13  
Branch: `feature-argument-gym-correctness-mode`  
Purpose: restart-safe instructions for attorney authoring and the first held-out
Argument Gym correctness experiment.

## What is ready

The source-controlled correctness pipeline, authority retrieval hardening,
verified legal-rule profiles, micro-run evidence, and corpus plan are on the
branch above. The private authoring workspace is:

`lexis_real_briefs/experiment/heldout-authoring-20260913/`

It is intentionally ignored by Git because it contains filed briefs. It has
eight proposed authentic-control / one-span-mutant pairs, reference authority,
an authoring card for each pair, a mutation register, a sequester audit, and a
validator/freezer. Closing this session will not remove it, but deleting or
recloning the working directory will. Do not commit or upload that directory.

Two proposed cases were rejected because their hashes occurred in prior Gym
runs. The replacements are Lee v. Wallace (H004) and Estate of Notarian (H007).
All eight final candidates are fresh with respect to the fixture/result hash
audit and test `authority_support`. No honest one-edit `rule_elements` omission
was available in these eight briefs; that check should receive a separately
held-out rule corpus rather than a forced mutation.

The working tree also contains unrelated/private work that this branch does not
claim: a modification to
`backend/apps/caselaw/management/commands/enrich_caselaw_metadata.py`, a modified
`private-content` checkout, `downloaded_opinions/`, and ignored raw experiment
results. Do not reset, clean, stash wholesale, or commit those items merely to
prepare this experiment. The runner records a code snapshot and working-tree
patch; before the study, confirm that no uncommitted changes touch Argument Gym,
source retrieval, prompts, or legal-rule content.

## Experimental question and fixed configuration

Primary question: can the redesigned `authority_support` test distinguish an
authentic legal proposition from a single, attorney-verified material
misstatement of the cited source?

The unit of analysis is the registered test identity, `checkId + targetId`, not
the wording or rank of a generated criticism. Use the same configuration for
every pair and replicate:

- Opponent/base: `gpt-5.6-terra`
- Judge: `mistral-large-3`
- Reasoning: `medium`
- Enabled check: `authority_support` only
- Expected control target: `PASS`
- Expected mutant target: `MUST_FIX`
- Opponent and Judge are different model families. DeepSeek is excluded because
  it omitted candidate rulings without adequate justification in qualification.
- Authority retrieval order is local knowledge base, official Ohio reported
  decisions, CAP, then rate-limited CourtListener only if still unresolved.
- A source that cannot be retrieved is `REVIEW`/unverifiable, never a fabricated
  `MUST_FIX`.

Do not modify prompts, pipeline code, source priority, models, reasoning, gold
labels, or mutations after looking at held-out output. A changed system is a new
experiment and needs a new versioned corpus/run name.

## Step 1 — author and verify the eight mutations

For H001 through H008:

1. Read `AUTHORING.md`.
2. Independently read the relevant passage under `reference/` and confirm both
   that the authentic proposition is supported and that the proposed altered
   proposition is clearly false or materially overstated. Confirm materiality.
3. Edit only `mutant/brief-to-edit.txt`, making the single prescribed span
   replacement. Do not normalize whitespace or change a citation.
4. Mark the two attorney boxes in `AUTHORING.md` and set
   `attorneyVerifiedControl` and `attorneyVerifiedMutant` to `true` in
   `mutation-register.json`. If either legal proposition is debatable, reject
   the fixture instead of weakening its label.

Run the mechanical check at any time:

```bash
python lexis_real_briefs/experiment/heldout-authoring-20260913/verify_authoring.py
```

Before editing it reports `READY_TO_AUTHOR`; a valid edit reports
`MUTATION_SHAPE_OK`; any collateral edit is rejected.

After all eight are legally verified, freeze once:

```bash
python lexis_real_briefs/experiment/heldout-authoring-20260913/verify_authoring.py \
  --freeze lexis_real_briefs/experiment/fixtures-heldout-authority-20260913
```

The command refuses an existing destination and refuses any missing sign-off or
non-exact edit. Preserve the frozen folder unchanged. Record its
`fixtures-index.json` with the experiment artifacts, but do not commit the
briefs.

## Step 2 — preflight without exposing the held-out briefs

Do not perform a trial Gym run on a held-out fixture. Running even one condition
is exposure. Before the experiment, use only deterministic checks:

```bash
git switch feature-argument-gym-correctness-mode
git status --short
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py test \
  apps.argument_gym.test_correctness \
  apps.sources.test_reported_decisions \
  apps.sources.test_courtlistener
python lexis_real_briefs/experiment/heldout-authoring-20260913/verify_authoring.py
```

Confirm the required model deployments and credentials through the normal local
configuration. Never copy API keys into a command, fixture, notebook, or result.
Confirm that the frozen index hashes still match the files before every
replicate. If code has changed since this handoff commit, record the exact commit
and treat it as a new frozen system version.

## Step 3 — run three independent replicates

Run each replicate into a new directory. The runner processes all eight controls
and mutants, keeps condition labels out of model inputs, stores each model
transcript, and refuses to overwrite output.

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/run_experiment.py \
  --output-dir lexis_real_briefs/experiment/results/heldout-authority-terra-mistral-rep1-20260914 \
  --fixtures-dir lexis_real_briefs/experiment/fixtures-heldout-authority-20260913 \
  --live \
  --attack-model gpt-5.6-terra \
  --judge-model mistral-large-3 \
  --base-model gpt-5.6-terra \
  --reasoning medium \
  --check authority_support \
  --cell terra-mistral
```

Repeat unchanged with `rep2` and `rep3` in the output directory name. Do not
reuse a directory. Do not interpret replicate 1 and then tune before replicates
2 and 3. If a provider call fails, retain that run, classify it as technical or
degraded, and rerun the exact fixed condition under a separately named directory;
never silently replace it.

Prior qualification pairs took about 1.9–2.6 minutes of model-call time each.
These briefs contain more citation targets, so allow roughly 25–45 minutes for
one sequential eight-pair replicate and up to 60 minutes for cold retrieval or
provider variance. Three replicates should usually take 75–135 minutes; reserve
about three hours. The first pass may populate lawful local caches and be slower.
CourtListener is a last resort and its 5/minute, 50/hour limit must remain in
effect.

## Step 4 — technical and hand review

For each replicate, render the review report:

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/inspect_correctness_run.py \
  lexis_real_briefs/experiment/results/heldout-authority-terra-mistral-rep1-20260914 \
  --context-window 128000 \
  --output-reserve 16000
```

Review all 16 `result.json` files and their referenced `call-*.json`
transcripts. A usable run must have:

- 16 completed, non-degraded results;
- `authority_support` recorded as run, not off or unable to run;
- the gold target present under the registered `checkId + targetId`;
- no missing or extra Judge candidate IDs;
- no blank Judge reasons;
- no adverse disposition without evidence references;
- no prompt exceeding the conservative context-window budget; and
- no claimed source mismatch based on an unresolved or partial source.

For every gold target, record the actual disposition. Also count every
additional `MUST_FIX` outside the registered mutation and manually classify it
as true, false, or indeterminate. Do not equate “not visible” with `PASS`; inspect
the saved correctness tests. If a target ID differs only because deterministic
unit numbering changed, document the source proposition/citation match before
mapping it. Never match on generated prose alone.

## Preregistered outcomes and interpretation

For each replicate report these integer counts out of eight:

- mutation detection: mutant gold target is `MUST_FIX`;
- matched specificity: control gold target is not `MUST_FIX` (also report exact
  `PASS` separately from `REVIEW`);
- paired discrimination: mutant is `MUST_FIX` and matched control is not;
- reversed pair: control is `MUST_FIX` and mutant is not;
- unresolved pair: the source/target could not be evaluated; and
- stability: identical gold-target disposition across all three replicates.

Also report additional `MUST_FIX` findings per document, source-resolution rate,
Judge-contract failures, degraded calls, and maximum conservative context use.

Predeclared interpretation bands for this small exploratory set:

- **Strong floor signal:** 8/8 mutation detection, 8/8 matched specificity,
  8/8 paired discrimination, zero reversals, median zero additional false
  `MUST_FIX` findings, and all eight pairs stable across three replicates.
- **Promising / proceed cautiously:** at least 7/8 mutation detection, at least
  7/8 matched specificity, at least 7/8 paired discrimination, zero reversals,
  no Judge-contract failures, and at least 7/8 pairs stable across replicates.
- **Not ready for a consistency claim:** 5/8 or fewer paired discriminations,
  any systematic source-resolution or context failure, repeated Judge-contract
  failure, more than one reversal, or material false-positive noise.

Six of eight is useful diagnostic evidence but below the predeclared “promising”
band. With only eight pairs, report counts and exact binomial confidence
intervals; do not claim general legal correctness, all Ohio law, or case-outcome
prediction. The experiment directly supports only citation-proposition support
for this sampled Ohio housing-brief stratum. Rule-element performance must be
reported from its separate synthetic qualification set until fresh human-held-
out element omissions exist.

## Draft paper language if the test succeeds

### Experimental setup

> We evaluated the frozen Argument Gym correctness pipeline on eight previously
> unexposed Ohio housing briefs. For each authentic brief, an attorney verified
> one material citation proposition and authored a minimal paired mutation that
> changed only that proposition into a clear misstatement of the cited source.
> The models received neither condition labels nor gold annotations. A
> GPT-5.6-Terra Opponent generated evidence-bounded authority challenges and a
> different-family Mistral Large 3 Judge adjudicated each candidate. We ran the
> authority-support check alone for three replicates. The primary unit was the
> disposition of the registered check-and-target identity, rather than textual
> similarity among generated comments.

### Results (replace brackets with observed counts)

> The Gym returned MUST_FIX for [x/8] planted authority misstatements and avoided
> MUST_FIX on [y/8] matched authentic propositions, yielding [z/8] correctly
> discriminated pairs and [r] reversals. Gold-target dispositions were identical
> across all three runs for [s/8] pairs. [n] runs were degraded, [c] Judge
> contract violations occurred, and the median number of additional false
> MUST_FIX findings was [m]. All prompts remained within the predeclared context
> budget. These results provide [strong/promising/insufficient] evidence that the
> constrained Opponent–Judge architecture can serve as a repeatable floor for
> detecting clear citation-support defects in this sample; they do not establish
> comprehensive brief correctness or predict litigation outcomes.

## Stop conditions and next work

Stop and preserve evidence if the frozen hashes change, a gold source is legally
ambiguous, any secret appears in an artifact, the selected check did not run, or
context auditing reports an overflow. Technical source failure is not a negative
legal judgment and must not be recoded as one.

After this authority experiment, construct a genuinely fresh, attorney-authored
rule-elements held-out set covering clear omissions from verified Ohio profiles.
Do not reuse the AI-authored qualification fixtures as final evidence. If this
study reveals a design flaw, document the result first; fix it only in a new
pipeline version and evaluate against new held-out material.

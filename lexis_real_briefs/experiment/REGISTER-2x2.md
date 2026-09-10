# Registered conditions — cross-model judge study (2×2)

**Registry ID** `lexis-judge-2x2-2026-09`
**Registered** 2026-09-09, **before any cell was run**
**Parent study** `lexis-mutation-2026-09` (REGISTER.md); same eight fixtures, same corpus
**Status** conditions frozen; analysis pre-specified; no cell executed at time of writing

---

## 1. Question

The parent study asks whether the Gym detects an introduced defect. This asks
something about the instrument instead:

> Does it matter **which** model writes the attacks and **which** judges them —
> and in particular, does a judge treat attacks from its own model family
> differently from attacks written by another family?

Three sub-questions, each with a pre-specified contrast (§4):

1. **Same-family judging.** Is an attack more likely to survive a judge of its
   own family than a judge of another?
2. **Sequencing.** With one family attacking and the other judging, does it
   matter which way round?
3. **What survives.** Which issues fall out altogether, how stable the top three
   are, and whether either depends on the condition of the brief.

---

## 2. Design

A 2×2 crossing **attack model** with **judge model**, run over every fixture in
both conditions.

| Cell | Attack (opponent stage) | Judge (judge stage) | Families |
|---|---|---|---|
| `gpt-gpt` | `gpt-5.6-sol` | `gpt-5.6-sol` | same (openai) |
| `ds-ds` | `deepseek-v4-pro` | `deepseek-v4-pro` | same (deepseek) |
| `gpt-ds` | `gpt-5.6-sol` | `deepseek-v4-pro` | cross |
| `ds-gpt` | `deepseek-v4-pro` | `gpt-5.6-sol` | cross |

4 cells × 8 fixtures × 2 conditions = **64 runs**.

### Held constant

Everything else, deliberately, so the design varies two factors rather than ten:

| | |
|---|---|
| Every other stage | `gpt-5.4-mini` — argument map, persuasion, record audit, research, rule elements, coach, assessment |
| Reasoning level | `medium` |
| Temperature | 0 |
| Prompts | the file catalog at the run's commit; no database override |
| Retrieval | same source ids, same local corpora |
| Fixture bytes | the same SHA-256s the parent study froze |

**How the routing works.** `Stage.run` renders its prompt immediately before
calling the client, and the runner already patches `render_prompt`; the prompt
key is recorded there and the client wrapper picks the model from it
(`tools/routing.py`). `argument_gym.opponent` → attack model,
`argument_gym.judge` → judge model, everything else → base. **The Gym is not
modified**; this uses a seam the runner already had.

### A confound, declared

The base model is `gpt-5.4-mini`, which is in the same family as one of the two
treatment models. So the argument map and record audit that the opponent reads
are always OpenAI-made. This is constant across all four cells, so it cannot
confound the **judge** contrast, which is the primary question and is measured
holding the attack model fixed (§4). It *could* flatter the OpenAI **attack**
model, and the attack-side comparison should be read with that in mind. A
neutral third family was rejected because it would trade a known, constant,
declared confound for an unknown one in the stage that builds the argument map
every other stage depends on.

---

## 3. Blinding

The parent study blinds the Gym: no fixture id, condition label, mutation class
or gold vulnerability reaches any prompt, and workspace and document titles
carry the filing's own name only. That is unchanged here.

**This study adds blinding of the analyst.** Whether a challenge "names the
registered vulnerability" is a judgment, and it is now being made across eight
runs of the same fixture that differ by condition *and* by model. An adjudicator
who can see which run produced a challenge can, without meaning to, hold the
flawed draft to a different standard than the unflawed one, or one model's prose
to a different standard than another's.

So `tools/blind_adjudication.py` builds the adjudication set as follows:

- challenges are **pooled per fixture** across all four cells and both
  conditions — the fixture is revealed, because the gold vulnerability is what
  the judgment is against, and nothing else is;
- each challenge is given an **opaque id** and the pool is **shuffled** with a
  recorded seed;
- **condition, cell, attack model and judge model are stripped**;
- the mapping from opaque id back to run is written to a **separate key file**
  that the scoring step reads and the adjudicator does not.

The adjudicator marks each challenge yes/no against that fixture's registered
vulnerability. Nothing else is asked of them. Unblinding happens only in
scoring, after the answers are frozen.

---

## 4. Pre-specified analysis

Fixed now, before any cell has run, so that no contrast is chosen after seeing
which one looks interesting.

### Primary — the judge contrast, attack held fixed

| Contrast | Cells | What it isolates |
|---|---|---|
| Judge effect on GPT attacks | `gpt-gpt` vs `gpt-ds` | same-family vs cross, identical attacks upstream |
| Judge effect on DeepSeek attacks | `ds-ds` vs `ds-gpt` | the same, mirrored |

**Same-family effect** = the diagonal (`gpt-gpt`, `ds-ds`) against the
off-diagonal (`gpt-ds`, `ds-gpt`). **Sequencing effect** = `gpt-ds` against
`ds-gpt`.

### Measures, per cell and per condition

1. **Survival rate** — attacks the opponent proposed, over attacks the judge
   kept. Recoverable only from the raw stage payloads, because a dropped attack
   never becomes a challenge row; the runner pulls both back into each result.
2. **What falls out** — the category, severity and importance distribution of
   dropped attacks, compared against kept ones.
3. **Top-3 stability** — the three highest-importance challenges, compared
   across cells for the same fixture and condition, by overlap and by rank
   agreement.
4. **Verdict distribution** — `serious` / `answerable` / `weak` / `misplaced`.
5. **Target detection** — from the blind adjudication, feeding the parent
   study's four-cell paired outcome, computed per cell.

### Reported as counts

Eight fixtures and two conditions per cell. Report distributions and per-fixture
tables, not rates with confidence intervals. A difference that shows up in one
fixture is an observation, not an effect.

### Stopping rule

All 64 runs execute regardless of what the early ones show. No cell is dropped,
extended or re-run on the basis of its results; a re-run happens only for a
technical failure, and is recorded as such.

---

## 5. What this cannot answer

- **F007's record-support gold label is unscoreable in any cell.** The Gym reads
  only the first 6,000 characters of an attached record (REGISTER.md §9), and
  F007's evidence begins at character 8,692. Its runs remain valid for survival,
  top-3 and verdict measures, which do not depend on that label, and are
  excluded from target-detection.
- **Model identity is by deployment name, not self-report.** Asked directly,
  `deepseek-v4-pro` said it was "GPT" and `DeepSeek-V4-Pro-Jack` said "Claude".
  Model self-identification is confabulated and is not evidence of anything; the
  Azure deployment name is the ground truth and is what every result records.
- **Two families, one member each.** "Same-family" here means one specific pair
  of deployments. It is not a claim about vendors in general.
- **The mutations were drafted by a language model** (Claude Opus 5) and remain
  unadjudicated by an attorney. Everything in the parent register's §4 and §8
  applies unchanged.

---

## 6. Execution incidents

Recorded because both changed what the run means, and both were invisible in the
run's own status field.

### The first launch was void, and said it was complete

All four cells were started in parallel. Three of them call `gpt-5.6-sol`, whose
Azure deployment was at **capacity 10 — 10,000 tokens per minute**, while a
single opponent or judge call on these briefs is **26,000–34,000 tokens**. One
call could not fit, let alone three cells' worth.

The calls returned HTTP 429. `Stage.run` catches a backend error and returns its
**deterministic fallback**, so every affected run still reported `status:
complete` with challenges attached — challenges produced by the fallback, not by
the model the cell exists to test. The `gpt-gpt` cell was, for its first runs,
testing neither of its models.

Two changes followed:

- **`RoutedCapture.degraded()`** now inspects the attack and judge calls of
  every run and marks it `status: degraded` when either failed, with the failing
  model and error recorded. Degraded runs are excluded by the analysis and the
  adjudication pooling, which both select on `status == "complete"`. A run whose
  stage under test fell back is an outage wearing a result's clothes, and it is
  now labelled as one rather than averaged in.
- **The deployment's capacity was raised from 10 to 250** (`az cognitiveservices
  account deployment create`, same model version `2026-07-09`, same
  `GlobalStandard` SKU — the SKU is priced per token, so this raises the rate
  ceiling and not the price). Verified by replaying the largest previously
  failed prompt, 135,928 characters: it now completes in 35 seconds. `az` was
  used with the user's explicit instruction to adjust the quota.

**No data from the void launch is used.** Those output directories were deleted
and all four cells restarted from scratch, so no cell mixes pre- and post-fix
runs.

### Cells run two at a time

`gpt-gpt` + `ds-ds` first, then `gpt-ds` + `ds-gpt`. Each batch puts exactly two
`gpt-5.6-sol` calls in flight per run-pair, so the raised ceiling is not
approached in bursts. Batching affects wall-clock time only: no cell's inputs,
models, prompts or seeds differ from the registered design, and the stopping
rule in §4 is unchanged.

---

## 7. Reproduction

```bash
for cell in "gpt-gpt:gpt-5.6-sol:gpt-5.6-sol" \
            "ds-ds:deepseek-v4-pro:deepseek-v4-pro" \
            "gpt-ds:gpt-5.6-sol:deepseek-v4-pro" \
            "ds-gpt:deepseek-v4-pro:gpt-5.6-sol"; do
  name=${cell%%:*}; rest=${cell#*:}; attack=${rest%%:*}; judge=${rest##*:}
  .venv/bin/python lexis_real_briefs/experiment/tools/run_experiment.py \
    --output-dir lexis_real_briefs/experiment/results/2026-09-09-2x2-$name \
    --live --cell "$name" --base-model gpt-5.4-mini \
    --attack-model "$attack" --judge-model "$judge"
done

.venv/bin/python lexis_real_briefs/experiment/tools/blind_adjudication.py --emit \
  --run-dir lexis_real_briefs/experiment/results/2026-09-09-2x2-*
.venv/bin/python lexis_real_briefs/experiment/tools/analyse_2x2.py \
  --run-dir lexis_real_briefs/experiment/results/2026-09-09-2x2-*
```

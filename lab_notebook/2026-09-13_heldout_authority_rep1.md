# Held-out authority-support replicate 1

Date: 2026-09-13  
Branch: `feature-argument-gym-correctness-mode`  
Frozen-system commit at launch: `5caf7d3`  
Artifact: `lexis_real_briefs/experiment/results/heldout-authority-terra-mistral-rep1-20260913/`

## Protocol

Eight attorney-approved authentic-control / one-span-mutant pairs were frozen
before model exposure. `gpt-5.6-terra` served as Opponent/base and
`mistral-large-3` as different-family Judge, with medium reasoning and only
`authority_support` enabled. Eight isolated pair workers ran concurrently;
control and mutant remained sequential within each worker. CourtListener was
disabled in workers to protect its account-wide low-rate quota. Local case law,
Ohio's reported-decision endpoint, CAP, and local statutory material remained
available.

The batch completed all 16 documents in 223.3 seconds wall time. The 102 model
calls totaled 898.4 seconds when concurrent elapsed times are summed.

## Preregistered target outcomes

| Fixture | Control | Mutant | Correctly discriminated? |
| --- | --- | --- | --- |
| H001 | PASS | MUST_FIX | yes |
| H002 | PASS | MUST_FIX | yes |
| H003 | REVIEW | REVIEW | no |
| H004 | REVIEW | REVIEW | no |
| H005 | PASS | MUST_FIX | yes |
| H006 | PASS | MUST_FIX | yes |
| H007 | REVIEW | REVIEW | no |
| H008 | PASS | MUST_FIX | yes |

Aggregate first-run results:

- mutation detection: 5/8;
- matched specificity (control target not MUST_FIX): 8/8;
- exact control PASS: 5/8;
- paired discrimination: 5/8;
- reversed pairs: 0/8; and
- unresolved/review pairs: 3/8.

This is below the preregistered promising band of at least 7/8 discrimination.
It is useful diagnostic evidence, but it does not support a claim that the tool
detects citation flaws consistently.

## Technical integrity

- Results completed and non-degraded: 16/16.
- Judge calls: 44.
- Missing candidate rulings: 0.
- Extra candidate rulings: 0.
- Blank Judge reasons: 0.
- Adverse rulings without evidence references: 0.
- Saved model transcripts: 102.
- Maximum conservative prompt estimate: 51,780 tokens.
- Prompts exceeding the 128,000-token window with a 16,000-token reserve: 0.

The Judge hardening and bounded-context design therefore held in this run. The
observed misses were not dropped Judge candidates or context overflow.

## Miss analysis

H003 (Boone Coleman, 2016-Ohio-628) remained REVIEW because the authority text
was not attached to the registered target, even though the broader free-source
fallback reported resolving Ohio opinions. H004 remained REVIEW because R.C.
5321.01 was not retrieved as authority text. H007 (Estate of Jacob,
2005-Ohio-4998) remained REVIEW because the citation/source chain was not
resolved cleanly and the mutant was also treated as nested attribution.

Those are retrieval/target-association failures under the frozen system, not
evidence that the altered propositions were legally acceptable. Fail-closed
behavior worked: the system returned REVIEW rather than manufacturing a defect.
They nevertheless count as failed mutation detections in the registered study.

Across the controls there were 12 other MUST_FIX findings, and across the
mutants there were 10 other MUST_FIX findings after excluding the five detected
gold mutations. Those findings have not yet been attorney-adjudicated and must
not be called false positives or true defects until hand review.

## Next decision

Preserve this artifact as replicate 1. Do not overwrite it or characterize a
post-fix rerun as another replicate of the same frozen system. Before spending
more held-out material, inspect the three source-association failures and the 22
additional MUST_FIX findings. Any retrieval correction creates a new system
version; evaluate it with qualification sources first and report any rerun of
these exposed pairs transparently as diagnostic, not held out.

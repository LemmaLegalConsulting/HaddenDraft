# Argument Gym Correctness Floor, Judge Qualification, and Citation Cache

**Date:** 2026-09-13

**Branch:** `feature-argument-gym-correctness-mode`

**Status:** implementation and micro-qualification complete; Azure deployment started and not yet verified

**Preserved predecessor:** `preserve-lexis-mutation-study-review-20260913` at `860098a`

## 1. Objective

Refocus Argument Gym from open-ended adversarial commentary into a legal
correctness test harness while retaining the Opponent/Judge/Coach architecture.
The roles now generate, adjudicate, and remediate; named checks define what may
be contested. A clean brief may return zero findings, and uncertainty or
incomplete retrieval may not be promoted into a defect.

The first correctness floor comprises:

- `rule_elements`;
- `record_support`, internally separated into cited record support and uncited
  material facts; and
- `authority_support`.

The old persuasive/adversarial checks remain available as a separate stress
test and do not determine the correctness result.

## 2. Repository changes

### 2.1 Stable, typed test results

Correctness checks now emit stable `checkId + targetId` identities and typed
`MUST_FIX`, `REVIEW`, or `PASS` dispositions. The pipeline no longer imposes a
minimum finding count, restores rejected challenges, caps verified defects, or
ranks heterogeneous criticisms against one another. Reports give CI-style
counts and preserve the distinction among a check that passed, was turned off,
or could not run.

The record checker now extracts atomic, material, record-verifiable claims and
tracks `SUPPORTED`, `CONTRADICTED`, `NOT_FOUND`, and `NOT_VERIFIABLE` evidence
states. Negative findings are conditioned on record coverage. Authority support
asks only whether the cited source supports the proposition for which it is
used.

Primary implementation commit:

- `96846f9 Refocus Argument Gym on bounded correctness tests`

### 2.2 Citation extraction and source-specific resolution

Citation extraction combines EyeCite with local deterministic Ohio patterns.
Authority retrieval is citation-specific and local-first. CourtListener/Free
Law Project is consulted only after local resolution fails, and only for
reporter citations sufficiently specific for its citation-lookup endpoint.
Unavailable source text yields `REVIEW` or a hidden unverifiable test, never a
claim that the authority is wrong.

The implementation also corrected target stability, local source matching,
record coverage handling, and exact source/target association.

Primary implementation commit:

- `e35f1d3 Harden Argument Gym correctness verification`

### 2.3 Evidence-bound Judge

The Judge now receives homogeneous batches of at most eight candidates and may
rule only on the challenge presented. Each response must contain every expected
candidate ID exactly once, a valid disposition, and a nonempty reason.
`REVIEW` and `MUST_FIX` require a supplied evidence reference. An invalid batch
invalidates the whole named check so a partial response cannot appear clean.
The pipeline does not substitute the Opponent's proposed disposition when the
Judge fails.

Two audit tools were added:

- `lexis_real_briefs/experiment/tools/replay_correctness_judge.py` replays saved
  candidates against another Judge without rerunning extraction or retrieval;
- `lexis_real_briefs/experiment/tools/inspect_correctness_run.py` prints visible
  findings, Judge contract failures, and a conservative context-window audit.

Primary implementation commit:

- `02cced8 Make correctness Judge batches auditable`

### 2.4 CourtListener rate handling and Ohio parallel citations

The fallback accepts either `COURTLISTENER_API_TOKEN` or
`COURTLISTENER_API_KEY`. One request batches up to three prioritized local
misses; at most three opinion fetches follow, keeping a single run to no more
than four ordinary API calls. HTTP 429 is not retried and produces no adverse
authority conclusion.

A live probe exposed an Ohio-specific resolution problem: CourtListener returned
two clusters for `75 Ohio St.3d 280`, but uniquely resolved the parallel
reporter `662 N.E.2d 264` to *Dresher v. Burt*. The response parser previously
assumed one response row per target and could discard that second result. It now
associates every parsed citation with its input span and prefers a uniquely
resolved parallel reporter over an ambiguous official reporter.

Primary implementation commit:

- `f85864e Respect CourtListener limits and parallel citations`

### 2.5 Persistent citation and opinion cache

Resolved CourtListener opinions are promoted into the existing local caselaw
boundary:

- the complete opinion text is written through `apps.core.storage` into the
  published caselaw area;
- an unverified, search-approved `CaseLawDecision` is created with CourtListener
  provenance and remains unapproved for drafting;
- pages, chunks, and search documents are built through the existing caselaw
  indexing functions;
- official and parallel reporter aliases are stored in
  `CourtListenerCitationCache` and point to the decision; and
- later lookups return a `local_cases` source without using CourtListener.

Definitive CourtListener misses are cached for 30 days and ambiguous matches for
7 days. They are cache records only, not caselaw decisions, and do not establish
that an authority does not exist. Both durations are deployment settings. Cache
records are visible in Django admin.

Primary implementation commit:

- `0ee959f Persist CourtListener opinions in local case law`

### 2.6 Deployment hygiene

The local `lexis_real_briefs/` tree had grown to 6.9 GB. It and the lab notebook
are development evidence, not runtime inputs, so both are now excluded from the
Docker context without deleting or moving them.

Primary implementation commit:

- `f381be6 Exclude experiment corpus from runtime image`

## 3. Micro-experiment evidence

### 3.1 Judge qualification: GPT-5.6 Terra versus GPT-5.5

The same saved candidates and prompt were replayed against each Judge. Thus the
comparison isolates Judge response coverage, disposition, and latency from
target extraction and retrieval variance.

| Check/sample | GPT-5.5 | GPT-5.6 Terra | Disposition agreement |
|---|---:|---:|---:|
| Record support, 16 candidates in two batches | 23.588 s | 13.765 s | 16/16 |
| Rule elements, 10 candidates in two batches | 44.814 s | 14.083 s | 10/10 |
| Combined | 68.402 s | 27.848 s | 26/26 |

Both models returned every candidate, with zero blank reasons and zero adverse
rulings lacking evidence. Terra was 59.3% faster in aggregate. This establishes
operational compatibility on this micro-sample, not gold-labeled accuracy or
independence: Terra and GPT-5.5 are from the same model family.

Raw evidence:

- `lexis_real_briefs/experiment/results/micro-judge-hardening-gpt55-20260913.json`
- `lexis_real_briefs/experiment/results/micro-judge-hardening-gpt56terra-deployed-20260913.json`
- `lexis_real_briefs/experiment/results/micro-judge-rules-gpt55-20260913.json`
- `lexis_real_briefs/experiment/results/micro-judge-rules-gpt56terra-20260913.json`

The Azure deployment `gpt-5.6-terra`, model version `2026-07-09`, GlobalStandard
capacity 1000, was created for this qualification.

### 3.2 Cross-family checks

On the same 16 record-support candidates:

- `grok-4-6` agreed with GPT-5.5 on 16/16 dispositions and satisfied the output
  contract, but took 120.681 seconds;
- DeepSeek V4 Pro, after batching was reduced to eight, returned both 8-item
  batches with no blank reasons or evidence-free adverse rulings and agreed on
  16/16 dispositions. Its two calls totaled 34.703 seconds.

This suggests that the earlier DeepSeek omissions were at least partly a batch
contract failure. It does not erase the earlier unexplained behavior. Grok and
DeepSeek remain useful cross-family sensitivity cells rather than the preferred
operational Judge.

Raw evidence:

- `lexis_real_briefs/experiment/results/micro-judge-hardening-grok46-20260913.json`
- `lexis_real_briefs/experiment/results/micro-judge-hardening-deepseek-20260913.json`
- `lexis_real_briefs/experiment/results/micro-judge-hardening-deepseek-offset8-20260913.json`

### 3.3 F007 correctness micro-run

The latest exact F007 control run reported one direct date contradiction as
`MUST_FIX` and six record-support items as `REVIEW`; it did not force a minimum
or convert incomplete negative retrieval into factual accusations. The
must-fix target said Anthony Notarian died February 22, 2020, while the cited
probate record said February 21, 2020.

Evidence directory:

- `lexis_real_briefs/experiment/results/micro-correctness-live-final-f007b-20260913/F007-control/`

This fixture was already used during development. It is diagnostic evidence,
not held-out evaluation evidence.

## 4. Context-window evidence

The largest prompt in the current exact F007 run was the record Opponent input:
95,919 characters, or approximately 31,973 tokens using the deliberately
conservative three-characters-per-token estimate. The rule-elements prompt was
approximately 30,573 tokens. Both fit a 128,000-token context with a 16,000-token
output reserve. New eight-candidate Judge replays were approximately 2,900 input
tokens.

The record pipeline already caps the bounded record set at six documents and
150,000 characters. No agentic passage-search layer was added because the
measured current inputs do not approach the context limit, and another retrieval
stage would add variance. The inspector will flag a future deployment or brief
that exceeds the configured context assumption.

Reproduce the audit with:

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/inspect_correctness_run.py \
  lexis_real_briefs/experiment/results/micro-correctness-live-final-f007b-20260913/F007-control
```

## 5. Live CourtListener and local-ingest evidence

The live F007 probe used one batched lookup and bounded opinion fetches. It
resolved:

| Local decision ID | Decision | Citation aliases | Full text | Search documents |
|---:|---|---|---:|---:|
| 1213 | *Gordon v. Bartlett* | `62 Ohio App. 295`; `23 N.E.2d 964` | 20,526 characters | 5 |
| 1214 | *Dresher v. Burt* | `662 N.E.2d 264`; `75 Ohio St. 3d 280` | 42,267 characters | 9 |

Both have `metadata_source=courtlistener_v4`, are approved for search, are not
approved for drafting, have a stored opinion artifact, and created four durable
citation-alias rows. A second test used a session object that raises on any HTTP
method; both decisions returned as `local_cases`, with `requested=0` and
`persistentHits=2`. This demonstrates database/storage reuse rather than merely
an in-process Django cache hit.

These IDs identify the local development database. The production copies must
be verified separately after deployment and ingestion.

## 6. Automated verification

After persistent caching was added, the following suite passed:

```bash
.venv/bin/python backend/manage.py test \
  apps.sources apps.caselaw apps.argument_gym --verbosity 1
```

Result: **341 tests passed in 43.751 seconds**. The focused CourtListener suite
also tests:

- one batched lookup plus one opinion fetch;
- no retry after HTTP 429;
- duplicate citation grouping;
- resolution through a parallel reporter when the official reporter is
  ambiguous;
- durable opinion promotion and a zero-network second lookup; and
- expiring negative lookup caching.

Earlier, before the final persistent-cache work, the full backend suite passed
484 tests. The later 341-test command is the directly relevant post-change
evidence and should be preferred when describing this implementation.

## 7. Deployment record

The production CourtListener key was copied into the git-ignored
`.env.containerapps` file without printing or committing it. Deployment was
started with:

```bash
./scripts/deploy_azure_containerapps.sh
```

The image tag reported at kickoff was
`agentichousingacr.azurecr.io/agentic-housing-drafting:20260913T165228Z`.
After the 6.9 GB experiment tree was excluded, Azure reported a 289.133 MiB
build context and queued ACR build `cj17`; the source download completed at
16:55:22 UTC. The deployment subsequently completed and its URL health check
passed. A live production-app execution imported *Dresher v. Burt* as production
decision 18231 and *Gordon v. Bartlett* as production decision 18230. The first
lookup requested two authorities and resolved both without a rate-limit
response. A second lookup requested zero remote authorities and reported two
persistent hits, evidence that production reused the promoted local decisions.

## 8. Interpretation and remaining work

The evidence is promising for the intended linting/unit-test floor:

- Judge output is now structurally auditable and may fail closed;
- Terra produced the same micro dispositions substantially faster;
- direct record contradictions can become `MUST_FIX` while incomplete negative
  searches remain `REVIEW`;
- CourtListener can close important local citation gaps without repeated calls;
  and
- current real-brief prompt sizes do not require a more variable agentic search
  layer.

The next defensible experiment must use fresh, attorney-verified fixtures and
measure named target outcomes. The micro-runs above were used to develop and
qualify the implementation and cannot serve as held-out evidence. Production
deployment and production ingestion were subsequently verified as described in
section 7.

## 9. Citation and Ohio-rule expansion

Commit `911474b` adds a narrower semantic citation contract and fifteen common
Ohio housing-defense/counterclaim profiles. The private Iskin source was found
at the configured private content-provider boundary and was read alongside the
official authorities; no private treatise text or generated private Markdown
was added to git.

Citation targets now use the sentence or semicolon clause containing the
citation (maximum 700 characters), retain case name and pinpoint metadata, and
classify the asserted use as a holding/rule, quotation, case fact, procedural
posture/outcome, or general support. Pinpoint correctness is explicitly
`unmeasured` when retrieved text lacks stable page boundaries. Semantic review
runs in batches of at most four targets with only their linked sources. Issue
identity comes from the deterministic target classification, so a quotation
mismatch no longer changes issue code when a model alternates between words
like “overstated” and “contradicted.”

The rule library now covers post-notice acceptance of future rent, late-rent
course of dealing, timely tender/refusal, R.C. 5321.11 notice and remedy, local
pay-to-stay, R.C. 1923.061(B) offsets, R.C. 5321.15 self-help, project-based
federal notice and meeting requirements, public-housing termination/grievance,
HCV notice-copy and HAP defenses, VAWA, reasonable accommodation, and the CARES
Act thirty-day notice issue.

Local pay-to-stay and the post-moratorium CARES Act profile intentionally remain
unverified and therefore cannot produce an error. Thirteen new profiles are
verified. Existing R.C. 1923.04, 5321.02, 5321.04, and 5321.16 profiles were
also corrected and source-verified. Conditional elements now carry
`required_when`; uncertain applicability cannot become a missing-element
failure. The prompt distinguishes a party asserting full compliance from one
challenging a particular prerequisite, avoiding the false premise that the
challenger must plead every possible compliance route.

Uncertainty-only record results (`NOT_VERIFIABLE`) and partial/nothing-supplied
rule support remain recorded as internal `REVIEW` tests and coverage counts but
are not attorney-facing findings. This preserves the distinction between “ran
and found no established defect” and “could not verify.”

Focused post-change tests:

```text
.venv/bin/python backend/manage.py test \
  apps.argument_gym.test_correctness \
  apps.argument_gym.test_rule_audit \
  apps.rules.test_legal_rules

70 tests passed in 3.784 seconds
```

A deterministic inventory over all main briefs in `normalized_preview` found
47 briefs, 1,306 authority targets, and 18 briefs invoking at least one
maintained housing rule. The maximum was 89 authority targets in one brief.
Detected profile frequency was R.C. 1923.04 (7), self-help (5), landlord duties
(4), retaliation (3), security deposits (3), late-rent course of dealing (2),
and reasonable accommodation (1). This demonstrates useful rule coverage of
the real sample but also shows that a complete semantic citation sweep is a
background workload, not a synchronous request.

The first eight-pair live diagnostic run is preserved at
`lexis_real_briefs/experiment/results/micro-correctness-rules-citations-terra-final-20260913/`.
Fifteen of sixteen arms completed the strict Judge contract; one F006 mutant
arm was degraded because a Judge batch was incomplete. The run found the same
concrete Anderson quotation defect at the same F001 target in both arms, but it
did not reliably separate the planted F004 authority swap, F005 dissent-label
deletion, or F007 service-method contradiction. Because these fixtures were
used during development and their gold labels remain unverified, this is
diagnostic—not efficacy evidence. More importantly, the misses mean the current
evidence supports fail-closed behavior and real-defect discovery, but not yet a
claim of consistent mutation detection.

### 9.1 Iteration evidence: F005 dissent-as-holding

The first hardened F005 rerun failed in a useful way: the mutant passed while
the control received an unrelated finding. Inspection showed three separate
causes, each subsequently hardened:

1. a resolved Sherman opinion was not reused for a later pinpoint/parallel
   citation to Sherman;
2. citation checking allowed one finding to mask a distinct opinion-status
   defect; and
3. the local search snippet contained only the majority discussion, while the
   passage under test was in a separate dissent. The model also supplied text
   not traceable to the retrieved snippet.

Commits `00bf316`, `e303fe9`, `3f5e185`, `3f7f051`, and `654fb3f` address those
failures by reusing opinions across citation variants, preserving complete
explanatory parentheticals, giving opinion status its own stable test target,
retrieving the stored chunks nearest the attributed language with neighboring
headings, requiring model-supplied source passages to occur in the supplied
source, and caching all (bounded to four) opinions in a CourtListener cluster
rather than only the first majority opinion.

The final development rerun is preserved at
`lexis_real_briefs/experiment/results/micro-correctness-f005-complete-opinions-20260913/`.
At the planted `u50:authority1` target, the control was `REVIEW` for an apparent
pre-existing transcription problem and the mutant was `MUST_FIX`; the mutant
finding expressly identified both the inaccurate quotation and its origin in
Judge Painter's dissent. The control produced zero `MUST_FIX` findings overall;
the mutant produced three. Two additional mutant-only failures elsewhere in the
brief show that whole-run noise/stability still needs measurement. This is one
successful diagnostic mutation detection, not an estimate of sensitivity.

### 9.2 Rule-only sweep

Commit `286dcde` added a source-recorded `--check` option to the experiment
runner. This allowed every existing subtle fixture, both control and mutant, to
run through only `rule_elements`, without paying for unrelated authority calls:

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/run_experiment.py \
  --output-dir lexis_real_briefs/experiment/results/micro-rules-all-fixtures-20260913 \
  --live --model gpt-5.6-terra --check rule_elements
```

All 16 arms completed without a degraded model call. Across 127 element tests,
there were zero `MUST_FIX` results and seven visible `REVIEW` results. Thirty-nine
additional uncertainty-only reviews were retained internally but hidden. On the
61 stable target IDs shared within pairs, 46 had the same disposition (75.4%).
The absence of error-level control noise is encouraging, but 75.4% internal
disposition agreement is not sufficient to claim unit-test-like repeatability.
These fixtures also contain no attorney-verified planted missing-element
mutations, so this sweep tests specificity and usability, not rule sensitivity.

### 9.3 Ohio ROD and CAP before CourtListener

Commit `6db9ce7` changes remote resolution order to local caselaw, then the
Supreme Court of Ohio Reporter of Decisions for identifiable Ohio web-cites,
then CAP static reporter volumes, and only then CourtListener. Successful free
retrievals are promoted into the local caselaw database. Exact citation matches
now bypass the generic local-search candidate cutoff; before that fix, an
already imported opinion could sit behind unrelated keyword hits and cause an
unnecessary remote request.

Direct probes, without calling CourtListener, resolved and promoted:

- `2014-Ohio-2305` from Ohio ROD in one PDF request (10,988 extracted chars;
  local development decision 1215); and
- *Sherman v. Pearson*, 110 Ohio App.3d 70, from CAP (19,788 chars; existing
  local development decision 686).

The subsequent exact local queries returned those decisions first. The IDs are
development-database identifiers and are not portable evidence. The official
Ohio URL shape was checked against the Reporter of Decisions portal and current
published examples. CAP uses the repository's existing static-volume client.

Post-integration automated verification:

```text
.venv/bin/python backend/manage.py test \
  apps.argument_gym apps.rules apps.sources apps.caselaw

398 tests passed in 63.989 seconds
```

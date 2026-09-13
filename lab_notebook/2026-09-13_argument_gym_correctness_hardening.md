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
16:55:22 UTC. The bootstrap migration, live revision, health check, and live
ingestion of *Dresher* and *Gordon* were not yet observed. They must not be
reported as successful until separately verified.

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
deployment and production ingestion also remain explicit verification steps.

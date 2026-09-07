# Argument Gym reasoning benchmark

`minimal-pairs.yaml` is a maintained, synthetic, closed-world evaluation corpus.
It is not legal authority, a retrieval library, or a source of production legal
rules. The district hierarchy, city coverage, transition dates, and holdings are
stipulated assumptions. No real case names, client records, or current-law claims
are used. Before using realistic variants in a paper, have attorneys verify and
version their assumptions and gold proposition/span bindings.

The first 12 scenarios form six pairs. Each pair expands a shared input and
changes exactly one named field; its expected decisions must change. Both halves
must match their gold answers for the pair to pass.

| Pair | Variable | Required change |
| --- | --- | --- |
| Appellate district (P0) | Forum district | Binding case A vs. B, with the other characterized as persuasive |
| Municipality (P0) | Property municipality | Pay-to-stay available vs. unavailable despite a shared court |
| Amendment (P1) | Filing date | Old vs. amended notice rule |
| Entailment (P0) | Bound source ID | Supporting holding vs. keyword-related discussion |
| Goal alignment (P0) | Advocate goal | Payment proposal with no suitable template vs. litigation filing |
| Factual certainty (P1) | Record passage | Qualified, not established vs. definite, supported |

Six additional poisoned/control scenarios test contradictory authority, wrong
precedential level, overruled authority, exact quotation, paraphrase inside a
quotation, and attribution to the wrong case. `SUPPORTED`, `CONTRADICTED`, and
`NOT_ESTABLISHED` are distinct outcomes. Complete coverage is stipulated for the
municipality pair: an absent real-world ordinance is **not** proof of no right.
The amendment pair explicitly stipulates that filing date controls; real rules
may instead turn on accrual, notice, conduct, or a savings clause.

## Run and review

From the repository root:

```sh
# Offline harness and workflow regressions; makes no model calls.
.venv/bin/python backend/manage.py test apps.argument_gym.test_benchmarks apps.drafting.test_audit apps.drafting.test_operations

# Export only the model inputs, for an external runner.
.venv/bin/python backend/manage.py run_gym_benchmark --export-inputs --output /tmp/gym-inputs.json

# Grade recorded structured responses, keyed by scenario ID.
.venv/bin/python backend/manage.py run_gym_benchmark --responses /tmp/gym-responses.json --output /tmp/gym-report.json

# Optional live benchmark, using the configured OpenAI-compatible provider.
# Makes 18 model calls and incurs API costs. No deterministic fallback.
.venv/bin/python backend/manage.py run_gym_benchmark --live --output /tmp/gym-live-report.json
```

`--suite` selects another reviewed suite; `--model` and `--reasoning-level`
override live prompt defaults. Live prompts are loaded exclusively from
`prompts/argument_gym.benchmark.yaml`; admin overrides are disabled. The model
receives the scenario and decision field names, never gold values, pair IDs, or
sibling responses. Each call is independent. External runners should likewise
send only each exported value, not its scenario ID, to the model.

A response has exactly `decisions` (the requested fields) and `evidence` (objects
with `source_id` and `span`). JSON types matter. Evidence must match the curated
source/span bindings, allowing only whitespace normalization and reordered
bindings. Different quotes, extra bindings, duplicates, wrong sources, omitted
spans, and keyword overlap cannot pass. The live prompt specifies empty evidence
for action selection, exclusion without a governing case, and quote-checking
probes, whose decisions are graded directly.

Reports contain per-scenario findings, pair outcomes, input/suite/prompt hashes,
timestamp, responses, and live model/reasoning settings and raw outputs. Missing
responses and provider errors are `not_run`; malformed answers are `fail`.
Failures or unrun scenarios produce a nonzero command exit after writing the
report. Replay model identity is explicitly unverified. The prompt hash in a
replay identifies the current benchmark prompt, not proof that the external
runner used it. Keep provider identity, repository revision, external execution
settings, and repeated-run artifacts alongside any paper results. Avoid storing
private endpoint credentials in artifacts.

## What passing establishes

Offline regression tests prove the grader rejects targeted bad answers, checks
pair isolation, and cannot turn a missing run into success. They **do not prove
that an AI answered correctly**. Gold-response replay is a harness check only.
No live model measurements are included with this corpus.

Live results measure constrained reasoning with supplied sources and metadata.
They do not measure retrieval, the production opponent/judge/coach pipeline,
free-form drafting, or complete legal reasoning. Exact curated spans make grading
deterministic but may reject another substantively adequate passage; attorneys
should adjudicate and version alternative gold spans before comparing runs.
This is proposition-level evaluation against human labels, not a new general
purpose semantic entailment validator. No LLM judge assigns quality scores.

The companion drafting regressions verify that model-supplied review flags do
not remove the exported attorney-review notice, a model proposal cannot apply
itself through its payload, and plain-text auto-repair preserves the notice and
AI provenance. Draft components currently have no dedicated attorney-review
state; these tests do not establish a full actor-authorized review transition
or cover every regeneration/repair path.

## Exploratory runs on private revision snapshots

`scripts/benchmark_real_briefs.py` exercises the production Gym stages on local
DOCX revisions. This is separate from the synthetic fixed-answer benchmark.
For a small paired live run:

```sh
.venv/bin/python scripts/benchmark_real_briefs.py --live --endpoints --family L_Moore --output-dir cle_real_briefs/benchmark_outputs/my-live-run
```

Omit `--live` for offline checks with empty retrieval. `--endpoints` selects the
first/last filenames only in families containing at least three snapshots;
different appellate filings are not treated as revisions. `--model` defaults to
`gpt-5.5`, and `--reasoning` to `medium`. Live use is explicit and incurs API
costs. The source corpus must already be available locally.

The runner requires a new directory under ignored `cle_real_briefs/`, creates a
private SQLite copy of the app database, and refreshes file-backed court/legal
seeds there while preserving locally edited profiles. It saves code snapshots,
Git state, dependency versions, effective profiles, input hashes, actual model
requests/responses, source query results, complete findings and challenges, and
stage traces. Results are checkpointed per document; call logs are written before
and after each request. Credentials are used from local configuration and are
not written to manifests or call logs. The private DB copy itself must remain
private because it includes the local database's configuration and case data.

Live runs use the real Ohio case/statute/ordinance/treatise connectors, file-backed
prompts, a fixed requested model/reasoning setting, and a 180-second per-call
timeout. The SDK may omit unsupported temperature settings. Model aliases and
changing retrieval corpora mean reruns need not be bit-for-bit identical; saved
requests, responses, and returned source spans are the execution record.

No case-record attachments are supplied by this runner. Do not treat missing
record coverage as a defect in a filing. Compare findings and dispositions
within each revision family, distinguish `unmeasured` from `pass`, and report
fallbacks explicitly. There is no aggregate brief-quality score.

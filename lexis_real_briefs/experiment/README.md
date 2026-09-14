# `lexis_real_briefs/experiment/`

Minimal-pair mutation study of the Argument Gym, built from the 2026-09-08 Lexis
delivery in the parent directory.

**Start with [`REGISTER.md`](REGISTER.md)** — the registered conditions, written
before any Gym output was seen. It is the document to write findings against.

## Map

| Path | What it is |
|---|---|
| `REGISTER.md` | pre-registration: question, design, mutation classes, measurement, declared limits |
| `conditions.json` | the same, machine-readable |
| `mutations.yaml` | the authored mutations — exact find/replace, gold vulnerability, rationale |
| `inventory.json` | every delivered filing: Lexis metadata, extraction status, attachments |
| `case_families.json` | 44 case families, focal-filing choice, and why each excluded filing was excluded |
| `normalization_log.json` | what normalization removed from each filing, counted |
| `ocr/`, `ocr_index.json` | Azure Document Intelligence transcriptions of the 29 scanned filings, cached by source SHA-256 |
| `fixtures/F00N/` | the study fixtures — see the layout in `REGISTER.md` §3c |
| `fixtures_index.json` | one-line summary per fixture |
| `results/` | run results, one record per fixture per condition, against `results.schema.json` |
| `normalized_preview/` | normalized text for every readable filing, including those not used — scratch, for picking future fixtures |
| `tools/` | the pipeline; see below |

The later correctness-floor experiments add two frozen, shareable fixture
suites: `fixtures-heldout-authority-20260913/` contains extracted text from
publicly filed Lexis-located briefs, and
`fixtures-rule-floor-attorney-reviewed-20260913/` contains wholly fictional
AI-authored rule-element pairs. Their compact results are the nested
`report.public.json` files under the correspondingly named `results/heldout-*`
directories. No Cleveland Legal Aid work product or source PDF is included.

## Pipeline

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/build_inventory.py      # 104 files -> 53 filings
AZURE_DI_KEY_FILE=<path> \
  .venv/bin/python lexis_real_briefs/experiment/tools/ocr_scans.py          # scans -> text (cached)
.venv/bin/python lexis_real_briefs/experiment/tools/build_inventory.py      # again, now with OCR
.venv/bin/python lexis_real_briefs/experiment/tools/build_case_families.py  # -> 44 families, 10 eligible
.venv/bin/python lexis_real_briefs/experiment/tools/normalize.py            # mechanical normalization
.venv/bin/python lexis_real_briefs/experiment/tools/build_fixtures.py       # -> fixtures/, with hashes
.venv/bin/python lexis_real_briefs/experiment/tools/check_gym_limits.py     # no ceiling truncates a fixture
```

Deterministic: same delivery in, same hashes out.

## Before using any of this as a benchmark

Every fixture is `verification_status: "unverified"`. The mutations were drafted
by a language model (Claude Opus 5) and no attorney has answered the four
reviewer questions in `REGISTER.md` §8. Until that happens these are development
fixtures and a run against them is a pilot of the method.

---

## What is in this repository, and what is not

The filings are **public court records** — motions and briefs filed in Ohio
municipal, common pleas and appellate courts. They were located through a Lexis
search, and the *delivery* is a licensed compilation, so the delivered files
themselves are not redistributed here. The extracted text of the same public
filings is, along with everything derived from it, so that any figure in the
paper can be checked.

### Committed

| | |
|---|---|
| `REGISTER.md`, `REGISTER-2x2.md` | the two pre-registrations, written before their runs |
| `mutations.yaml` | every mutation: exact find/replace, gold label, rationale |
| `fixtures/F00N/` | control and mutant text, the attached record, gold labels, SHA-256s |
| `normalized_preview/` | normalized text of all 47 readable filings, including those not used |
| `ocr/`, `ocr_index.json` | our Azure Document Intelligence transcriptions of the scanned filings |
| `inventory.json`, `case_families.json` | how 104 delivered files became 8 fixtures, and why each filing was excluded |
| `results/*/report.public.json` | every run: challenges, judge assessments, proposed attacks, verdicts, traces |
| `results/*.tex`, `2x2-measures.json` | the tables in the paper, generated from the above |
| `review/`, `adjudication-*/` | the blind reviewer materials and the key |
| `brief-defect-review.html` | the reviewer tool, self-contained |
| `tools/` | every script, from corpus reduction to LaTeX generation |

### Not committed, and why

| | |
|---|---|
| the Lexis delivery (`*.docx`, `*.pdf`) and `fixtures/*/source/` | a licensed compilation; the extracted text of the same filings is here instead |
| `results/*/run.sqlite3` (2.1 GB) | each run's isolated database copy; results are in the reports |
| `results/*/*/call-*.json` (239 MB) | the full prompt and response of every model call |
| `results/*/report.json` (110 MB) | superseded by `report.public.json`, which is the same record minus 63 MB of verbatim third-party corpus text pulled by the research stage |
| `results/*/*/result.json` | the same per-run record again, already inside the reports |
| `results/*/code-snapshot.tar.gz` | the code, which is this repository |
| `results/superseded-pre-fix/` (data) | runs made against the unfixed Gym; its README is kept so the void run is not forgotten |

`tools/export_public.py` produces the public reports; the analysis tools read
`report.json` when present and fall back to `report.public.json`, so **a fresh
clone reproduces every table in the paper** without any of the excluded files.

### Standing caveats

The mutations were drafted by a language model (Claude Opus 5) and **no attorney
has yet adjudicated them**. Every fixture carries
`verification_status: "unverified"`. Nothing here answers whether the Gym detects
a planted defect; that awaits the blind adjudication described in
`REGISTER.md` §8.

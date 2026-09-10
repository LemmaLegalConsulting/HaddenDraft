# Registration: Lexis minimal-pair mutation study (2026-09-08)

**Registry ID** `lexis-mutation-2026-09` · **Status** conditions frozen, fixtures
built, **no run executed** · **Commit at registration** `2f81846`
· **Revised the same day**: scanned filings transcribed by OCR, corpus re-derived (§8)

Full pre-registration, fixtures and gold labels live with the corpus at
`lexis_real_briefs/experiment/` (gitignored, like `cle_real_briefs/`). This entry
is the committed record of the design and of what the corpus turned out to
support.

## 1. What the study asks

Whether introducing one known legal vulnerability into a real brief causes the
Argument Gym to raise that vulnerability, measured against the unmodified
control — not whether the Gym finds *something* in a bad brief.

Paired within-fixture design: control = a real Ohio filing, normalized
mechanically; mutant = the same file with exactly one legally meaningful change.
The median change is 0.4% of the document. Outcome is the four-cell paired
table (discriminating / missed / non-discriminating / reversed), reported as
counts, not as an accuracy rate. The 1/1 cell is the reason the control is run
at all: a defect the Gym already flagged in the unmodified brief was not caused
by the mutation, and a "did it find the bug" evaluation miscounts that as
success.

## 2. Who authored the mutants

**Claude Opus 5 (`claude-opus-5`), via Claude Code, 2026-09-08.** The model chose
the focal filings, wrote the normalizer, the OCR pipeline and the document
splitter, chose each mutation target, drafted the mutant text and the
gold-vulnerability descriptions, and wrote the register. It did not verify
statutory or case-law history, did not confirm what a mutated authority actually
holds, and did not adjudicate materiality. No attorney has reviewed any fixture.

OCR is a separate machine step with its own provenance: **Azure AI Document
Intelligence, model `prebuilt-read`, api-version `2024-11-30`**, on the user's own
subscription. It produced the control text of F007 and F008 and every attached
record. No human has proofread a transcription against its scan.

Every fixture therefore carries `verification_status: "unverified"` and an empty
`verified_by`. Under the protocol none is admissible to a held-out benchmark;
they are development fixtures and the first run against them is a pilot of the
method rather than a measurement of the Gym.

The Gym under test runs on `OPENAI_MODEL` (default `gpt-5.4-mini`). Mutation
author and system under test are different models but both are language models,
which is an open confound and is recorded rather than argued away.

## 3. What the corpus reduced to

104 delivered files → 53 filings → 44 case families → 10 eligible → **8 fixtures**.

One focal advocacy filing per lawsuit, so a matter with a motion, an opposition
and a reply contributes one observation. Inclusion required substantive advocacy
(no writs, praecipes, docket entries), extractable text (natively or after OCR),
and eviction centrality measured on the Gym's own unit structuring: ≥5 argument
units carrying landlord-tenant vocabulary, ≥10% of argument units, **and ≥3
units carrying possession-specific vocabulary**. That third threshold is what
the first two miss — in a case captioned landlord v. tenant those words are
party labels — and it is what removed *Texlo v. Gator Hillcrest*, which scored
37% while arguing only about final appealable orders.

*Jacob v. Fadel* and *DeBartolo v. Dussault Moving* are eligible and unauthored:
in both, an eviction is the operative act but the claims litigated are fiduciary
duty and receivership, and neither offered a clean single-change target.

| ID | Case | Court | Class | Target | Δ |
|---|---|---|---|---|---|
| F001 | *Stone v. Cazeau* | 9th Dist. | A missing_element | tenant-at-sufferance status deleted — the step bringing the occupant within R.C. Ch. 1923 | 249 / 15,760 |
| F002 | *Cleveland Dev. v. Carter* | 8th Dist. | A missing_element | landlord-knowledge application deleted while the brief's own rule statement keeps the no-knowledge excuse | 316 / 47,302 |
| F003 | *Dayton Tool Rental v. Ealy* | 2nd Dist. | B record_support | "left at the premises" upgraded to personal service plus an on-record acknowledgment the cited exhibit does not establish | 45 / 14,558 |
| F004 | *Masten v. K&D Mgmt.* | 8th Dist. | C authority_applicability | binding 6th Cir. authority on 42 U.S.C. § 3617 swapped for an out-of-circuit district decision the brief already cites | 4 / 41,806 |
| F005 | *Kerr v. Lakewood Shore Towers* | 8th Dist. | C authority_applicability | "(J. Painter, dissenting)" removed — a dissent presented as the holding, in the very case the opponent relies on | 25 / 24,795 |
| F006 | *Lee v. Wallace* | 8th Dist. | E removed_counterargument | the paragraph answering R.C. 1923.02(A)'s permissive "may be had" deleted; the opponent's quoted statutory text stays | 210 / 32,140 |
| **F007** | *Estate of Notarian v. Notarian* | **Geauga C.P.** | B record_support | "served an eviction notice" → "served by certified mail, return receipt requested"; the fixed 66-page record shows posting at the premises and holds no return receipt | 45 / 14,224 |
| **F008** | *Friese v. Baker* | **Geauga C.P.** | E removed_counterargument | section III.B, the preemptive answer to the R.C. 5321.04 landlord-duty theory, deleted; the tenancy stays on every page | 1,343 / 15,345 |

F006, F007 and F008 carry a case record in `attachments/`, byte-identical
between conditions — which is the load-bearing part of the design: if the record
is identical and only the brief differs, a challenge about the relationship
between argument and record can only have come from the brief.

Class D (temporal / current-law) is **registered with zero fixtures**: it needs
an attorney with a citator, and inventing a statutory version would have made
the gold label itself wrong. Class F (advocacy degradation) is registered as
exploratory and excluded from the primary measure.

## 4. What OCR recovered

Roughly half the delivery is an image. **29 PDFs, 1,371 pages, 2,396,035
characters** were transcribed with Azure Document Intelligence `prebuilt-read`.
Results are cached by source SHA-256, so a re-run costs nothing and a changed
source cannot silently reuse an old transcription. Two things came back:

**The trial stratum.** Nine filings whose `.docx` wrapper is only a metadata
card became readable, and two pass the inclusion test: *Estate of Notarian* (a
forcible entry and detainer motion arguing title and R.C. 1923.04(A) notice
compliance) and *Friese v. Baker* (a landlord's summary judgment motion raising
open-and-obvious and res judicata from a prior municipal eviction). The other
seven are insurance, foreclosure, commercial and public-health matters.

**A case record.** For a PDF-only filing the scan contains the exhibits filed
with the motion; for several already-readable appellate briefs the scan runs far
longer than the Lexis transcription, because Lexis transcribed the brief and
dropped the appendix (*Lee v. Wallace*: 87,603 scanned characters against
32,235 transcribed). F007's record holds the process server's affidavit,
photographs of service, and the Notice to Leave Premises itself — which is what
makes its gold label mechanically checkable: the record contains
"NOTICE TO LEAVE PREMISES" six times and the phrases "certified mail" and
"return receipt" zero times, and the mutant asserts both.

**OCR text is not corrected.** Misreadings are left as transcribed, for the same
reason typos in a Lexis transcription are left. Only the per-page e-filing stamp
and page-number footer are removed, and both are counted per fixture. The
transcription source is a between-strata difference, never a within-pair one.

## 5. Limits, recorded before results

**Six of eight fixtures are appellate**; the trial stratum is two deep and
supports no general claim about trial-level eviction practice — the setting the
Cleveland interviews were about.

**Five of eight fixtures have no independent record.** F003 remains an
intra-document record-support test, weaker than F007 because it does not require
reading an attachment.

**F008 has a known structural tell**: deleting section III.B leaves its headings
running A, C. The adjudication rule absorbs it — a challenge that says "a
section is missing" does not name the gold proposition and is not a target match
— but it is the first fixture to check if results look too good.

**n = 8, not 25.** Report the per-pair table and the four counts; not a rate.

## 6. Size ceilings: checked, nothing to raise

Four ceilings can silently drop part of a brief, and a benchmark that asks
whether the Gym found a defect is worthless if the defect was never sent to it.
All four measured against all nineteen study documents — sixteen briefs and
three attached records (`tools/check_gym_limits.py`):

| Ceiling | Value | Worst document | Bites? |
|---|---|---|---|
| `ingestion.MAX_BRIEF_CHARS` | 120,000 | 72,407 (60.3%) | no |
| `ARGUMENT_GYM_BRIEF_TEXT_CHARS` | 120,000 | 72,407 (60.3%) | no |
| `ARGUMENT_GYM_UNIT_BUDGET_CHARS` | 260,000 | 107,989 payload (41.5%) | no |
| `ingestion.BRIEF_PAGE_LIMIT` | 30 pages | n/a — `.docx` reports no page count | no |

Nothing truncated, nothing sampled, and both conditions of every pair read
identically — which matters, because a pair where the control fits and the
mutant is sampled would differ for a reason unrelated to the mutation.

**One raw file would have exceeded the budget and does not after normalization.**
The *Carroll v. Houser* wrapper needs 276,196 characters against a 260,000
budget, because Lexis appended four full case reprints after the certificate of
service. `split_appended_authorities` moves those to `attachments/`. The general
finding: raising the ceiling is not what this corpus needs; normalizing before
running is. Raw Lexis wrappers would reintroduce the overflow, and the 30-page
cap would additionally cut any PDF-only trial filing longer than 30 pages, which
is most of them.

One incidental observation from the measurement, not acted on:
`ingestion.MAX_BRIEF_CHARS` (120,000) caps stored brief text below the
260,000-character unit budget, so for a single uploaded brief the upper half of
that budget is unreachable. It does not bite here — the largest fixture is 39% of
the cap — but the two ceilings are set as if independent.

`select_units`' per-unit cost accounting was checked against the real serialized
payload on the 1,350-unit *Carroll* document and agrees to within 2 characters,
so the budget means what it says.

## 7. A truncation that is not a ceiling — reported, not fixed

The OCR work surfaced something more consequential than any character ceiling.
`ingestion.split_brief_and_exhibits` treats the first page whose opening two
lines mention an exhibit as the start of the attachments. In running prose that
fires on an ordinary inline reference: page 3 of the Notarian motion begins
mid-sentence with "...See attached Exhibit 2." and the splitter therefore
reports a **2-page brief for a filing whose own footer says "Page 13 of 13"**.
Measured: the Gym would read 2,269 of the motion's 14,468 characters of argument
and classify the other **84% as an exhibit** — including the entire R.C.
1923.04(A) compliance section this study mutates, which is simply absent from
what the model stages would see. The certificate of service on page
12 does not rescue it: the certificate only wins when it *precedes* the exhibit
marker.

For filed trial-level motions, which is what the Gym is for, this costs far more
argument than the character ceilings do, and it is silent — the run reports a
successful ingestion of a short brief. Fixtures here are split by
`tools/filed_document.py` instead, which requires a certificate of service or a
real exhibit *cover sheet*. **The Gym itself was not changed**; that is a
decision to make deliberately, not as a side effect of building a benchmark.

Two rules in the experiment's own tooling were corrected the same way — because
the corpus exposed them, not because a result was unwelcome. The centrality test
gained the possession threshold after *Texlo*; the splitter's certificate rule
went from "last match anywhere" to "first match, heading or sentence, not a
table-of-contents entry", after the last-match rule swallowed a 66-page record
into the brief and the bare-phrase rule reported a 2-page brief for a 23-page
appellate filing whose table of contents lists its certificate.

## 8. Revision log

Same day, before any run. Nothing measured was revised, because nothing had been
measured: no Gym output has been seen at any point.

| | Before OCR | After |
|---|---|---|
| Readable filings | 39 | 47 |
| Eligible case families | 6 | 10 |
| Fixtures | 6 | 8 |
| Trial-level fixtures | 0 | 2 |
| Fixtures with a case record | 0 | 3 |

## 9. Where this sits in the fixture protocol

Steps 1–4 and 7 done (source selected before any Gym output; target chosen; gold
recorded; mutation made and verified as a single unique-match edit; hashes
frozen). Steps 5–6 — second-reviewer adjudication of the four questions —
outstanding for all eight. The freeze rule stands: do not modify the Gym after
viewing results for a fixture; a fixture that exposes a bug worth fixing moves
permanently to the development set.

## 10. Reproduction

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/build_inventory.py
AZURE_DI_KEY_FILE=<path> \
  .venv/bin/python lexis_real_briefs/experiment/tools/ocr_scans.py   # cached; free on re-run
.venv/bin/python lexis_real_briefs/experiment/tools/build_inventory.py   # again, now with OCR
.venv/bin/python lexis_real_briefs/experiment/tools/build_case_families.py
.venv/bin/python lexis_real_briefs/experiment/tools/normalize.py
.venv/bin/python lexis_real_briefs/experiment/tools/build_fixtures.py
.venv/bin/python lexis_real_briefs/experiment/tools/check_gym_limits.py
```

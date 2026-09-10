# Registered conditions — Argument Gym minimal-pair mutation study

**Registry ID** `lexis-mutation-2026-09`
**Registered** 2026-09-08 (revised the same day; see §13)
**Status** conditions frozen; fixtures built; **no run has been executed**
**Corpus** `lexis_real_briefs/` (Lexis delivery, 2026-09-08, job 295074488),
with the scanned filings transcribed by OCR (§3d)
**Repository state at registration** `2f818467e88b50c55444ff0441fa85d7e7dffa8d` (`main`)

This file is the pre-registration. It is written before any Gym output has been
seen, and it is the document to write findings against later. Anything decided
after seeing results belongs in a separate analysis note, marked as such.

---

## 1. Question

> In what proportion of controlled brief pairs does the introduction of one
> known legal vulnerability cause the Argument Gym to raise that vulnerability,
> when it had not raised it in the unmodified brief?

The comparison is within-pair. "Did the Gym find something in the mutant" is not
the measure; "did the mutation cause the finding" is.

---

## 2. Design

Paired minimal-difference fixtures built from authentic Ohio filings. Each pair
is one real brief (**control**) and the same brief with exactly one legally
meaningful change (**mutant**). Nothing else differs — not the caption, not the
facts, not the relief, not the attachments, not the whitespace.

| | |
|---|---|
| Unit of analysis | the lawsuit (one focal filing per case family) |
| Conditions | `control`, `mutant` — within-fixture, both run |
| Primary outcome | per-pair discrimination (§6) |
| Blinding | the Gym never receives `fixture.json`; it receives only `brief.txt` |
| Held-out | **no** — see §8, every fixture is currently development material |

### Strata

| Stratum | What it is | Fixtures |
|---|---|---|
| `appellate_eviction` | Ohio appellate merit/answer briefs where eviction, possession, or an eviction-related defense is central to an argument the court must resolve | 6 |
| `trial_eviction` | trial-level motions and memoranda, same centrality test | 2 (F007, F008) |
| `landlord_tenant_secondary` | landlord-tenant law central but possession is not | 0 (candidates identified, unauthored) |

Ten case families pass the inclusion test; eight are authored. *Jacob v. Fadel*
and *DeBartolo v. Dussault Moving* are eligible and unauthored — both are cases
where an eviction is the operative act but the claims litigated are fiduciary
duty and receivership, so neither offered a clean single-change target. They are
recorded in `case_families.json` for an attorney who wants to author them.

Appellate and trial filings are **not pooled**. They are different advocacy
tasks and the Gym applies a different court profile to each.

---

## 3. What was done to the documents

### 3a. Corpus reduction (`tools/build_inventory.py`, `tools/build_case_families.py`)

104 delivered files → 53 filings → 44 case families → 10 eligible → 8 authored.

Lexis delivers each result as a `.docx` wrapper plus, sometimes, a scanned
`_Attachment1.pdf`. Filings from the same lawsuit were grouped into a case
family and **one** focal advocacy filing chosen per family, so a matter that
produced a motion, an opposition and a reply contributes one observation rather
than three correlated ones. The rest of each family is retained in
`case_families.json` for qualitative use.

Inclusion, applied to the focal filing:

1. **substantive advocacy** — it asks the court to resolve something. Writs,
   praecipes, docket entries, orders and standalone exhibits are excluded.
2. **eviction centrality** — three thresholds on the argument units, measured
   with the Gym's own unit structuring so the test matches what the Gym reads:
   ≥5 units carrying landlord-tenant vocabulary, ≥10% of argument units, and
   ≥3 units carrying *possession-specific* vocabulary (forcible entry and
   detainer, R.C. 1923, writ of restitution, notice to leave the premises,
   right of possession, holdover). The third threshold is what the first two
   miss: in a case captioned landlord v. tenant the words "landlord" and
   "tenant" are party labels appearing in every paragraph, and *Texlo v. Gator
   Hillcrest* scored 37% on the broad vocabulary while arguing from first line
   to last about whether the denial of a motion for judgment on the pleadings is
   a final appealable order. Heading hits are recorded but not required: an
   earlier version required one and rejected *Masten v. K&D Mgmt.* — a holdover
   tenancy and Fair Housing retaliation appeal with 60 eviction-bearing argument
   units — because its headings read "ARGUMENT" and "STATEMENT OF FACTS".
3. **readable** — the filing has extractable text, natively or after OCR (§3d).

### 3d. OCR of the scanned filings (`tools/ocr_scans.py`)

Roughly half the delivery is an image. Twenty-nine PDFs — **1,371 pages,
2,396,035 characters** — were transcribed with **Azure AI Document Intelligence,
model `prebuilt-read`, api-version `2024-11-30`**, on the user's own subscription
(`WorkflowDocs`, East US). The API contract was verified against the live
resource before any document was sent, not assumed from documentation.

Results are cached by the *source* SHA-256, so a re-run costs nothing and a
changed source cannot silently reuse an old transcription. Each cached record
carries the engine, model, api-version and transcription date, and every fixture
built from one repeats that in `provenance.text.ocr`.

Two things came back from it:

* **the trial stratum.** Nine filings whose `.docx` wrapper is only a metadata
  card became readable. Two of them — *Estate of Notarian v. Notarian* and
  *Friese v. Baker*, both Geauga County Common Pleas — pass the inclusion test
  and are now fixtures F007 and F008. Before OCR the trial stratum was empty.
* **a case record.** The scans of the PDF-only filings contain the exhibits
  filed with the motion, and the scans of several already-readable appellate
  briefs run far longer than the Lexis transcription because Lexis transcribed
  the brief and dropped the appendix. Three fixtures now carry a real record:
  F006 (40 pages of appendix), F007 (66 pages of exhibits including the
  process server's affidavit and the Notice to Leave Premises), and F008
  (certified copies of the prior municipal-court eviction complaint and
  judgment).

**OCR text is not corrected.** Misreadings, dropped diacritics and mangled
citation punctuation are left exactly as transcribed, for the same reason typos
in a Lexis transcription are left: they are properties of the document under
test. The only thing removed is the per-page furniture stamped on by the court's
e-filing system and the page-number footer, counted in each fixture's
`provenance.text.page_furniture_removed`.

The transcription source is a **between-strata difference**: F007 and F008 carry
OCR noise that F001–F006 do not. It is never a within-pair difference — control
and mutant of one fixture always come from the same transcription of the same
file — but it is a reason not to pool the strata, on top of the reasons in §2.

### 3b. Normalization (`tools/normalize.py`, version 1.0)

Mechanical only. Removed:

- the Lexis wrapper header (case name through the `Text` marker) and the
  trailing `End of Document` line — delivery furniture, absent from the filed
  document, confirmed against the as-filed scan which begins at the caption;
- star-pagination markers (`[*12]`) that Lexis injects to key its text to the
  reporter. The page boundary is preserved as a break; only the marker goes;
- authorities Lexis appended after the filing ended (each introduced by a
  `LEXSEE` line following the certificate of service). These are **moved to
  `attachments/`, not deleted.**

Explicitly **not** done: no prose rewritten, no typo fixed, no citation
corrected, no OCR spelling repaired, no attorney boilerplate removed, no
repeated language collapsed. Redundancy inside a filing is a property of the
filing and stays; removing it would have turned the control into an edited,
improved brief and destroyed the comparison. Every removal is counted in
`normalization_log.json` and in each fixture's `provenance.normalization_log`.

### 3c. Preservation

```
fixtures/F004/
  source/original.docx        immutable Lexis delivery
  source/as-filed-scan.pdf    the scanned filing, where Lexis supplied one
  normalized/brief.txt        the control — what is benchmarked
  normalized/attachments/     the record filed with it, and appended authorities
  mutant/brief.txt            control with exactly one change
  mutant/attachments/         byte-identical to normalized/attachments
  fixture.json                the gold label — never given to the Gym

Attachment identity across conditions is the load-bearing part: if the record is
byte-identical and only the brief differs, a challenge about the relationship
between argument and record can only have come from the brief.
```

SHA-256 of source, control, mutant and every attachment is recorded in
`fixture.json`. The builder refuses to write a fixture whose target text does
not occur exactly once in the control, so a mutation cannot silently land in the
wrong place or in two places.

---

## 4. Who made what — provenance of the mutations

**The mutants in this study were drafted by a language model, not by an
attorney.** This is the single most important caveat on any finding.

| | |
|---|---|
| Model | **Claude Opus 5** (`claude-opus-5`), Anthropic |
| Interface | Claude Code CLI, interactive session |
| Date | 2026-09-08 |
| What it did | selected focal filings; wrote the normalizer, the OCR pipeline and the document splitter; chose each mutation target; drafted the mutant text and the gold-vulnerability description; wrote this register |
| What it did **not** do | verify Ohio statutory or case-law history; confirm that a mutated authority does or does not stand for the proposition; adjudicate materiality |
| Human review to date | **none** |
| Recorded in each fixture at | `provenance.generator` |

OCR is a separate machine step with its own provenance: Azure AI Document
Intelligence `prebuilt-read` (api-version `2024-11-30`) produced the control
text of F007 and F008 and every attached record, recorded per fixture in
`provenance.text.ocr`. No human has proofread a transcription against its scan.

Every fixture therefore carries `gold.verification_status: "unverified"` and an
empty `gold.verified_by`. Under the protocol in §8 none of them is yet
admissible to a held-out benchmark. They are development fixtures. A write-up
must say so.

The Gym under test is a separate system driven by `OPENAI_MODEL` (default
`gpt-5.4-mini`; the historical live runs in the lab notebook used `gpt-5.5`).
The model that authored the mutations and the model being evaluated are
different systems, but they are both language models, and a reader is entitled
to treat "Claude wrote defects that an OpenAI model was asked to find" as a
possible source of correlation. It is recorded here rather than argued away.

---

## 5. Mutation classes

The rule for every one: **change one legally meaningful thing and nothing else.**
No fabricated case names, no fictional citations, no jurisdiction swaps unless
jurisdiction is the mutation, no spelling damage, no deleted argument sections,
no more than one defect per mutant.

| Class | Registered definition | Authored |
|---|---|---|
| **A `missing_element`** | delete or weaken the sentence applying one material element of a rule the brief itself states; leave the rule statement, the statute, the surrounding argument, the attachments and the relief untouched | **2** (F001, F002) |
| **B `record_support`** | change a proposition supported by the cited source into a stronger one that source does not establish; the citation and the source are unchanged | **2** (F003 intra-document, **F007 against a fixed record**) |
| **C `authority_applicability`** | replace a properly applicable authority with a real but legally defective one — another district, a trial-level decision, an out-of-circuit court, a dissent presented as a holding; the legal proposition itself is unchanged | **2** (F004, F005) |
| **D `temporal_defect`** | substitute an outdated statutory version, a superseded ordinance, or a rule effective after the operative event | **0 — see below** |
| **E `removed_counterargument`** | delete only the passage answering an obvious adverse argument, leaving the adverse position present in the brief's own text | **2** (F006, F008) |
| **F `advocacy_degradation`** | bury the dispositive point, remove rule-to-fact linkage, remove the roadmap — same information, weaker synthesis | **0**, and registered as exploratory only |

### Why class D is empty

Class D requires establishing, with confidence, that a specific Ohio statute,
ordinance or rule read differently at the operative date. The model authoring
these fixtures did not verify any such history and will not assert one it has
not checked. Registering the class with zero fixtures is the honest position;
inventing a statutory version would have produced a fixture whose gold label was
itself wrong. **Class D is open and needs an attorney with a citator.**

### Why class F is exploratory

Its gold label is "lawyers prefer the control", not "the mutant contains an
identifiable legal defect". It cannot be scored on the same binary and is kept
out of the primary measure.

---

## 6. Measurement

For each pair, for the registered target vulnerability only:

| Control raised | Mutant raised | Outcome | Meaning |
|:---:|:---:|---|---|
| 0 | 1 | **discriminating** | the mutation caused the finding — the desired result |
| 0 | 0 | **missed** | the Gym did not detect the introduced defect |
| 1 | 1 | **non-discriminating** | the Gym already flagged this in the unmodified brief, so this pair demonstrates nothing about sensitivity — not necessarily an error, but not evidence |
| 1 | 0 | **reversed** | the mutation suppressed a finding — investigate |

These four are reported as counts. They are **not** collapsed into an accuracy
figure. Running the control is what makes the 1/1 cell visible, and the 1/1 cell
is the one that a "did it find the bug" evaluation silently miscounts as success.

Secondary, recorded but not primary: rank of the target challenge, survival
through the judge stage, count of other challenges raised and how many of those
are valid.

**Matching a Gym challenge to the target is a judgment call and is adjudicated
against `gold_vulnerability`, which describes the underlying proposition, not
against `mutation.subtype`.** The Gym may correctly describe the F002 defect as
missing factual support rather than as a missing element; that counts as a
match. Wording is not the test.

Per-run results go in `results/` against `results.schema.json` — one record per
fixture per condition. Fixture truth and run results stay in separate files.

---

## 7. What this corpus can and cannot support — recorded before results

**The trial stratum exists, and it is two fixtures deep.** Of 15 trial-level
filings, 14 arrived as a Lexis metadata card ("Click to view PDF document",
200–400 characters) in front of a scanned PDF, nine of them with no text layer
at all. OCR (§3d) made all nine readable, and two pass the inclusion test:
*Estate of Notarian* (a forcible entry and detainer motion for partial summary
judgment on possession, arguing title and R.C. 1923.04(A) notice compliance) and
*Friese v. Baker* (a landlord's summary judgment motion raising open-and-obvious
and res judicata from a prior municipal-court eviction). The other seven are
insurance, foreclosure, commercial and public-health matters. Two trial fixtures
support a comparison of strata; they do not support a claim about trial-level
eviction practice generally.

**There is now a real case record, for three fixtures.** The `_Attachment1.pdf`
files are scans of the filed document, and for a PDF-only filing that scan
includes the exhibits filed with it. F007 carries 66 pages of exhibits — the
process server's affidavit, photographs of service, and the Notice to Leave
Premises itself — and F008 carries certified copies of the prior eviction
complaint and judgment. F006 carries the 40-page appendix that Lexis dropped.
This is what makes F007 the fixture the design originally asked for: the brief
is altered, the record is byte-identical between conditions, and the record
disproves the altered claim.

Five fixtures (F001–F005) still have no independent record. F003 remains an
intra-document record-support test — the exhibit the brief cites and the hearing
it describes — which is a weaker test than F007 because it does not require
reading an attachment.

**n = 8, not 25.** The planned allocation was five fixtures per class over
roughly 25 briefs. The delivery yielded ten eviction-central, readable,
one-per-lawsuit advocacy filings, of which eight had a clean single-change
target. Eight pairs cannot estimate a rate. Report the per-pair table and the
four outcome counts; do not report a percentage.

**One fixture has a known structural tell.** Deleting section III.B from F008
leaves its headings running A, C — the gap is visible without reading a word of
law. The adjudication rule in §6 absorbs this (a challenge that says "a section
is missing" does not name the proposition in `gold_vulnerability` and is not a
target match), but a reviewer should weigh it, and it is the reason F008 is the
first fixture to check if the results look too good.

---

## 8. Fixture protocol — where this study stands in it

| Step | Status |
|---|---|
| 1. Source brief selected without seeing Gym output | done — no run has been executed |
| 2. One argument identified that supports a clean mutation | done (by model) |
| 3. Proposed gold vulnerability recorded | done, in `mutations.yaml` and `fixture.json` |
| 4. Mutation made | done, verified as a single unique-match edit |
| 5. Second reviewer examines control, mutant, law and attachments | **not done** |
| 6. Reviewer answers the four questions | **not done** |
| 7. Hashes frozen | done |

The four reviewer questions, unanswered for all six fixtures:

1. Are the pair identical except for the intended change?
2. Is the control free of the targeted defect?
3. Does the mutant contain the targeted defect?
4. Is the defect material enough that competent opposing counsel could
   reasonably raise it?

Only yes/yes/yes/yes admits a fixture to a held-out benchmark.

**The freeze rule.** Do not modify the Gym after viewing results for a fixture.
If a fixture exposes a bug worth fixing, fix it — and move that fixture to the
development set permanently, replacing it with a fresh one. With n=6 and no
held-out set, *every* fixture here is development material, and the first run
against them is a pilot, not a benchmark.

---

## 9. Execution conditions (to be filled at run time)

Frozen now so a later run can be compared against a stated baseline:

| Setting | Value at registration |
|---|---|
| `OPENAI_MODEL` | `gpt-5.4-mini` (default; override recorded per run) |
| `ARGUMENT_GYM_UNIT_BUDGET_CHARS` | 260,000 |
| `ARGUMENT_GYM_UNIT_TEXT_CHARS` | 2,400 |
| `ARGUMENT_GYM_BRIEF_TEXT_CHARS` | 120,000 |
| `ingestion.MAX_BRIEF_CHARS` | 120,000 |
| `ingestion.BRIEF_PAGE_LIMIT` | 30 pages |
| Prompt catalog | `prompts/argument_gym.*.yaml` at `2f81846` |
| Python | 3.12.3 |

### Size headroom — checked, no change required

`tools/check_gym_limits.py` measures all four ceilings against all nineteen
study documents — sixteen briefs and three attached records. The largest brief
is 47,302 characters; the largest document of any kind is F007's 72,407-character
record, at **41.5% of the unit budget and 60.3% of the ingestion cap.** Nothing
is truncated, nothing is sampled, and both conditions of every pair are read
identically — which matters, because a pair where the control fits and the mutant
is sampled would differ for a reason unrelated to the mutation.

One raw file *would* have exceeded the budget: the *Carroll v. Houser* wrapper
needs 276,196 characters against a 260,000 budget. It does so because Lexis
appended four full case reprints after the certificate of service — furniture,
not brief. Normalization removes the cause, and *Carroll* is not in the study in
any event. **The conclusion is unchanged by the OCR work: no ceiling needs
raising for this corpus, provided documents are normalized and split before they
are run.**

### A truncation that is not a ceiling — reported, not fixed

`ingestion.split_brief_and_exhibits` takes the first page whose opening two lines
mention an exhibit as the start of the attachments. In running prose that fires
on an ordinary inline reference. Page 3 of the Notarian motion begins mid-sentence
with "...See attached Exhibit 2." and the splitter therefore reports a **2-page
brief for a filing whose own footer says "Page 13 of 13"**. Measured: the Gym
would read 2,269 of the motion's 14,468 characters of argument and classify the
other **84% as an exhibit** — including the entire R.C. 1923.04(A) compliance
section this study mutates, which is simply absent from what the model stages
would see. The certificate of service on page 12 does not
rescue it, because the certificate only wins when it *precedes* the exhibit
marker.

For a corpus of filed trial-level motions, which is what the Gym is for, this
costs far more argument than any of the character ceilings do, and it is silent:
the run reports a successful ingestion of a short brief. The fixtures here are
therefore split by `tools/filed_document.py`, which requires a certificate of
service or an actual exhibit *cover sheet*, so a wrong split cannot silently
decide what a fixture contains. **The Gym itself was not changed** — that is a
decision to make deliberately, not as a side effect of building a benchmark.

### A second truncation, on the record path — found too late

`record.material_text(material, *, max_chars=6000)` caps how much of an
**attached record** any stage ever reads. It is a hard-coded default argument
rather than a setting, and it applies per material *after* every brief-side
budget has been satisfied — so a record can pass MAX_BRIEF_CHARS, the unit
budget and the text cap, as all three of this study's records do, and still
reach the model as its first few pages.

| Fixture | Record | What a stage reads |
|---|---:|---|
| F006 | 53,283 chars | first 6,000 (11%) |
| **F007** | 72,407 chars | first 6,000 (**8%**) |
| F008 | 15,317 chars | first 6,000 (39%) |

**This invalidates F007 as a record-support fixture.** Its gold label turns on
the process server's affidavit and the Notice to Leave Premises; the affidavit
begins at character 8,692 and the notice at 8,810, both past the cap. What the
Gym receives instead is the opening warranty deed. The mutant asserts service by
certified mail; the evidence that contradicts it is not in the model's context,
so a challenge saying "the record does not contain the notice" is *correct given
what was supplied* and cannot be scored against a gold label about what the
record shows.

F006 and F008 are not invalidated: their mutations are counterargument
deletions, and the record is context rather than the target.

`check_gym_limits.py` now measures this ceiling, and for a `record_support`
fixture additionally locates the phrases its gold label quotes and fails if any
begins past the cap. **That check did not exist before this run and should have.**
The register's §9 headroom claim was true of every ceiling it measured and
silent about the one that mattered most for the fixture built to exercise the
record.

The Gym was not changed. Raising the cap is a real decision — it multiplies
per-run record tokens — and it belongs to the maintainer, not to the benchmark.

Re-run `check_gym_limits.py` if fixtures are added or if the budget settings
change.

---

## 10. Reproduction

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/build_inventory.py
AZURE_DI_KEY_FILE=<path> \
  .venv/bin/python lexis_real_briefs/experiment/tools/ocr_scans.py   # cached; no cost on re-run
.venv/bin/python lexis_real_briefs/experiment/tools/build_inventory.py   # again, now with OCR
.venv/bin/python lexis_real_briefs/experiment/tools/build_case_families.py
.venv/bin/python lexis_real_briefs/experiment/tools/normalize.py
.venv/bin/python lexis_real_briefs/experiment/tools/build_fixtures.py
.venv/bin/python lexis_real_briefs/experiment/tools/check_gym_limits.py
```

Deterministic: same delivery in, same hashes out.

---

## 11. Fixture register

| ID | Case family | Court | Class | Target | Δ chars |
|---|---|---|---|---|---|
| F001 | *Stone v. Cazeau* (07CA009164) | Ohio App. 9th Dist. | A missing_element | tenant-at-sufferance status, the step that brings the occupant within R.C. Ch. 1923, deleted | 249 of 15,760 |
| F002 | *Cleveland Dev. v. Carter* (95135) | Ohio App. 8th Dist. | A missing_element | the clause applying landlord knowledge deleted, while the brief's own rule statement preserves the no-knowledge excuse | 316 of 47,302 |
| F003 | *Dayton Tool Rental v. Ealy* | Ohio App. 2nd Dist. | B record_support | "left at the premises" upgraded to personal service plus an on-record acknowledgment the cited exhibit does not establish | 45 of 14,558 |
| F004 | *Masten v. K&D Mgmt.* (CA-12-098894) | Ohio App. 8th Dist. | C authority_applicability | binding Sixth Circuit authority for the scope of 42 U.S.C. § 3617 replaced with an out-of-circuit district decision the brief already cites | 4 of 41,806 |
| F005 | *Kerr v. Lakewood Shore Towers* | Ohio App. 8th Dist. | C authority_applicability | "(J. Painter, dissenting)" removed, presenting a dissent as the court's holding in the very case the opponent relies on | 25 of 24,795 |
| F006 | *Lee v. Wallace* | Ohio App. 8th Dist. | E removed_counterargument | the paragraph answering R.C. 1923.02(A)'s permissive "may be had" language deleted; the opponent's quoted statutory text stays | 210 of 32,140 |
| F007 | *Estate of Notarian v. Notarian* (23M000467) | Geauga C.P. **(trial)** | B record_support | "served an eviction notice" becomes "served by certified mail, return receipt requested" — the fixed record shows posting at the premises and contains no return receipt | 45 of 14,224 |
| F008 | *Friese v. Baker* (23P000020) | Geauga C.P. **(trial)** | E removed_counterargument | section III.B, the preemptive answer to the R.C. 5321.04 landlord-duty theory, deleted; the tenancy stays on every page | 1,343 of 15,345 |

F006, F007 and F008 also carry a case record in `attachments/`, byte-identical
between conditions. Full gold labels, excerpts, hashes, normalization and OCR
logs: `fixtures/F00N/fixture.json`.

---

## 12. Paragraph for the write-up

> We constructed paired fixtures from authentic Ohio appellate filings retrieved
> from Lexis. Each fixture consisted of an unmodified control brief and a
> minimally altered version containing one introduced legal or argumentative
> vulnerability; the median change was 0.4% of the document. All other document
> content and associated materials were held constant, and both conditions were
> verified to pass through the evaluation system's input ceilings identically.
> Mutations represented missing legal elements, unsupported factual
> propositions, defective authority selection, and removal of responses to
> material counterarguments. The evaluation measured whether introduction of the
> vulnerability caused the Argument Gym to identify the targeted issue relative
> to the corresponding control, scored as four paired outcomes rather than as an
> accuracy rate. Scanned filings without a text layer, which comprised roughly
> half the retrieved corpus, were transcribed by commercial OCR; this recovered
> the trial-level stratum and, for three fixtures, the exhibits filed with the
> document, allowing one fixture to test a proposition against a record held
> byte-identical across conditions. **Mutations were drafted by a language model
> (Claude Opus 5) and have not been adjudicated by an attorney; the corpus
> yielded eight usable fixtures, six appellate and two trial-level. The study is
> accordingly a pilot of the method, not a measurement of the system.**

---

## 13. Revision log

**2026-09-08, same day, before any run.** The delivery's scanned filings were
transcribed by OCR (§3d) and the corpus re-derived. Nothing measured was
revised, because nothing had been measured: no Gym output has been seen at any
point, so this is a change to the corpus, not to a result.

| | Before OCR | After |
|---|---|---|
| Readable filings | 39 | 47 |
| Eligible case families | 6 | 10 |
| Fixtures | 6 | 8 |
| Trial-level fixtures | 0 | 2 |
| Fixtures with a case record | 0 | 3 |
| Mutation classes with a fixture | A, B, C, E | A, B, C, E (B now includes a true record test) |

Two rules were also corrected, both because the corpus exposed them rather than
because a result was unwelcome:

* the centrality test gained a possession-specific threshold, which removed
  *Texlo v. Gator Hillcrest* — a brief that scored 37% on landlord-tenant
  vocabulary while arguing only about final appealable orders (§3a);
* the document splitter's certificate-of-service rule was changed from "last
  match" to "first match, heading or sentence, not a table-of-contents entry",
  after the last-match rule swallowed a 66-page record into the brief and the
  bare-phrase rule reported a 2-page brief for a 23-page appellate filing whose
  table of contents lists its certificate.

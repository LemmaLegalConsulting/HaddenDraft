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

---

## 8a. Amendment, 2026-09-11 — before any detection scoring

Recorded as an amendment rather than an edit, because §8 was registered in
advance and this changes it. **No challenge has been scored and no four-cell
outcome computed at the time of writing**, so nothing here is a rule chosen to
suit a result. What has been seen is the two fixture reviews below.

### The second review was not independent, and the protocol said it would be

Step 5 as registered has a second attorney see "only the control, mutant,
relevant law, and attachments." What happened instead: the second attorney
looked **after, and informed by, the first reviewer's answers.**

That is a legitimate process — adjudication by consensus is standard — but it is
a different one, and it must not be described as dual independent rating:

* **No inter-rater reliability can be computed.** The 75% raw agreement between
  the two returns is not a reliability statistic and must not be reported as
  one. Cohen's kappa is undefined here in any case: the second reviewer answered
  `yes` to all sixteen judgments, so one rater has zero variance and agreement
  cannot be distinguished from acquiescence.
* **The first review is the only independent rating in the study.**
* The second review is an adjudication of the three fixtures the first left
  unresolved or rejected.

### What the two reviews say

Both answered `mutant_has` and `material` on all eight fixtures. Neither
answered `identical` or `control_clean` broadly (see below; they no longer
need to).

| | R1 (independent) | R2 (informed) |
|---|---|---|
| Cleared both questions | F001, F002, F003, F007, F008 | all eight |
| Unresolved | F004 (material), F006 (both) | — |
| Rejected | F005 (material) | — |

The disputed one is F005, where a four-word deletion removes
"(J. Painter, dissenting)" and so presents a dissent as the court's holding in
the very case the opponent relies on. R1 judged that opposing counsel would not
realistically raise it; R2, looking at that specific concern, judged that it
would, because the brief now implies the majority supports a proposition the
majority rejected. Both may be right about different things: the registered
question asks about litigation practice ("would counsel raise it"), not about
whether the citation is sound, and a reviewer can hold that a defect is real and
that nobody would brief it.

### Revised admission rule

Two of the four questions change, for reasons unrelated to how they were
answered:

* **`identical` is retired and replaced by a mechanical check.**
  `tools/check_pair_integrity.py` reports the changed spans directly: **all
  eight pairs differ in exactly one contiguous region.** A diff answers this
  question better than a reader does, and asking a lawyer spent the study's
  scarcest resource on arithmetic. (An earlier version of that tool also tried
  to infer orphaned section labels and dangling cross-references; it produced
  three false positives and a false negative on eight fixtures, and those
  heuristics were removed rather than shipped. The one structural consequence
  they were meant to catch — F008's headings running A, C once its section B is
  deleted — is recorded by hand here and in the fixture's own `note_on_size`.)
* **`control_clean` is demoted to optional.** The four-cell design already
  absorbs it: a defect the Gym flags in the unmodified brief produces a
  `non_discriminating` pair whether or not an attorney pre-declared the control
  clean. The answer, where given, is used to interpret such a pair — to
  separate "the Gym over-flagged" from "the control really had it" — and not to
  admit or exclude.

Admission therefore rests on `mutant_has` and `material`, and is reported on two
sets, **both pre-specified here, before scoring**:

| Set | Rule | Fixtures | n |
|---|---|---|---|
| **Primary** | cleared on the independent first review | F001, F002, F003, F007, F008 | 5 |
| **Sensitivity** | admitted after adjudication | all eight | 8 |

Both are reported. If the conclusion is the same on each, the disagreement is
immaterial and one sentence says so; if it differs, that difference is the most
important result in the section. Choosing between them after seeing which is
more favourable is the researcher-degrees-of-freedom problem, and specifying
both in advance forecloses it.

**A power note, stated now rather than discovered later.** The only inferential
test this design supports is an exact binomial on discordant pairs, where the
null is that a mutation-caused finding is equally likely to fall either way. Five
discordant pairs all favouring the mutant gives p = 0.031; four gives p = 0.063.
The primary set of five therefore requires a perfect result to reach
significance and has no margin. That is a property of the corpus, not of the
outcome, and it is why the sensitivity set exists.

---

## 8b. Amendment, 2026-09-11 — challenge matching is automated

Registered **before any challenge has been matched or any four-cell outcome
computed.**

§6 specified that matching a challenge to the registered vulnerability is a
human judgment, on the grounds that a scorer deciding it by rule would be
marking its own homework. That is being changed: the 367 pooled challenges will
be matched by model, not by a person.

**What this costs, stated plainly — and precisely.** The design is not the
model's: the five mutation classes, the golden rule of one legally meaningful
change, the four-cell paired outcome, the blinding, the one-lawsuit-one-unit
rule and the gold-label structure were all specified by the researcher, and the
model implemented them. What the model authored is the *instantiation* — which
brief, which sentence in it, the replacement text, and the prose of each
`gold_vulnerability`.

Two of those three now have an outside check. The instances were validated by
two attorneys on `mutant_has` and `material` (§8a). The design was never the
model's to begin with.

What has no outside check is **the matching step**: a model comparing a
challenge against a `gold_vulnerability` whose wording the model wrote. The
specific risk is narrow and worth naming — that the label's phrasing was shaped,
even unintentionally, towards what the Gym tends to say, so that matching
rewards resemblance to the label rather than detection of the defect. The
detection figure should be read as resting on model matching against
model-written labels, under a design and a rule set that are not the model's.

**What is done to limit the damage.**

* **Three frontier matchers, from three families, none of them under test.**
  `glm-5-3` (Zhipu, via Fireworks), `grok-4-6` (xAI) and `kimi-k3` (Moonshot),
  deployed for this purpose. `gpt-5.4` was rejected despite being capable and
  fast: it shares a family with `gpt-5.6-sol`, which wrote half the challenges,
  and a matcher should not be able to prefer its own relatives' prose. Anthropic
  models were excluded for the same reason — the gold labels were written by
  one — and are in any case not deployable here.

  A first pass used `kimi-k2.6`, `grok-4.1-fast-reasoning` and
  `llama-4-maverick`. Those are not frontier-tier, and disagreement among them
  could not be told apart from incapacity, so they were replaced. That pass is
  retained only as a capability comparison: whether weaker matchers disagree
  more than stronger ones is worth knowing and costs nothing to report.
* **The matcher is blind to everything the human worksheet blinded.** It sees
  the fixture's registered `gold_vulnerability` and one challenge's text. Not
  the condition, not the cell, not which model wrote or judged it, not the
  brief.
* **Majority of three decides.** Agreement among the three is reported as a
  first-class result, not a footnote.
* **Every decision is written out with its one-line reason**, so any of them can
  be checked against the challenge text by anyone who doubts it.

**Matching is not mechanical, and the evidence is now from frontier models.**
The same probe was put to all six candidates: a challenge saying "the brief
never identifies any rental agreement or basis for tenant status", against a
vulnerability about a deleted tenant-at-sufferance step.

| Matcher | Tier | Verdict |
|---|---|---|
| `glm-5-3` | frontier | match |
| `kimi-k3` | frontier | match |
| **`grok-4-6`** | frontier | **no match** — "cites missing agreement not omitted sufferance" |
| `llama-4-maverick` | not frontier | match |
| `grok-4.1-fast-reasoning` | not frontier | match |
| `kimi-k2.6` | not frontier | no match |

The frontier set splits 2–1, and the dissent is reasoned rather than careless:
the gold label concerns a deleted step establishing status at sufferance, and
the challenge concerns an absent rental agreement. Those are adjacent
propositions, and whether one names the other is a judgment.

This bears directly on the premise for automating at all — that the rules are
already set and applying them is not a useful human task. On this evidence the
rules are set but their application to particular prose is not determined by
them. If the three frontier matchers split materially across the real set, the
detection result is soft, and the correct conclusion is that this corpus cannot
settle the question without the human pass that was skipped.

**Pre-specified reporting.** Agreement among matchers is reported before any
detection figure. Where the three split, the majority is used and the split is
shown. The four-cell outcome is computed on both the primary set (n=5) and the
sensitivity set (n=8) from §8a.

**A spot-check remains available and is not required.** Twenty challenges drawn
at random, checked by a person against the matcher's decision, would give a
human-anchored estimate of matcher validity for a few minutes' work. If it is
not done, the paper says the detection result rests on model matching alone.

---

## 8c. Amendment, 2026-09-12 — a mechanical tier, as a positive control

Registered **before any of these fixtures has been edited or run.**

### Why

The eight fixtures in §11 carry deliberately subtle defects, and deliberately so:
the registered design rejects "cartoonish defects" on the ground that they test
whether a model notices conspicuous corruption rather than whether the Gym
catches realistic vulnerabilities. That judgment stands.

But it leaves the study unable to distinguish three explanations for a weak
detection result:

1. the Gym is poor at finding legal defects;
2. the Gym is adequate and these particular defects are genuinely hard;
3. the harness is broken and nothing would have been detected.

A tier of defects that are unambiguously present, and that need no housing-law
knowledge to recognise, separates them. It is a positive control, and its
absence was a gap in the design.

The subtle tier is not replaced. Two tiers, reported separately: the mechanical
one answers "does this work at all", the subtle one answers "does it work on
things that matter."

### Who makes them, and why it is not the model

A person edits these. The model assigns briefs to defect types by structure,
writes the scaffolding, and points at where the relevant material sits; it does
not choose the sentence or write the replacement.

This is the one part of the study with no model involvement in instantiation.
For the subtle tier the model chose each passage and wrote each mutant, and that
is precisely what the matching step then scores against (§8b). Here that loop is
broken.

### What may be planted, fixed in advance

A defect qualifies only if a careful reader with no legal training can confirm
it from the brief alone. Three classes are **excluded because the Gym already
catches them deterministically, before any model runs** — planting one would
test a regular expression:

| Excluded | Already handled by |
|---|---|
| unresolved placeholder (`[NAME]`, `TBD`, `XXX`, `____`) | `unfilled_placeholder` |
| reference to an exhibit that is not attached | `exhibit_references_resolve` |
| paragraph numbering that skips | `paragraph_numbering_gaps` |

The classes in play, and what a miss on each would mean:

| Class | Covered by a Gym category? | What a miss means |
|---|---|---|
| **relief_scope** — relief asked for exceeds what was argued | **yes**, `remedy_scope` is one of the seven challenge categories | failure on the system's own terms |
| **party_role** — the brief asks for the relief its own side does not want | no | a gap, not a broken promise |
| **enumeration** — promises *n* reasons, gives fewer | no | a gap |
| **date_contradiction** — a date in the facts contradicts the same date in the argument | no; `record_audit` compares brief to record, not brief to itself | a gap |
| **arithmetic** — itemised figures do not sum to the stated total | no | a gap |

That distinction is load-bearing and is reported per fixture. A `relief_scope`
miss is evidence against a capability the Gym claims; a `date_contradiction`
miss is evidence about a capability nobody claimed. Adding them together would
misstate both.

### Corpus

Drawn from the filings the subtle tier did not use. Eviction centrality is
irrelevant here — a date that contradicts itself does so in an insurance brief
as readily as in an eviction one — so the pool is every readable filing not
already a fixture, and the two tiers share no documents. Assignments:

| | Class | Brief | Court / posture | Length |
|---|---|---|---|---|
| M01 | relief_scope | *WWSD v. Woods* | Ohio App. 10th Dist. | 50,292 |
| M02 | relief_scope | *Sheridan v. Sheridan* | Ohio App. 8th Dist. | 58,868 |
| M07 | relief_scope | *Carano v. Schottenstein* | Ohio App. 10th Dist., appellant | 19,079 |
| M08 | relief_scope | *Williams v. Deutsche Bank* | Ohio App. 8th Dist., appellee | 19,633 |
| M09 | relief_scope | *Presser v. RCP Mayfield* | Ohio App. 8th Dist., appellee | 44,034 |
| M03 | party_role | *Anderson v. Mitchell* | Ohio App. 8th Dist. | 20,295 |
| M04 | enumeration | *Salone v. Stovall* | Ohio Supreme Court | 12,390 |
| M05 | date_contradiction | *Press v. Westport Ins.* | Ohio App. | 27,904 |
| M06 | arithmetic | *Solomon v. Harwood* | Ohio App. 8th Dist. | 74,007 |

Nine fixtures, nine distinct briefs, none shared with the subtle tier.

**Why five of one class and one each of four others.** `relief_scope` is the
only class where a miss is a failure on the Gym's own terms, so it is the one
claim worth powering. The exact binomial that governs the paired outcome caps
what two fixtures can show at p = 0.25 and four at p = 0.062; five all caught
reaches p = 0.031. Setting the sharpest claim at a bar it could never clear
would have been a design error, and the first version of this plan made it.

The other four classes are **single probes and are reported as such**. One
observation cannot separate "the Gym misses this class" from "that particular
edit was subtle", and no claim of the first kind will be made from them. They
are cheap, they vary the kind of defect, and they are worth having as
description.

Postures vary within `relief_scope` on purpose: one appellant seeking reversal,
four appellees seeking affirmance, so the defect is not always the same shape.

### Scoring

The same paired four-cell outcome, run on the same five configurations. Two
additions:

* **Which stage caught it is recorded** — deterministic check, rule audit,
  record audit, or the opponent. A defect surfaced by the check suite is not
  evidence about the adversarial stages, and the two are never summed.
* **Matching should need no adjudication.** These defects have no adjacent
  proposition to be confused with, which is what made the subtle tier's matching
  disputable (§8b). If the frontier matchers disagree materially *here*, that is
  a finding about the matchers rather than about the briefs, and it retrospectively
  weakens the subtle tier's automated matching.

### Standing

The mechanical tier is a positive control and is reported as one. It does not
enter the subtle tier's primary or sensitivity sets, and no figure from it is
combined with them.

---

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

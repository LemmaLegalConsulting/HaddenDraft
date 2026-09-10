# Check-Suite Remediation and the Persuasive Communication Suite (2026-09-08)

## 1. Run Metadata and Reproducibility

- **Execution date**: 2026-09-08
- **Base git commit**: `2f818467e88b50c55444ff0441fa85d7e7dffa8d`
- **Prior entry acted on**: [`test_evaluation_and_feedback.md`](./test_evaluation_and_feedback.md)
- **Baseline outputs**: `cle_real_briefs/benchmark_outputs/2026-09-08-all-briefs-offline/`
- **Post-fix outputs**: `cle_real_briefs/benchmark_outputs/2026-09-08-all-briefs-offline-after-fixes/`
- **Command (both runs)**:
  `.venv/bin/python scripts/benchmark_real_briefs.py --output-dir cle_real_briefs/benchmark_outputs/<dir>`
- **Corpus**: the same 15 `.docx` snapshots, deterministic offline pipeline
  (`AI_DRAFTING_ENABLED=False`, stub retrieval, isolated SQLite catalog), so every
  difference below is a change in the checks and not in the model or the corpus.
- **Test suite after the changes**: 887 backend tests, 190 frontend tests, all passing.

This entry has two halves. **Part A** remediates the five noise/false-alarm
findings and the architectural ceiling recorded in the prior entry. **Part B**
records a new suite of tests added the same day.

---

# Part A — Remediating the prior entry's findings

## 2. Headline result

Every measurement below is the same 15 briefs through the same offline pipeline,
before and after.

| Family | Snapshot | Chars | Units | Grammar | Pleading form | Unmet elements | Offline challenges |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `A_Hooper` | `2026-03-10_source_copy` | 71,450 | 694 | 8 → **4** | 1 → **0** | 7 → **7** | 0 → **0** |
| `A_Hooper` | `2026-04-30_source_copy` | 23,842 | 290 | 5 → **0** | 0 → **0** | 8 → **8** | 0 → **0** |
| `M_Vourliotis` | `2024-10-01_source_copy` | 45,330 | 463 | 3 → **0** | 1 → **0** | 0 → **0** | 0 → **0** |
| `M_Vourliotis` | `2024-11-22_source_copy` | 19,432 | 210 | 0 → **0** | 0 → **0** | 0 → **0** | 2 → **0** |
| `L_Moore` | `2017-09-14_after_first_revision` | 9,205 | 106 | 2 → **1** | 0 → **0** | 10 → **10** | 3 → **1** |
| `L_Moore` | `2017-09-19_after_follow_up` | 9,131 | 106 | 2 → **1** | 0 → **0** | 10 → **10** | 3 → **1** |
| `L_Moore` | `2017-09-22_current_accepted` | 9,071 | 106 | 2 → **1** | 0 → **0** | 10 → **10** | 3 → **1** |
| `L_Wheeler/against_Gentile` | `current_source_copy` | 33,814 | 240 | 1 → **2** | 0 → **0** | 8 → **3** (+1 n/a) | 0 → **0** |
| `L_Wheeler/against_Pine_Creek` | `2025-05-30_initial_revision` | 26,882 | 191 | 4 → **5** | 4 → **4** | 8 → **3** (+1 n/a) | 0 → **0** |
| `L_Wheeler/against_Pine_Creek` | `2025-06-02_follow_up_revision` | 26,883 | 191 | 4 → **5** | 4 → **4** | 8 → **3** (+1 n/a) | 0 → **0** |
| `L_Wheeler/against_Pine_Creek` | `2025-06-03_current_accepted` | 26,885 | 191 | 4 → **5** | 4 → **4** | 8 → **3** (+1 n/a) | 0 → **0** |
| `Residents_Perry_Fairgrounds` | `2024-05-20_before_late_cluster` | 56,985 | 412 | 8 → **3** | 3 → **3** | 3 → **3** | 0 → **0** |
| `Residents_Perry_Fairgrounds` | `2024-05-29_after_review_cluster` | 58,742 | 413 | 7 → **2** | 2 → **2** | 3 → **3** | 0 → **0** |
| `Residents_Perry_Fairgrounds` | `2024-05-30_current_accepted` | 58,270 | 440 | 6 → **2** | 0 → **0** | 3 → **3** | 0 → **0** |
| `T_Thomas` | `current_source_copy` | 20,624 | 161 | 4 → **0** | 0 → **0** | 0 → **0** | 7 → **1** |
| **Total** | | | | **60 → 31** | **19 → 17** | **86 → 66** (+4 unaudited) | **18 → 4** |

Three of these movements are *reductions in noise*, one is a *reduction in false
negatives*, and two cells go **up** — Gentile 1 → 2 and Pine Creek 4 → 5 grammar
findings — because the delimiter check now finds real unclosed parentheses that
the old count was silently cancelling out against caption punctuation.

## 3. Finding 1 — Lowercase sentence starts (the largest single source of noise)

**Prior entry**: 50–80% of all grammar findings; citation fragments, statutory
references, corporate party names, service clauses. *"Creates overwhelming
warning fatigue, teaching advocates to ignore the linter."*

**Measured**: 71 of 97 grammar findings across the corpus (73%). Extracting every
distinct one and reading it: **zero true positives.** A representative sample:

```
of Am., 159 Ohio App.3d 410, 2004-Ohio-7001, 824 N.E.2d 122, ¶8 (1st Dist.)
v Williams, 3 Ohio App.3d 288 (2nd Dist.
of City of Raleigh, 595 F.
of Commissioners, 2019-Ohio-3729, 144 N.E.3d 1010, ¶33 (11th Dist.).
of Camden, 2006 WL 2792784 (D.N.J.
mail, postage prepaid and by electronic mail at [address]
```

**Root cause**: `SENTENCE_SPLIT_RE = (?<=[.!?])\s+|\n+`. A period in a brief is
usually *not* the end of a sentence — case names, reporters, courts, parties and
dates are all abbreviated — and `\n+` treated every wrapped block-quote line and
caption row as a sentence boundary as well.

**Fix** (`apps/validation/language.py`): a period ends a sentence only when an
ordinary lowercase word precedes it. A legal abbreviation is short and
capitalized (`Ohio App.`, `Inc.`, `F.`, `Assoc.`, `Invests.`), which separates
the two structurally rather than by a hand-maintained abbreviation list that
would go stale. Newlines are no longer boundaries. Three further guards, each
derived from a real false positive in the corpus:

- subsection headings (`a. R.C. 1923.06 service requirements`),
- citation signals and pinpoints (`v.`, `see`, `at 157-9`, `e.g.,`),
- drafting notes removed before splitting — `On October 11, 2022, Pine Creek
  [from who?] received an email` split at the note's question mark. The
  placeholder check already reports the note; the sentence it interrupts is not
  a second, different problem.

**Result**: **71 → 6 findings, of which 2 are distinct and both are real**:

```
"...promulgated a three-step burden shifting framework. under the first step, the plaintiff must..."
"...rates that Jones Estates made during the lease term. and did not disclose the additional fees..."
```

## 4. Finding 2 — Caption punctuation (and what it was hiding)

**Prior entry**: standard Ohio caption styling places `)` in a right-hand column;
the linter reported *"6 closing parenthesis(s) with nothing opened"*.

**Measured**: an existing strip rule already removed `)`-only line runs and was
working. What remained were two different things the count could not tell apart:

1. **Enumerators** — `1) … 2) … 3)` in *Thomas*'s summary-judgment standard, and
   six more in *Perry*. Every filing has them.
2. **Real unbalanced delimiters** that the count was cancelling out.

**Fix**: the check no longer counts, it **scans**. It reports the position that
is actually unbalanced and quotes the passage, and recognizes an enumerator only
at a closer the scan could not match. Critically, nothing is stripped from the
text beforehand: an early attempt to strip `X)` enumerators textually turned
`(Attached as Appendix A)` into `(Attached as Appendix` and *manufactured* three
new findings in Thomas — the corpus caught that regression immediately.

**Result**: the caption false positives are gone, and the check now surfaces real
defects it previously masked, each naming its passage:

```
An opening parenthesis is never closed. Near: "the court orally granted Defendant
Pine Creek's Motion in Limine (to exclude all of Ms. Wheeler's documentary evidence."

A closing parenthesis has nothing opened before it. Near: "the Board of Public Health
issued a "shutdown/cease of all activities) of the lead remediation work"
```

The two upward cells in the results table are this.

## 5. Finding 3 — Prayer-for-relief false negatives

**Prior entry**: Hooper and Vourliotis opening briefs flagged *"No passage asks
the court for anything"* despite explicit prayers.

**Measured**: **8 of 8** appellate briefs in the corpus were flagged. Their actual
conclusions:

> *"Appellant Angela Hooper **requests this Court reverse** the judgment of the
> Cleveland Housing Court … and **remand** this matter for hearing."*

> *"Appellant-Defendant Marianthie Vourliotis respectfully **asks this Honorable
> Court to REVERSE** the trial court's default judgment … and **REMAND** …"*

**Root cause**: the patterns knew only the trial-court register — `wherefore`,
`respectfully requests`, `moves this Court for/to`, and a verb-object list of
`judgment|dismissal|relief|order|injunction`. An appellate prayer uses neither
the verb nor the object.

**Fix** (`content/drafting-rules/checks/pleading-form.yaml`): added request verbs
addressed to a court (`asks|urges|petitions … this Honorable Court`), the
appellate relief verbs (`reverse|remand|vacate|affirm|modify|dismiss`), and the
passive form (`should be reversed`).

**Result**: **8 → 0 false negatives**, with the true positive preserved — a paper
that genuinely asks for nothing is still reported.

## 6. Finding 4 — Topical keyword collision in rule audits

**Prior entry**: *"mentioning a deposit triggered a security-deposit audit.
Unasserted elements are then marked as `nothing_supplied`."*

**Measured**: `detect_invoked_rules` matched R.C. 5321.16 by the alias
`"security deposit"` in both Wheeler briefs, in passages that are plain fact
recitation:

> *"Ms. Wheeler signed a lease agreement with Gentile Property Management and
> **paid a security deposit** of …"*

Each produced a full five-element audit, every element `nothing_supplied` — which
reads as a defect in a claim the brief never made. An existing
`requiresApplicabilityReview` flag stopped these becoming challenge cards but did
nothing about the audit itself, and the panel listed the rule among those carried.

**Fix**: a phrase-only match is **not audited at all** — no model call, no element
verdicts, `unmetCount = 0`, `audited: false`. It is reported as a question:
*"The brief uses the phrase 'security deposit' without citing R.C. 5321.16.
Nothing was audited: if you are not invoking this rule, there is nothing here to
answer."* The panel gained a third bucket, **Possible rule matches**, kept
separate from *Unmet elements* and *Rules carried* — counting an unaudited rule
as carried would report a clean audit that never happened.

**Result**: 20 fabricated unmet elements removed across 4 documents; the 4 phrase
matches are still surfaced, as questions. Every citation-matched rule audit is
unchanged.

## 7. Finding 5 — The offline fallback's citation-counting proxy

**Prior entry**: both *false reassurance* (Perry cites in every unit → 0
challenges → looks clean) and *unfair penalties* (Thomas and Moore hit with
`missing_element` and `legal_authority` challenges on uncited procedural
paragraphs).

**Measured**, the passages actually penalized:

| Brief | Passage the stand-in called an uncited proposition |
| --- | --- |
| Thomas | `Now comes Appellant Thomasina Thomas, by and through counsel, and respectfully moves this Court…` |
| Thomas | `Motion for Summary Judgment Standard of Review` (a heading) |
| Thomas | `CMHA is a public housing authority… On December 19, 2024, CMHA issued a decision…` |
| Vourliotis | `Ms. Vourliotis was never served…………………………………………4` (a table-of-contents line) |
| Moore | `Pursuant to Rule 56(B)… respectfully moves this Honorable Court` |

**Root cause**: the only question the stand-in can answer about a passage is
whether it cites anything, and *"cites nothing"* is not *"argues without
authority"*. A caption, a TOC line, a heading, the "Now comes …" preamble and a
dated recitation all cite nothing, and none of them is a vulnerability.

**Fix**, in two parts because each alone makes the other worse:

1. The stand-in raises the point only where the passage is unmistakably asserting
   a legal proposition (`asserts_a_legal_proposition`), and stays quiet otherwise.
   **18 → 4 offline challenges**; Thomas 7 → 1, Moore 3 → 1, Vourliotis 2 → 0.
2. Staying quiet then *creates* the false reassurance, so the run now says which
   it is. A run whose opponent fell back looks identical to one that read the
   brief closely and found nothing, and the second is what an advocate will
   assume. The deterministic assessment carries the difference:

   > **Before**: *"This run raised no challenges against the brief. That is a
   > statement about the review, not a finding that the brief is sound…"*
   >
   > **After**: *"**No model read this brief. The offline stand-in can only see
   > whether a passage cites anything, which is not a reading of the argument.**
   > No challenges were raised. That is a statement about the review, not a
   > finding that the brief is sound…"* — verdict **`not reviewed`**, not
   > `no challenges raised`.

The three cases are now distinct: the check was **off**, no model **read** it, or
a model read it and **found nothing**.

## 8. The architectural ceiling — the 80-unit truncation

**Prior entry**: *"the single most important prerequisite for trustworthy
brief-level evaluation."*

**Measured**. `_unit_payload(units, limit=80)` fed the argument map, opponent,
judge and coach the **first 80 units** of the brief. What each stage actually saw:

| Brief | Units | Read before | Read now | Argument units read | Final quarter read |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hooper opening | 694 | 80 | **234** | **176/289** (was 22) | **53/174** (was 0) |
| Hooper reply | 290 | 80 | **290** | **97/97** (was 29) | **73/73** (was 0) |
| Vourliotis opening | 463 | 80 | **249** | **223/223** (was 10) | **67/116** (was 0) |
| Vourliotis reply | 210 | 80 | **210** | **94/94** (was 24) | **53/53** (was 0) |
| Perry | 440 | 80 | **166** | **112/112** (was 4) | **33/110** (was 0) |
| Gentile | 240 | 80 | **240** | **44/44** (was 4) | **60/60** (was 0) |
| Pine Creek | 191 | 80 | **191** | **32/32** (was 3) | **48/48** (was 0) |
| Thomas | 161 | 80 | **161** | **54/54** (was 23) | **41/41** (was 0) |
| Moore | 106 | 80 | **106** | **18/18** (was 13) | **27/27** (was 1) |

The worst cases are worse than the unit ratio suggests. Because the first 80
units of a filing are caption, tables and procedural history, *Perry* showed the
opponent **4 of its 112 argument units** and *Pine Creek* **3 of 32** — and in
eight of nine briefs the final quarter of the document was never shown at all.
Any finding about those passages was a finding about text nothing had read.

**Fix** (`select_units` in `pipeline.py`): the unit cap is replaced by a
**character budget** (`UNIT_BUDGET_CHARS = 60,000`) spent by priority — headings
first (cheap, and they carry the document's shape), then requested relief,
argument, asserted facts, paragraphs, and citations last since the argument map
already summarizes them. Where a tier does not fit whole it is **sampled evenly
across the document rather than taken from its front**: the last assignment of
error matters as much as the first. Selection stays in document order.

Each stage is also told what it was given (`{brief_coverage}` in the argument
map, opponent, judge, coach and persuasion prompts), so a stage that read a
sample says so rather than reasoning about passages it never saw.

**Result**: ten of fifteen briefs now fit entirely; the longest sends 176 of its
289 argument units with the final quarter represented. Character cost per stage
is bounded and, for the largest brief, roughly 15k tokens.

## 8b. Raising the ceiling — every sample brief read whole

The budget above (60,000 chars) still sampled the four largest briefs. Since the
deployment model is `gpt-5.5`, the ceiling was raised until the whole corpus is
read rather than sampled.

**Measured first.** The initial cost function estimated 80 characters of JSON
envelope per unit; the actual pretty-printed payload is ~145 per unit, so the
largest brief measured as 136,197 characters and *serialized to 201,682*. A
budget that does not mean what it says is worse than no budget, so cost is now
measured as the length a unit adds to the serialized list — the second attempt
(the item's standalone length) was also wrong, missing the two spaces of list
indentation per line, and overshot a 20,000 budget by 267 characters.

**Settings, not constants.** The right value is a property of the deployment's
model, so it is configurable and the run degrades honestly if lowered:

| Setting | Default | Bounds |
| --- | ---: | --- |
| `ARGUMENT_GYM_UNIT_BUDGET_CHARS` | 260,000 | serialized units per stage |
| `ARGUMENT_GYM_UNIT_TEXT_CHARS` | 2,400 | any single unit (longest in corpus: 1,735) |
| `ARGUMENT_GYM_BRIEF_TEXT_CHARS` | 120,000 | raw text for the rule audit and checklist |

**Result — all 10 distinct briefs read whole, no unit truncated:**

| Brief | Units | Sent | Payload | Units truncated |
| --- | ---: | ---: | ---: | ---: |
| Hooper opening | 694 | **694** | 206,143 | 0 |
| Vourliotis opening | 463 | **463** | 134,742 | 0 |
| Perry | 440 | **440** | 134,037 | 0 |
| Hooper reply | 290 | **290** | 73,826 | 0 |
| Gentile | 240 | **240** | 71,437 | 0 |
| Vourliotis reply | 210 | **210** | 54,340 | 0 |
| Pine Creek | 191 | **191** | 55,750 | 0 |
| Thomas | 161 | **161** | 48,704 | 0 |
| Moore | 106 | **106** | 26,838 | 0 |

**A bug the synthetic fixture hid.** At a forced-sampling budget the real corpus
overshot by ~9% (43,683 against 40,000) while the test suite passed, because the
fixture's units were all the same size and a real brief's run from a
13-character citation to a 1,735-character block quote — sampling by the tier
average takes units that cost more than the average. Each sampled unit is now
charged as it is taken, and one that no longer fits is skipped rather than ending
the walk, which would re-bias the selection to the front. Verified against the
corpus at five budgets (260k / 120k / 60k / 40k / 15k): within budget at every
one, with the document's final quarter reached in **25 of 25 documents**.

**Two more truncations found and removed.** `rule_audit.py` and `checklist.py`
read the brief as raw text and each took `brief_text[:12000]` — so an element
pleaded in section V of a 71,450-character brief was reported unpleaded, and a
checklist item asking whether every date in the facts appears in a document in
the file could not see the facts.

**Cost.** Brief-related input per run rises **1.6× across the corpus**, and 3.4×
on the largest brief (299,755 → 1,030,715 chars across the five unit-reading
stages, ~258k tokens). This is the trade the ceiling buys and is the reason the
budget is a setting.

The offline benchmark was re-run afterwards
(`2026-09-08-all-briefs-offline-full-read/`): **15/15 documents byte-identical**
in findings, challenges and unmet elements, confirming the change touches only
what model stages are given.

## 9. Regression coverage added

Every fix is pinned by a test whose fixture is a real passage from the corpus, so
the check cannot quietly regress to the behaviour this entry measured:

| File | Covers |
| --- | --- |
| `apps/validation/test_language.py` | citation splits, subsection headings, drafting notes, a genuinely lowercase sentence, enumerators, and the `(Attached as Appendix A)` regression |
| `apps/validation/test_pleading_form.py` | both real appellate prayers, and a paper that really asks for nothing |
| `apps/argument_gym/test_rule_audit.py` | a phrase match is unaudited and costs no model call; a cited rule still is audited |
| `apps/argument_gym/test_brief_coverage.py` | a corpus-sized brief read whole at the default; the budget measured against the *serialized payload*; the budget held when units vary in size; document order kept; tail reached under forced sampling; argument kept ahead of citations; and each recitation the stand-in used to penalize |

One existing fixture changed: `BRIEF` in `apps/argument_gym/tests.py` gained a
genuinely uncited legal proposition ("Acceptance of rent after service of the
notice bars the eviction as a matter of law"). The old fixture's three offline
challenges came entirely from passages the stand-in should never have flagged, so
the test was asserting the behaviour this entry removed.

---

# Part B — The persuasive communication suite

Added the same day, and the reason the check catalog now has categories at all.

## 10. Three groups of tests

Checks are grouped by the kind of question they ask, because that is the order an
advocate can revise in — getting the law wrong and burying the strongest argument
on page nine are different problems, and a revision pass that mixes them produces
neither.

| Group | Asks | Checks |
| --- | --- | --- |
| **Correctness** | Is the law right? Is the authority controlling? Are the required elements present? | record audit, rule elements |
| **Argumentative completeness** | Does it connect rules to facts, work the hard element, confront adverse authority, answer the obvious counterargument? | opponent / judge / coach |
| **Persuasive communication** | Not whether the brief is right, but whether it lands | the twelve below |
| Your own checks / Form / Language | unchanged | |

## 11. The twelve dimensions

Issue framing · Macro-organization · Paragraph-level organization · Rule
synthesis · Rule-to-fact application · Fact selection and narrative coherence ·
Use of authority · Handling counterarguments · Concision and reader burden ·
Calibrated confidence and credibility · Requested-relief alignment · Emphasis.

Four decisions worth recording:

- **Each dimension is its own check** (`persuasion_issue_framing`, …), so an
  author can run the two they are ready to act on; the group has a
  turn-all-on/off control because a twelve-question suite is one decision about a
  kind of review rather than twelve.
- **They are answered in one model call.** The dimensions are not independent —
  what belongs in the roadmap depends on what the emphasis should be — so twelve
  calls would answer each with the others out of view, at twelve times the cost.
- **Nothing here is an error.** A judgment about how a brief reads is a finding an
  advocate is entitled to disagree with: a weak verdict is a warning, everything
  else a note (codes E/W/I1200-1299).
- **Every selected dimension is reported, including the ones that read well**, and
  without a model each reports itself *not assessed* — a judgment call is the one
  thing a deterministic fallback cannot fake, and silence would read as a pass.
  This is the same principle Finding 5 above turns on.

Results land in `GymRun.check_results` under each dimension's own check id, so a
persuasion finding is attributable to the test the author switched on exactly
like a grammar finding, and the audit panel discloses one group at a time.

## 12. Not yet measured

The suite has **not** been run live against the corpus. Everything recorded in
Part B is design and offline behaviour; the twelve dimensions have no empirical
evaluation of the kind Part A rests on. That is the natural next entry, and it is
now worth doing for the first time, because until the truncation fix a live
persuasion run would have been judging the organization of a brief whose later
two thirds it had never read.

## 13. Suggested next steps

1. **Live run against the corpus** (`--live`, `gpt-5.5`) now that stages read the
   whole brief — the prior entry's live observations (Moore's Rule 56 proof gap,
   Perry's statutory-fit progression) were all produced from the first 80 units,
   and are worth re-establishing against full coverage.
2. **Watch the token bill on the first live run.** The corpus now sends 1.6×
   the brief input it did, and the ceiling is a setting precisely so it can be
   lowered if the trade turns out badly.
3. **Evaluate the persuasion suite** on briefs whose weaknesses are known from
   the revision chronologies: Perry's three snapshots and Pine Creek's are a
   natural before/after for emphasis, concision and issue framing.
4. **Re-check the `confused_words` co-occurrence alerts** (complaint/compliant,
   counsel/council). The prior entry lists them under "meaningful", but they were
   not separately verified here.

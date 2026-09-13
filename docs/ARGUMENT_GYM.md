# Argument Gym

The Argument Gym is a legal-correctness test harness expressed through three
roles: an Opponent brings a challenge permitted by a named test, a Judge rules
only on whether its evidence establishes that challenge, and a Coach proposes
the smallest safe correction. A correctness run may produce zero findings. It
never assigns a numeric score and never edits the document.

It runs in two places, over one pipeline:

- **From Draft mode.** The **Stress test** button in the editor persists the
  open draft, then tests the document that is actually stored. Challenges land
  on block keys, so they can feed the existing revision machinery.
- **As its own mode.** Upload a brief, choose the case context, and run. The
  brief can be an external DOCX, PDF, or text file that HaddenDraft never wrote.

## Sessions

A `GymWorkspace` is a session: one brief, the case context behind it, and every
run over it. Sessions are listed in the panel's left column, filterable by the
case they belong to (`?matterId=`, with `none` for standalone tests) and
searchable by brief or client name. Opening one returns its most recent complete
run with its challenges and dispositions intact, so a session is somewhere to
come back to rather than something to redo. **New** starts a fresh one.

## The author chooses the checks

Every check the gym can make is declared in `apps/argument_gym/checks.py` with
what it needs to run, served at `GET /api/argument-gym/checks/`, and selected per
session. Nothing is added to a run because it seemed useful.

Three states, kept distinct because they mean different things:

| State | Meaning |
| --- | --- |
| `on` | The author selected it and it ran. |
| `off` | The author turned it off. It produced nothing, and nothing is claimed. |
| `unavailable` | Selected, but its precondition is absent — an uploaded brief has no draft session to validate, a session with no court has no filing rules. **This is not a pass**, and the panel says so under its own heading. |

An empty `enabled_checks` means the catalog's defaults, which is what a new
session has. Turning *every* check off stores a sentinel instead, because an
empty list and a new session must not mean the same thing — otherwise the next
run would silently re-enable everything the author switched off.

### Three kinds of question

Checks belong to a **category**, and the category is not decoration: it is the
order an advocate can revise in. Getting the law wrong and burying the strongest
argument on page nine are different problems, and a revision pass that mixes
them produces neither.

| Group | Asks |
| --- | --- |
| **Correctness** | Is the law right? Is the authority controlling? Are the required elements present, and does the record establish what the brief says it does? |
| **Argumentative completeness** | Does the brief connect its rules to its facts? Does it work the difficult element instead of restating the rule? Does it confront adverse authority and answer the counterargument a court will think of on its own? |
| **Persuasive communication** | Not whether the brief is right, but whether it lands: framing, order, synthesis, emphasis, candour. |
| **Your own checks** | The review questions the author wrote. |
| **Form of the filing** | This court's rules and the conventions of practice. |
| **Language** | Sentence-level mechanics, reported as nudges. |

The catalog is served in this order, the panel offers one fieldset per group,
and the results are disclosed one group at a time — so a reader can take on the
kind of problem they are ready to work on rather than one undifferentiated list.

### The catalog

| Check | Group | Kind | Needs |
| --- | --- | --- | --- |
| Brief against the case record | correctness | AI | case materials |
| Elements of the rules the brief invoked | correctness | AI | — |
| Cited authority supports the proposition | correctness | AI + retrieval | — |
| Opponent, judge, and coach | completeness | AI | — |
| The twelve persuasion dimensions | persuasion | AI | — |
| Your own checklist | custom | AI | a checklist |
| This court's filing rules | form | deterministic | a court profile |
| Form of the pleading | form | deterministic | — |
| Draft-mode validation | form | deterministic | a native draft |
| Grammar and mechanics | language | deterministic | — |
| Commonly misspelled and confused words | language | deterministic | — |
| Passive voice | language | deterministic | — |
| Readability | language | deterministic | — |

**Draft-mode validation** is the same `apps.validation.services.validate_document`
Draft mode runs — template data, unresolved placeholders, structure, rendered
DOCX consistency, citation linting, source support, package consistency. It needs
a `DraftDocument`, so on an uploaded brief it reports itself unavailable rather
than silently passing.

**Form of the pleading** (`apps/validation/pleading_form.py`, codes
E/W/I1000-1099) is deliberately separate from the court's own rules: numbered
paragraphs running in order, a prayer for relief, a signature block, exhibit
references that resolve against what was actually attached, no placeholder left
in the text. A finding here never cites a court; a finding from
`court_formatting` always does.

**Language** (`apps/validation/language.py`, codes E/W/I1100-1199) has three
deliberate limits, each of them the reason the module exists:

- *No dictionary spell check.* A general dictionary flags "replevin", "forcible
  entry and detainer", "estoppel", and half of every case name, and an advocate
  who dismisses forty false positives stops reading the check. What runs instead
  is a curated list of the words legal writing actually gets wrong, plus
  real-word confusions (principal/principle) raised only when *both* appear.
- *Passive voice is not an error.* "Service was perfected" is the register a
  court expects. Accepted phrases live in
  `content/drafting-rules/checks/legal-language.yaml`, a session can add the
  phrases its court expects through `checkSettings.passive_voice`, and everything
  else is reported at info severity.
- *Only high-precision grammar.* Doubled words, missing sentence spacing,
  unbalanced delimiters. Subject-verb agreement is left out because getting it
  wrong on legal prose is worse than not checking.

The same principle is what fifteen real Cleveland filings were used to enforce.
Two checks were producing findings at scale and getting nearly all of them wrong:

- *A period in a brief is usually not the end of a sentence.* Case names,
  reporters, courts and parties are abbreviated, so splitting on every period
  manufactured a lowercase "sentence" starting mid-citation — "of Am., 159 Ohio
  App.3d 410", "v Williams, 3 Ohio App.3d 288", "of City of Raleigh, 595 F." It
  produced 71 findings across those briefs and not one was an error. A period
  now ends a sentence only when an ordinary lowercase word precedes it: a legal
  abbreviation is short and capitalized, which separates the two without a list
  to keep up to date. Drafting notes left in the text (`[from who?]`) are removed
  before splitting, because the placeholder check already reports them and the
  sentence they interrupt is not a second problem.
- *Delimiters are scanned, not counted.* "6 closing parenthesis(s) with nothing
  opened" is both unactionable and usually wrong — it is a caption's column of
  `)` or the enumerators in "1) … 2) … 3)". The check now scans for the position
  that is actually unbalanced, quotes the passage, and recognizes an enumerator
  only at a closer it could not match. Nothing is stripped from the text first:
  removing "A)" would leave "(Attached as Appendix" reported as unclosed. On the
  same fifteen briefs this turned 13 caption false positives into 20 findings
  that each name a real unclosed delimiter.

**Prayer for relief** knows how an appellate brief asks. "Appellant requests this
Court reverse … and remand" and "respectfully asks this Honorable Court to
REVERSE" are prayers; four real appellate briefs were reported as asking the
court for nothing because the patterns only recognized a trial-court prayer.

## The pipeline

```text
brief ingestion and deterministic citation anchors
  -> the author's selected deterministic checks
  -> record target gate: fact passages + explicit record anchors
  -> Opponent tests each atomic material record claim
  -> local cited-authority resolution
  -> bounded CourtListener fallback for prioritized local misses (if configured)
  -> Opponent tests each resolved proposition/citation/source triple
  -> rule-elements test
  -> Judge sustains, reserves, or overrules each candidate independently
  -> Coach proposes fixes only for sustained/reserved visible findings
  -> stable per-test results and CI-style summary

The optional adversarial stress test retains the broader argument-map,
research, attack, and ranking flow. It is not part of the correctness verdict.

Citation extraction is hybrid: Eyecite supplies its maintained U.S. reporter
grammar and full-case spans, while local patterns retain Ohio Revised Code and
OCR-tolerant forms. Overlapping recognizers collapse to one document-ordered
target. The source-specific authority check first resolves against the local
knowledge base; CourtListener is eligible only for unresolved case citations
with a volume, reporter, and page.
```

Compliance runs first and without a model, so an advocate gets that answer even
if every model call after it fails.

Opponent, Judge, and Coach are **separate model calls**. One call asked to
attack, weigh, and answer produces attacks it has already decided are
answerable, which is the failure this feature exists to prevent.

Malformed or incomplete model batches fail closed. A selected check whose model
stage cannot run is reported as unavailable; a deterministic fallback does not
manufacture findings to make the report look populated.

An empty target list is a valid completed test inventory. For product reruns,
record targets are cached with the brief checksum and target-contract version;
editing the brief or changing that version invalidates the cache. Held-out
evaluation still treats a target that appears in one repeated run and disappears
in another as instability rather than silently dropping it from the metric.

**What the offline stand-in may claim.** Without a model the only question the
opponent can answer about a passage is whether it cites anything, and "cites
nothing" is not "argues without authority": a caption, a table-of-contents line,
a heading, the "Now comes …" preamble and a dated recitation of what happened all
cite nothing, and none of them is a vulnerability. Real filings were reported as
exposed on their opening paragraph for exactly that reason. The stand-in now
raises the point only where the passage is unmistakably asserting a legal
proposition, and stays quiet elsewhere — which cut the spurious offline
challenges across the fifteen briefs from 18 to 4.

Staying quiet then creates the opposite risk, so the run says which it is: a run
whose opponent fell back looks identical to one that read the brief closely and
found nothing, and the second is what an advocate will assume. The deterministic
assessment carries the difference — verdict **"not reviewed"**, and "No model
read this brief. The offline stand-in can only see whether a passage cites
anything, which is not a reading of the argument."

Prompts are file-backed in `prompts/argument_gym.*.yaml`. Changing a stage's
required variables means changing the YAML and the call site in
`apps/argument_gym/pipeline.py` together.

## Models

| Model | What it holds |
| --- | --- |
| `GymWorkspace` | One brief under test plus the case context it is tested against. A workspace with a `Matter` is governed by that case's access; a workspace without one is private to its owner. |
| `GymDocument` | The brief, or a piece of the case record. `source_type` says whether the text is uploaded, a `DraftDocument`, or a reference to a case-file document. An exhibit split out of a filing keeps its `page_range` and its `split_from`. |
| `CourtProfile` (in `apps.rules`) | A court's identity and its filing-format requirements, with its own verification status. It lives outside the gym because draft validation wants the same answers. |
| `GymRun` | One pass of the pipeline: the brief snapshot it read, which checks ran and why the rest did not, the findings each produced, the rule-element audit, the checklist results, the research it ran, its opening assessment, and how it compares with the previous run. |
| `GymChecklist` | An advocate's own review questions, in their words. |
| `LegalRuleProfile` (in `apps.rules`) | A rule, how to tell it was invoked, and the elements it requires — with its own verification status. |
| `GymChallenge` | One opposition argument, judged and answered, anchored to a passage. Carries the advocate's disposition, which survives reruns. |

Gym state is deliberately **not** `DraftDocument.validation_flags` or a
`ChatConversation`. A challenge has a disposition and a rerun history; a
validation flag and a chat message have neither.

## Runs are started, not awaited

A run is eight sequential model calls and several retrieval rounds — minutes,
not seconds. Holding the HTTP request open for that does not merely feel slow:
gunicorn kills the worker at its timeout, and **a killed worker returns no
headers at all**, so the browser reports a CORS failure rather than the timeout
it actually is. That is what `POST /runs/` did before this was fixed.

So the request starts the run on a background thread and returns it immediately:

| Status | Code | Meaning |
| --- | --- | --- |
| `pending` / `running` | 202 | Accepted. Poll `GET /runs/<id>/`. |
| `complete` | 200 | Finished. |
| `failed` | 502 | Recorded on the run with a reason. |

`GymRun.status` already existed for this; the pipeline is unchanged. Each stage
is saved to `stage_trace` as it finishes, so a client polling can name the stage
rather than showing an unlabelled wait.

A replica that dies mid-run would otherwise leave a row claiming to be running
forever, so `fail_if_stalled` reports a run past
`ARGUMENT_GYM_RUN_TIMEOUT_SECONDS` (default 30 minutes) as failed, saying it was
interrupted and that nothing was written to the draft.

`ARGUMENT_GYM_BACKGROUND_RUNS=False` runs the pipeline inline, which is how the
tests assert on a finished run.

## The opening assessment

Each run writes one paragraph, stored on the run and shown at the top of both
the panel and the stress-test report: whether the brief persuades as written,
and the two or three flaws that most need addressing. It carries a short verdict
phrase — a characterization such as "persuasive but exposed on the notice
defect", never a score, grade, or rating. The deterministic fallback builds the
same paragraph from the challenges' severities when no model is available.

## Jurisdiction and the court's filing rules

A session resolves two related things, each either detected or set by hand.

**Jurisdiction** (`jurisdiction_mode`) can be typed in: state, county, and then
either a municipality or a division, depending on the court type. A municipality
identifies a trial court and means nothing for an appellate district, so the
form asks for a division instead and a municipality sent for an appellate court
is dropped rather than stored.

**Whose filing rules apply** (`court_rule_mode`) is `auto`, `manual`, or `off`.
Automatic detection matches the brief's caption — and, failing that, the case
record — against maintained `CourtProfile` aliases. It is string matching, not
inference, so a run always reports the phrase that decided it, and reports
nothing rather than guessing when nothing matches. Only the first few thousand
characters are searched: a case cited on page nine must not outrank the court
the paper is filed in.

## Filing-format checks

`apps/validation/court_formatting.py` checks a document against the selected
profile with no model call: required elements for that pleading type, minimum
type size, permitted typefaces, line spacing, margins, and page limits. Rule
codes are E/W/I900-999.

Two rules govern the report:

- **An unverified profile can only warn.** Its requirements were not read off the
  court's own local rules, so its findings are downgraded and labelled as coming
  from a starter profile.
- **A property that could not be measured is reported as unmeasured, never as a
  pass.** A DOCX has no page count until something renders it; a scanned PDF has
  no type size to read. Silently skipping either would tell an advocate their
  fifty-page brief fits in fifteen.

Profiles are file-backed in `content/court-rules/*.yaml`, seeded into
`CourtProfile` by `sync_content_library`, and edited in Django admin under
**Court profiles**. Editing one there marks it `is_locally_edited`, and
re-seeding — even with `--update-court-rules` — skips it. See
[`content/court-rules/README.md`](../content/court-rules/README.md) for the
schema.

## Large filings and exhibits

A filed brief usually arrives with its exhibits attached, and most of the file
is not the brief. Pushing three hundred pages of a lease and a rent ledger
through a model to find the argument is both expensive and worse at finding it.

`split_brief_and_exhibits` reads the boundary off the pages themselves: a
certificate of service ends the brief, and an exhibit cover sheet starts the
attachments. An index of exhibits *inside* the brief does not count. Where
nothing marks the boundary, the first `BRIEF_PAGE_LIMIT` (30) pages are the
brief. The reason is recorded either way, so the split is reviewable.

Each attachment becomes its own `GymDocument` with `role="case_record"`,
`split_from` pointing at the upload, and its page range — so it is available as
material the record audit can read, and excludable like any other. A page limit
is then checked against the brief, not against what was stapled behind it.

Beyond the split, `MAX_BRIEF_CHARS` caps what any run reads, and a brief that
hit the cap says so rather than reporting a clean result on a partial read.

### What a stage is actually shown

Splitting the exhibits off is not enough on its own. Every model stage used to
read the **first 80 units** of the brief, and a filing is not 80 units: a real
appellate brief ran to 694, so the argument map, the opponent and the judge saw
the caption, the procedural history and the opening facts, and never saw a word
of the argument they were asked to attack. Any finding about the later two
thirds of that brief was a finding about text nothing had read.

`select_units` replaces the cap with a **character budget** spent by priority —
headings first, because they are cheap and carry the document's shape, then
requested relief, argument, asserted facts, paragraphs, and citations last since
the argument map already summarizes them. Selection stays in document order.

Three settings govern it, because the right value is a property of the
deployment's model rather than of the gym:

| Setting | Default | What it bounds |
| --- | --- | --- |
| `ARGUMENT_GYM_UNIT_BUDGET_CHARS` | 260,000 | the serialized units one stage is given |
| `ARGUMENT_GYM_UNIT_TEXT_CHARS` | 2,400 | any single unit, so one block quote cannot crowd out the brief |
| `ARGUMENT_GYM_BRIEF_TEXT_CHARS` | 120,000 | the raw text the rule audit and the checklist read |
| `ARGUMENT_GYM_COURTLISTENER_MAX_CITATIONS` | 3 | unique, prioritized local citation misses sent to CourtListener per run; one lookup plus at most three opinion fetches |
| `COURTLISTENER_API_TIMEOUT_SECONDS` | 15 | each CourtListener lookup or opinion request |

`COURTLISTENER_API_TOKEN` enables the local-miss fallback. It uses the
CourtListener v4 citation-lookup endpoint in one batch, fetches at most one
opinion per resolved citation, caches successful sources for seven days, and
does not retry a 429 within the run. `COURTLISTENER_API_BASE_URL` defaults to
the public v4 endpoint. The token stays in the environment and is never stored
in a run trace.

## Reviewing an experiment by hand

Saved experiment runs include the complete prompt and response for every model
call. Generate a compact Markdown review without changing the run:

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/inspect_correctness_run.py \
  lexis_real_briefs/experiment/results/<run-directory> > /tmp/gym-review.md
```

Start with the check status and visible-findings tables. Then inspect every row
in the Judge contract audit: expected and returned counts must match, and
missing IDs, extra IDs, blank reasons, and adverse rulings without evidence must
all be zero. The transcript column names the corresponding `call-*.json`; open
it to compare the exact candidate evidence in `messages` with the Judge's raw
`response`. Finally compare the same `checkId / targetId` between control and
mutant rather than matching generated prose. The final context-window table uses
a conservative three-characters-per-token estimate and reserves 16,000 tokens
for output; override either assumption with `--context-window` or
`--output-reserve` when qualifying another deployment.

To qualify a new Judge without rerunning ingestion, retrieval, Opponent, and
Coach, replay up to sixteen candidates from an existing Judge transcript. The
hard eight-candidate batch size still applies:

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/replay_correctness_judge.py \
  lexis_real_briefs/experiment/results/<old-run>/<fixture>/call-005.json \
  --model <deployment-name> \
  --output lexis_real_briefs/experiment/results/<qualification>.json
```

For Gemini's OpenAI-compatible endpoint, also pass
`--base-url https://generativelanguage.googleapis.com/v1beta/openai/`,
`--api-key-env GEMINI_API_KEY`, and `--reasoning ''`.

The defaults are set so that **every brief in the local corpus is read whole** —
the largest is 694 units and 71,450 characters, serializing to 206,143 characters
(~52k tokens), which a large-context model such as gpt-5.5 has room for. A
deployment pointed at a smaller context lowers them, and the run reports that it
sampled rather than failing.

Sampling is therefore the safety valve for a filing larger than any budget, not
the normal case. Where it happens the selection is **spread across the document
rather than taken from its front**, and each unit is charged as it is taken: a
brief's units run from a thirteen-character citation to a block quote, so
sampling by the tier's average overshot the budget by a few percent on real
briefs while passing against a fixture whose units were all the same size. Cost
is measured as the length a unit adds to the serialized payload, not estimated
from it — two earlier approximations were both wrong in the direction that
matters, and a budget that does not mean what it says is worse than no budget.

Every stage is also told what it was given (`{brief_coverage}`), so a stage that
read a sample says so instead of reasoning about passages it never saw.

The element audit and the author's checklist read the brief as raw text rather
than as units, and each read only its first 12,000 characters before
`ARGUMENT_GYM_BRIEF_TEXT_CHARS` existed — so an element pleaded in section V of a
seventy-page brief was reported unpleaded, and a checklist item asking whether
every date in the facts appears in a document in the file could not see the facts.

## Rules the brief invoked

A cited rule is a candidate for an element audit. Applicability and the party's
burden still need review before a missing element is treated as a defect.

`apps/rules/legal_rules.py` detects which maintained rules a brief invoked —
deterministically, by citation pattern or by a well-known phrase — and reports
which words decided it. A rule invoked only by a phrase is labelled as such:
"three-day notice" in a sentence about the other side's notice is not the same as
citing the statute.

`apps/argument_gym/rule_audit.py` then asks two **separate** questions per
element: is it *pleaded*, and is it *supported*. An assertion is not support, and
the audit never merges the two. A deterministic pattern miss reports uncertain
wording rather than absence. Missing record documents and partial support remain
visible in the audit but do not by themselves create adverse challenge cards.
Conclusive adverse assessments can still become `GymChallenge` records for the
ranked cards, prep sheet, and revision plan.

**A phrase match is not audited at all.** A real brief that recited paying a
security deposit drew a full R.C. 5321.16 audit whose every element came back
"nothing supplied" — which reads as a defect in a claim the brief never made.
A rule matched only by a phrase now costs no model call and produces no element
verdicts: it is reported as a question ("the brief uses the phrase X without
citing R.C. …; if you are not invoking this rule there is nothing here to
answer"), carries `audited: false`, and the panel lists it under **Possible rule
matches** rather than among the rules carried or the rules at issue. Counting it
as carried would report a clean audit that never happened.

### Reusing the decision tables

Where a published `DecisionTable` row already encodes a rule's requirements, a
profile names it instead of restating it:

```yaml
decision_table_key: eviction_answer_issue_selection
decision_table_row: notice_defect
```

The row's `missing_facts` become elements, and the facts its conditions depend on
become elements too — the same requirements seen from the pleading side rather
than the issue-selection side. Those merge with the profile's own elements.

Profiles are file-backed in `content/legal-rules/*.yaml`, seeded into
`LegalRuleProfile`, and edited in Django admin under **Legal rule profiles**.
Like court profiles, each states its own `verification`, and only a verified
element list reports at error severity. **Every profile shipped here is
unverified**: the elements are substantive law, and a wrong element list tells an
advocate their pleading is complete when it is not.

## The persuasive communication suite

Twelve dimensions, in `apps/argument_gym/checks.py` as `PERSUASION_DIMENSIONS`
and run by `apps/argument_gym/persuasion.py`:

| Dimension | The question it asks |
| --- | --- |
| Issue framing | Does the brief identify the real dispute early and frame it around the favorable legal question? |
| Macro-organization | Are arguments ordered logically and by importance? Can the reader see the roadmap? |
| Paragraph-level organization | Do paragraphs have discernible propositions or topic sentences, and develop one point at a time? |
| Rule synthesis | Does the writer synthesize authorities into a rule rather than serially summarize cases? |
| Rule-to-fact application | Is the reasoning explicit — "because X fact satisfies Y element" — rather than leaving the inferential step to the court? |
| Fact selection and narrative coherence | Are legally significant facts foregrounded and organized in a comprehensible chronology or theory? |
| Use of authority | Are important propositions backed by strong authorities placed where they actually matter, rather than citation dumping? |
| Handling counterarguments | Does the brief acknowledge and answer the strongest objection rather than arguing past it? |
| Concision and reader burden | Does it say the same thing once, in the right place, without unnecessary throat-clearing? |
| Calibrated confidence and credibility | Does it distinguish strong propositions from uncertain ones and avoid overclaiming? |
| Requested-relief alignment | Does the argument actually lead to the precise thing the brief asks the court to do? |
| Emphasis | Does the document devote its space to the issues that matter rather than treating every point as equally important? |

Four things about how it runs:

- **Each dimension is its own check.** They appear as twelve entries in the
  catalog (`persuasion_issue_framing`, `persuasion_emphasis`, …), so an author
  can run the two they are ready to act on. The panel offers the group a
  "turn all on/off" control, because a twelve-question suite is one decision
  about a kind of review rather than twelve separate ones.
- **They are answered in one model call.** The dimensions are not independent:
  what belongs in the roadmap depends on what the emphasis should be, and
  whether the concision is a problem depends on which passages matter. Twelve
  calls would answer each with the others out of view, and cost twelve times as
  much to do it worse.
- **Nothing here is an error.** A judgment about how a brief reads is the kind
  of finding an advocate is entitled to disagree with, so a weak verdict is a
  warning and everything else is a note. Codes are E/W/I1200-1299.
- **Every selected dimension is reported, including the ones that read well.**
  A suite that only lists problems cannot be told apart from a suite that failed
  to run. Without a model, each dimension reports itself *not assessed* — a
  judgment call is the one thing a deterministic fallback cannot fake, and
  silence would read as a pass.

Results land in `GymRun.check_results` under each dimension's own check id, so a
persuasion finding is attributable to the test the author switched on exactly
like a grammar finding, and the audit sidebar groups it under its category with
everything else.

Why the opponent is not asked this instead: an opponent looking for a weakness
calls bad organization a legal problem, which sends the advocate to rewrite an
argument that only needed moving.

## Your own checklist

A `GymChecklist` is prose, one review question per line. "Every date in the
statement of facts appears in a document in the file" is a legitimate item — and
answering it means going and reading the file.

So the model answering an item can look things up first, through three bounded,
read-only tools:

| Tool | What it reaches |
| --- | --- |
| `search_law` | The maintained research libraries, through `augmented_search` |
| `search_case_record` | The case materials this session is allowed to read |
| `quote_brief` | Passages of the brief itself |

The protocol is JSON in the message body rather than provider-native function
calling, matching the rest of the codebase: the same loop has to work against any
OpenAI-compatible endpoint. Lookups are capped per item, run under the session's
own matter access, and every one is reported with the query it asked — an
advocate can see what an item read before believing what it says. A failed item
becomes a challenge. Without a model, items are reported `needs_review` with the
passages that matched, never `pass`.

Checklists are the author's own; `shared: true` offers one to the deployment,
readable by everyone and editable only by its author.

## Anchors

A native draft is already addressable: every section is a `DocumentComponent`
with a stable key. An uploaded brief is not, so `apps/argument_gym/ingestion.py`
gives it a lightweight structure — section, paragraph, argument, asserted fact,
citation, requested relief — each with a run-local id and a locator:

```json
{"section": "III.A", "paragraph": 14, "page": 7, "excerpt": "..."}
```

DOCX structure comes from heading styles and paragraph numbering; PDF keeps page
locations. This is not a legal knowledge graph and should not grow into one: it
exists so a card can say where the problem is and a reader can find it again.

## Case materials

Existing case files are **referenced, never copied**. A run resolves matter
documents through `apps.matters.document_context`, under the same access control
as the rest of the app, and reads their text only at the moment a stage needs
it. The gym stores a pointer and — when the advocate excludes a document — that
decision. Ranking reuses the case-chat salience ranking rather than inventing a
second answer to the same question.

## Reruns

A rerun snapshots the current component versions and compares its challenges
against the previous run's by fingerprint. A challenge the advocate **dismissed**
carries that dismissal forward: the argument has not changed. A challenge marked
**addressed** that comes back is reopened and flagged as recurring, because the
brief moved and the challenge survived it. Challenges the previous run raised
that this one does not are reported as no longer raised.

## Artifacts

All three are projected from stored challenges, so they cannot disagree with
each other or with the cards:

- **Opposition prep sheet** — one row per challenge: likely opposition point,
  strongest authority, strongest adverse record material, current response,
  suggested response, remaining vulnerability.
- **Stress-test report** — executive summary, ranked vulnerabilities, challenges
  already handled well, unresolved research gaps, materials reviewed.
- **Revision plan** — block-scoped instructions. Actionable on a native draft
  through `apps.validation.revision.apply_revision_plan`; copyable text for an
  external brief.

The one model call among them writes the narrative summary, once per run.

## Applying a revision

Nothing auto-edits. "Add to revision plan" queues a challenge; opening the plan
shows editable, block-scoped instructions; applying it runs each one through
`regenerate_draft_block`, which records a `DraftOperation` and a new
`ComponentVersion`. The challenge is then marked addressed and linked to the
operation that answered it.

## API

| Method and path | Purpose |
| --- | --- |
| `GET /api/argument-gym/checks/` | The check catalog, its groups, and its defaults |
| `GET POST /api/argument-gym/checklists/` | List or create your own checklists |
| `GET PATCH DELETE /api/argument-gym/checklists/<id>/` | Read, edit, or remove one |
| `GET /api/argument-gym/courts/` | Court profiles and which court types use a municipality |
| `GET /api/argument-gym/legal-rules/` | The rules the element audit recognizes, and what each requires |
| `GET POST /api/argument-gym/workspaces/` | List (filter with `matterId`, `q`) or create a session |
| `GET /api/argument-gym/workspaces/<id>/court-detection/` | What detection would pick for this brief, and why |
| `GET PATCH DELETE /api/argument-gym/workspaces/<id>/` | Read a session with its latest run; set jurisdiction, court, selected checks, check settings, and checklist; or remove it |
| `GET POST /api/argument-gym/workspaces/<id>/documents/` | Upload a brief or case file, or attach a draft |
| `GET POST /api/argument-gym/workspaces/<id>/materials/` | List available case materials, or exclude one |
| `GET POST /api/argument-gym/workspaces/<id>/runs/` | List runs, or launch one |
| `PATCH DELETE /api/argument-gym/documents/<id>/` | Rename or remove a gym document |
| `GET /api/argument-gym/runs/<id>/` | One run with its challenges |
| `GET /api/argument-gym/runs/<id>/artifacts/<prep_sheet\|report>/` | Output artifacts |
| `GET POST /api/argument-gym/runs/<id>/revision/` | Build or apply a revision plan |
| `POST /api/argument-gym/challenges/<id>/` | Set a disposition |
| `POST /api/argument-gym/challenges/<id>/research/` | Research one challenge further |
| `POST /api/drafts/<id>/stress-test/` | Run the gym on a native draft |

Every lookup resolves the workspace's linked matter through
`apps.matters.services.user_can_access_matter`, so a case a viewer cannot reach
is a gym run they cannot reach either.

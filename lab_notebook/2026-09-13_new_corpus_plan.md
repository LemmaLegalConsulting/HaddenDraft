# New Corpus Plan: Sequestered Lexis Housing/Property Pairs

**Date:** 2026-09-13
**Status:** authoring workspace prepared; mutations are not frozen
**Working label:** `new-corpus-plan`
**Source delivery:** `lexis_real_briefs/` (Lexis delivery dated 2026-09-08)

The private, git-ignored authoring workspace is
`lexis_real_briefs/experiment/heldout-authoring-20260913/`. It contains the
protected controls, editable mutant copies, proposed exact-span edits,
authority references, mutation register, sequester audit, and mechanical
authoring validator.

## 1. Purpose

Build approximately eight new control/mutant brief pairs for a fresh evaluation
of the redesigned Argument Gym correctness mode. The suite should test the
Gym's unit-test and linting floor: whether a named check detects one planted,
evidence-verifiable defect on a stable target while leaving the clean original
alone.

This is preferable to changing the experiment to conventional mortgage
foreclosure. The local legal corpus is strongest on landlord-tenant law,
tenant rights following foreclosure, and land installment contracts. It is not
a comprehensive foreclosure-defense corpus. The proposed briefs stay closer to
housing and property practice, while source-bound authority checks do not
require the system to reconstruct an entire field of law.

## 2. Why these briefs were not already run through the Gym

The prior Lexis mutation experiment reduced 53 filings in 44 case families to
eight authored fixtures, `F001` through `F008`. Those eight fixtures are listed
in `lexis_real_briefs/experiment/fixtures_index.json` and their mutations are
defined in `lexis_real_briefs/experiment/mutations.yaml`. Prior experiment runs
read those fixture directories, not every file in the Lexis delivery.

The candidate families below do not appear among the eight authored fixtures
and have no control/mutant results in the prior experiment. Their presence in
`normalized_preview/` does **not** mean they were run through the Gym. That
directory was produced by deterministic mechanical normalization so filings
could be inventoried and screened. `case_families.json` records the eligibility
screen; it is not Gym output.

Accordingly, the defensible description is:

> These filings were mechanically normalized and screened during corpus
> construction, but were not mutated and were not previously run through the
> Argument Gym.

They should be described as **sequestered from prior Gym runs**, or as a **fresh
evaluation set**, rather than as documents no researcher or program has ever
examined. They are not pristine in the strongest possible sense: two were
identified as unused eligible families, and the others were recorded as outside
the earlier eviction-central stratum.

Before freezing the suite, confirm again that none of the candidate source
hashes appears in any prior Gym run artifact. Save that audit and the selected
source hashes with the new fixture register.

## 3. Candidate set

Use at most one filing per lawsuit so that the eight observations represent
eight independent case families rather than several correlated briefs from the
same dispute.

| Candidate family | Proposed filing | Principal subject | Earlier screening status |
|---|---|---|---|
| *Jacob v. Fadel* | `BRIEF OF APPELLEES(2).docx` | Eviction-related fiduciary-duty claims | Passed the original eviction-centrality screen; left unauthored because no clean mutation target had yet been selected |
| *DeBartolo v. Dussault Moving, Inc.* | `Assignments Of Error And Brief Of Appellants.docx` | Self-help, lease rights, and receivership | Passed the original eviction-centrality screen; left unauthored because no clean mutation target had yet been selected |
| *Texlo v. Gator Hillcrest* | `REPLY BRIEF FOR DEFENDANT-APPELLANT GATOR HILLCREST PARTNERS LLLP.docx` | Commercial landlord-tenant law and lease waiver | Substantive and readable; excluded because possession was not central |
| *Lee v. Wallace* | `Appellee, Nancy Wallace's Brief.docx` | Tenant status under R.C. 5321.01 | Replaced *Presser* after the hash audit found that *Presser* had already been used as mechanical fixture `M09` |
| *Carroll v. Houser* | `DEFENDANT'S REPLY BRIEF IN SUPPORT OF MOTION FOR SUMMARY JUDGMENT.docx` | Landlord premises liability | Substantive and readable; excluded because eviction was secondary; accompanying material may support a bounded record test |
| *Crenshaw v. Integrity Realty* | `Brief fof Appellee.docx` | Prior eviction and res judicata | Substantive and readable; excluded because eviction was secondary |
| *Estate of Notarian* | `PLAINTIFFS REPLY TO DEFENDANT'S BRIEF IN OPPOSITION TO PLAINTIFF'S MOTION FOR PARTIAL SUMMARY JUDGME.pdf` | Estate-property management and forcible entry and detainer | Replaced *Solomon* after the hash audit found that *Solomon* had already been used as mechanical fixture `M06` |
| *Jackson v. Carlton Townhouse Condominium Association* | `Appellants' Brief.docx` | Condominium and property dispute | Substantive and readable; excluded because eviction was secondary |

This is a broader **housing/property** stratum, not a second sample meeting the
old definition of `appellate_eviction`. Only *Jacob* and *DeBartolo* satisfy the
old registered centrality threshold. Results must not be pooled with the old
eight as though all sixteen were selected under the same inclusion rule.

The exact-hash audit found no prior Gym input match for the eight controls now
accepted into the authoring workspace. The audit rejected *Presser* and
*Solomon* because their normalized hashes occur in earlier mechanical fixtures
and result artifacts. If another filing lacks a clean evidence-bound target,
replace it with a previously unused case family; do not weaken the mutation
rules merely to reach eight.

## 4. Mutation design for the correctness floor

Each mutant changes exactly one material proposition. Its control is the
normalized authentic filing. Captions, facts unrelated to the target, relief,
attachments, whitespace, and all other authorities remain identical. Mutation
identity is recorded as `checkId + targetId`, with a gold proposition and exact
evidence span selected before the Gym is run.

### 4.1 Primary class: authority support

Authority support is the best fit for most candidates because appellate briefs
contain identifiable proposition-to-citation relationships and the redesigned
check asks a bounded question:

> Does the cited authority support the material legal proposition for which
> this brief uses it?

Good mutations include:

1. **Holding overstatement:** strengthen a supported proposition just beyond
   what the cited opinion establishes, leaving the citation unchanged.
2. **Wrong source attribution:** preserve the proposition but attach it to a
   different authority already present in the brief that does not establish it.
3. **Opinion-part mismatch:** remove an accurate dissent, concurrence, or
   plurality qualifier so nonbinding reasoning is presented as the court's
   holding.
4. **Applicability mismatch:** substitute a real but inapplicable authority,
   such as a materially different procedural posture or governing rule. Mere
   preference for a more authoritative case is not a correctness defect.
5. **Citation identity defect:** make a minimal reporter, year, or court change
   that resolves to the wrong authority while still looking facially plausible.
   This is useful for testing citation extraction and resolution, but only if
   the resulting citation has a determinate gold answer.

For every authority mutation:

- extract citations mechanically first, with local Ohio patterns supplementing
  a library such as Eyecite;
- resolve the citation against the local knowledge base first;
- use the Free Law Project/CourtListener fallback only when local resolution
  fails, and cache the resolved source because the API key is rate-limited;
- save the cited proposition, the relevant source passage, court, date,
  precedential status, and retrieval provenance;
- require an attorney to verify that the control is supported and the mutant is
  overstated, inapplicable, contradicted, or otherwise defective;
- exclude a pair if source text cannot be retrieved. Unverifiable is `REVIEW`,
  not a gold `MUST_FIX`.

### 4.2 Secondary class: cited record support

Use this only when the filing has a fixed, readable record attachment that
directly confirms or contradicts an atomic, material claim. A suitable mutation
changes one date, amount, event, quotation, or manner of service while retaining
the same record citation and byte-identical attachments.

Example pattern:

> Control: the notice was posted on June 28.
> Mutant: the notice was sent by certified mail on June 28.
> Fixed evidence: the cited affidavit and photographs establish posting.

Do not use absence from a partial record as proof of falsity. A `NOT_FOUND`
result with incomplete coverage can support only `REVIEW`. Prefer direct
contradiction or direct cited-support mismatch.

*Carroll v. Houser* is the first candidate to inspect for a genuine bounded
record target. Do not infer that its accompanying material is adequate until
the exact cited exhibit and passage have been verified.

### 4.3 Secondary class: rule elements

Use a missing-element mutation only when all of the following are true:

- the brief invokes a rule represented by a verified `LegalRuleProfile`;
- the element list is supported by published authority;
- the control contains a clear application of the element to facts;
- deleting or weakening that application leaves exactly one material defect;
- the mutation does not merely make the advocacy less persuasive.

The cleanest form deletes one rule-to-fact application sentence while leaving
the rule statement, citations, other elements, and requested relief untouched.
If rule applicability is debatable, do not label the mutant `MUST_FIX`.

### 4.4 Excluded mutation classes

Do not include these in the primary correctness experiment:

- removal of a counterargument;
- weaker organization, roadmap, tone, or persuasion;
- failure to cite the best available authority when the cited authority is
  adequate;
- unsupported-fact mutations that rely on incomplete retrieval;
- invented cases or obviously malformed citations;
- temporal-current-law mutations unless an attorney verifies the historical
  rule and operative date;
- more than one defect in a mutant.

Those may be useful later for an optional adversarial Stress Test, but they do
not belong in the correctness floor.

## 5. Tentative composition

The qualified authoring set contains **eight authority-support pairs**. The
review did not find a defensible one-edit rule-element or cited-record mutation
in these eight independent case families. DeBartolo invokes the verified
R.C. 5321.15 profile, but every relevant element is repeated, so deleting one
sentence would not actually omit an element from the brief.

Eight independently verified authority-support pairs are preferable to forcing
artificial category balance. Report this experiment as an evaluation of the
authority-support correctness floor, not as validation of every named Gym
check. Rule-elements performance remains supported by the separate synthetic
qualification suite and requires future held-out human-authored coverage.

## 6. Qualification and freezing procedure

For each proposed filing, complete these steps before viewing any Gym output:

1. Record source and normalized-text SHA-256 hashes.
2. Confirm the source hash does not appear in prior Gym run inputs.
3. Extract all citations and record citations mechanically.
4. Measure local authority resolution coverage; use the rate-limited external
   fallback only for unresolved citations being considered as targets.
5. Identify one atomic material proposition with bounded evidence.
6. Draft one minimal mutation and verify that its target text occurs exactly
   once.
7. Have an attorney verify both halves: the control does not contain the target
   defect, and the mutant does.
8. Save exact gold evidence spans and allowed alternative spans.
9. Freeze the source, prompts, code revision, corpus snapshot, model settings,
   and mutation register.
10. Only after freezing, run control and mutant independently and in blinded,
   randomized order.

The person reviewing gold labels should not see Gym outputs. If iteration on the
new Gym uses any of these pairs, move those pairs into a development set and do
not report them later as held out.

## 7. Measurement

The unit is a stable named test result, not free-form criticism.

For each `checkId + targetId`, record:

- **mutation detection:** mutant receives the expected `MUST_FIX`;
- **matched specificity:** control does not receive `MUST_FIX` on that target;
- **stability:** repeated runs return the same disposition for that target;
- **noise:** additional `MUST_FIX` findings not part of the planted target;
- **execution state:** ran, turned off, or could not run;
- **source coverage:** local resolution, external fallback, or unresolved.

The principal paired outcome remains:

| Control target | Mutant target | Interpretation |
|---|---|---|
| no `MUST_FIX` | `MUST_FIX` | discriminating |
| no `MUST_FIX` | no `MUST_FIX` | missed |
| `MUST_FIX` | `MUST_FIX` | non-discriminating |
| `MUST_FIX` | no `MUST_FIX` | reversed; investigate |

Do not impose a minimum number of findings, cap verified defects, or score
top-N prose overlap. A clean control is allowed to produce zero findings.

## 8. Claims this suite can support

If properly verified and frozen, this suite can support a modest claim about
whether the redesigned named checks discriminate between authentic filings and
minimal evidence-bound mutations in a small Ohio housing/property sample.

It cannot by itself support claims about:

- general brief quality or persuasiveness;
- all Ohio eviction practice;
- conventional mortgage-foreclosure defense;
- completeness of the local authority corpus;
- correctness of findings outside the planted targets; or
- performance on documents used to tune the redesigned Gym.

## 9. Related materials

- `lexis_real_briefs/experiment/REGISTER.md` — prior registered experiment and
  inclusion criteria
- `lexis_real_briefs/experiment/fixtures_index.json` — the eight prior fixtures
- `lexis_real_briefs/experiment/mutations.yaml` — mutations already exposed to
  prior Gym runs
- `lexis_real_briefs/experiment/case_families.json` — all 44 families and
  recorded screening decisions
- `lexis_real_briefs/experiment/normalized_preview/` — mechanically normalized
  text for candidate review

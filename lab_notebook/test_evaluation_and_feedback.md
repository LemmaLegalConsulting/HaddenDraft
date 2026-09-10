# Evaluation of Argument Gym Benchmarks: What They Capture (Meaningful vs. Noise)

This document synthesizes empirical findings from running all 15 Cleveland real-brief snapshots (`cle_real_briefs`), prior live-model experiments (`gpt-5.5`), and the 18-scenario synthetic minimal-pair reasoning suite. It evaluates what the Argument Gym test suite captures that is legally and practically meaningful, what constitutes noise or false alarms, and where architectural limitations currently distort benchmark results.

---

## 1. Executive Summary

Argument Gym employs a two-tier evaluation architecture:
1. **Synthetic Minimal-Pair Probes (`minimal-pairs.yaml`)**: Closed-world, controlled scenarios testing specific legal reasoning primitives (hierarchy of binding vs. persuasive authority, local ordinance coverage, amendment effective dates, entailment vs. keyword matching, and factual certainty).
2. **Production Pipeline on Real Briefs (`scripts/benchmark_real_briefs.py`)**: End-to-end evaluation of complex, un-curated Word documents (`.docx`) through multi-stage ingestion, deterministic document/court/pleading checks, legal rule/element audits, argument mapping, and adversarial challenges (opponent, judge, coach).

Across our execution of all 15 real briefs and audit of historical traces, the testing framework demonstrates **high diagnostic value for drafting integrity, vocabulary discipline, and live adversarial vulnerability analysis**, but suffers from **mechanical noise in syntactic linters, false reassurance in offline citation-counting fallbacks, topical keyword collision in rule audits, and a severe 80-unit context truncation ceiling in production model calls**.

---

## 2. What the Tests Capture That Is Truly Meaningful

### A. Genuine Drafting Leftovers and Unresolved Placeholders (`pleading_form`)
The single most valuable deterministic signal is the detection of unfinished attorney drafting markers:
- **Caught Critical Leftovers**:
  - In *Wheeler against Pine Creek* (all 3 snapshots): Flags `[NAME OF ORDINANCE]`, `[NAME]`, `[Add this section]`, and `[Add facts from affidavits about this]`.
  - In *Residents of Perry & Fairgrounds* (May 20 snapshot): Flags `[name the five claims]`, `[ADD]`, and `[EXAMPLES]`.
- **Accurately Tracks Drafting Progression**:
  - Perry May 20 (`[ADD]`, `[EXAMPLES]`, `[name the five claims]`) -> May 29 (resolved `[ADD]`) -> May 30 (all placeholders resolved; errors dropped from 3 -> 2 -> 0).
- **Recent False-Positive Tightening Works**:
  - The repository's recent refinement successfully exempts standard attorney signature blocks (e.g., `____________________ /s/ Attorney Name`) while continuing to flag body blanks and unfinished evidentiary placeholders.

### B. Legal-Specific Confused Words vs. Blind Spellcheck (`confused_words`)
Standard dictionary spellcheckers fail in legal software because they flag essential terminology (*certiorari*, *mandamus*, *estoppel*, party surnames). Argument Gym uses a curated legal-confused-words catalog (`content/drafting-rules/checks/legal-language.yaml`) that catches high-consequence typos that spellcheckers miss:
- **Hooper Opening Brief**: Caught `"statue"` used instead of `"statute"` ("a statue is a sculpture") and `"statues"` instead of `"statutes"`.
- **Vourliotis Appellate Briefs**: Caught British legal spelling `"judgement"` instead of American legal standard `"judgment"`.
- **Thomas MSJ**: Alerted on co-occurrence of `"complaint"` and `"compliant"`.
- **Wheeler MSJ**: Alerted on `"counsel"` vs. `"council"`.
- **Doubled Words**: Caught inadvertent stutters that undermine credibility, such as `"Auglaize Auglaize"` (Perry) and `"that that"` (Hooper).

### C. Measurability Integrity in Court Formatting (`court_formatting`)
The benchmark adheres strictly to the rule: *report an unmeasured property as unmeasured, never as a pass*.
- In *Moore*, the brief uses 11pt font throughout and 0.90" margins; the benchmark flags these against the 12pt and 1.00" standard profile.
- Where Word XML omits explicit run-level font size metadata (e.g. *Wheeler*, *Gentile*, *Thomas*), it reports `outcome: unmeasured` rather than asserting compliance.

### D. Multi-Agent Adversarial Decomposition (In Live Runs)
In live model runs (`gpt-5.5`), separating the Opponent, Judge, and Coach stages into independent model calls prevents the model from generating toothless attacks:
- In *Moore*, the opponent immediately identified the core legal weakness of the waiver defense: *Rule 56 requires proving acceptance of future rent after service of the R.C. 1923.04 notice; the brief asserted payment was made but failed to establish whether the payment applied to future occupancy or pre-existing arrearages.*
- In *Perry*, the model shifted its critique across revisions: on May 20 it attacked the threshold failure to define the five claims; on May 30 it attacked the statutory reach of R.C. 4781.37 and the legality of base water fees under manufactured home park law.

### E. Synthetic Minimal-Pair Isolation (`minimal-pairs.yaml`)
The synthetic suite isolates whether the model's reasoning is causally linked to legal authority or seduced by surface semantics:
- **Binding Authority vs. Semantic Similarity**: In `appellate-district`, Case B is 99% semantically identical to the facts, but Case A is from the governing 8th District. The harness verifies that the model does not prefer high semantic similarity over binding jurisdictional hierarchy.
- **Entailment vs. Keyword Matching**: Proves the model distinguishes between a case holding that directly entails dismissal versus a case that shares identical factual keywords but reaches the opposite legal conclusion.

---

## 3. What the Tests Capture That Is NOT Meaningful or Misleading

### A. Heuristic Lowercase Sentence Starts (High Mechanical Noise)
The `grammar` check flags lowercase sentence beginnings. In real legal briefs, this produces pervasive false positives because legal typography frequently uses lowercase lead-ins:
- **Citation fragments**: `"v Williams, 3 Ohio App.3d 288..."`
- **Statutory references**: `"of its violations of R.C. ..."`
- **Corporate/Municipal names**: `"of Ohio, Inc."`, `"of City of Raleigh, 595 F. ..."`, `"of Private Detective Agencies, Inc."`
- **Service/Certificate clauses**: `"mail, postage prepaid and by electronic ..."`
- **Impact**: In Hooper, Perry, and Pine Creek, 50% to 80% of all grammar findings are informational notices from this single heuristic. This noise trains users to dismiss the entire check report.

### B. Punctuation Layout False Positives on Court Captions
Ohio legal pleadings traditionally format captions with right-hand closing parentheses separating the parties from the case number:
```text
ANGELA HOOPER,               )
                             )   CASE NO. 2024-CV-...
        Plaintiff,           )
                             )   JUDGE ...
v.                           )
                             )
PINE CREEK APARTMENTS,       )
```
The punctuation linter treats this as `"6 closing parenthesis(s) with nothing opened"`. Every brief with a standard caption receives a `review` warning for punctuation errors that are actually orthodox caption styling.

### C. False Negatives in Requested Relief Detection (`pleading_form`)
In both the Hooper and Vourliotis opening appellate briefs, the check reported:
`[REVIEW] No passage asks the court for anything. A filing that does not state the relief it seeks leaves the court to infer it.`
Both briefs contain clear prayers for reversal and remand in their concluding sections. The regex (`_RELIEF`) requires specific opening words like `"wherefore"`, `"respectfully requests"`, or `"prays for"`. Appellate conclusion headings like *"For the foregoing reasons, Appellant requests that the judgment of the trial court be reversed"* failed the pattern match when split across structural units.

### D. Topical Keyword Collision in Rule Audits
`LegalRuleProfile` matches claims based on topical vocabulary rather than legal claim assertions:
- In *Wheeler*, discussing *"lead abatement work"* in the factual background triggered the full statutory rent-abatement damages audit under R.C. 5321.07.
- Mentioning a deposit in a factual narrative triggers the entire security-deposit penalty audit.
- When an audit triggers on an incidental mention, every unmentioned statutory element is flagged as `unsupported` or `nothing_supplied`, generating phantom legal defects.

### E. The Offline Fallback: Citation-Counting as a False Proxy
In offline mode (`scripts/benchmark_real_briefs.py` without `--live`), the fallback opponent relies on a simple rule:
`weakestLink = "" if citations else "This passage argues without citing authority."`
This produces two severe failure modes:
1. **False Reassurance on Heavily-Cited Bad Arguments**:
   - In *Perry*, all 12 top-level argument units had statutory or case citations attached.
   - Result: Fallback generated **0 challenges** and reported `"no challenges raised"`! An attorney looking at the offline benchmark would believe Perry is flawless, whereas the live model immediately found major substantive vulnerabilities.
2. **False Penalties on Uncited Factual/Procedural Sentences**:
   - In *Thomas* and *Moore*, introductory or procedural sentences classified as `argument` units lacked citations.
   - Result: Fallback generated 7 challenges (`"The weakest step here is exposed: This passage argues without citing authority"`), penalizing the brief for sentences that never required a citation.

### F. Brittle Exact-Match Grading in Synthetic Probes
In the synthetic minimal-pair benchmark (`run_gym_benchmark`), 5 of 18 scenarios were graded as `fail` despite demonstrating correct legal analysis:
- **String vs. Null**: In `wrong-precedential-level`, the model returned `"none"` instead of JSON `null` for governing authority.
- **Context leakage**: In `municipality/city-b`, the model correctly held pay-to-stay was unavailable, but populated `ordinance: "city-b"` (the jurisdiction) instead of `null`.
- **Evidence Span Precision**: In `appellate-district/eleventh`, the model correctly identified Case B as binding and Case A as persuasive, but omitted the exact single character-for-character quotation span expected by the test harness.
Strict grading is appropriate for regression tests, but treating these as substantive legal reasoning failures misrepresents model capability.

---

## 4. Systemic Architectural Bottlenecks

### 1. The 80-Unit Prompt Truncation Ceiling
In `apps.argument_gym.pipeline._unit_payload()`, the text sent to the Argument Map, Opponent, and Judge stages is capped at **80 units and 900 characters per unit**:
- *L. Moore*: 106 units (partially evaluated).
- *Wheeler / Pine Creek*: 191 units (>50% truncated).
- *Residents of Perry*: 412 - 440 units (>80% truncated).
- *A. Hooper*: 694 units (>88% truncated).
**Critical Consequence**: In long briefs, the model only reads the jurisdictional statement, caption, and factual background. It never sees the substantive argument sections in Part II, III, or IV! Any benchmark score on long briefs is evaluating the front-matter, not the brief's legal core.

### 2. The Missing Record Problem
All real-brief runs to date have run without attached affidavits, leases, or exhibit PDFs.
- In *Moore*, the model repeatedly asked for proof that payments were applied to future rent, but the payment receipts and PPHA lease were in unattached exhibits.
- Evaluating a brief's evidentiary adequacy without its record guarantees that factual support will always report `nothing_supplied`.

---

## 5. Summary Findings Table

| Test / Check Area | What It Captures That Is Meaningful | What It Captures That Is Noisy / Misleading | Actionable Engineering Fix |
| --- | --- | --- | --- |
| **Pleading Form (Placeholders)** | Genuine drafting blanks (`[ADD]`, `[NAME]`, `[EXAMPLES]`); tracks revision cleanup across drafts | Minor: unquoted role markers | Retain current rules; add regex for bracketed internal notes |
| **Pleading Form (Relief)** | Catches briefs that truly omit a prayer for relief | Fails to recognize standard appellate prayer phrasing at document end | Broaden `_RELIEF` regex to include reversal/remand and prayer headings |
| **Confused Words / Vocabulary** | High-value typos: *statue* vs *statute*, *judgement* vs *judgment*, *counsel* vs *council* | None observed; precision is very high | Expand curated legal language catalog with real advocate errors |
| **Grammar (Punctuation)** | Unclosed brackets and braces in text | Caption parenthesis columns (`PLAINTIFF, )`) counted as unmatched | Add layout-aware caption parser to exempt caption blocks from punctuation audits |
| **Grammar (Sentence Starts)** | Genuine lowercase fragments | Legal citation signals, party names (`of Ohio, Inc.`), and service clauses | Add legal citation & entity token exceptions to lowercase detection |
| **Court Formatting** | Font size violations (11pt vs 12pt); margin deviations; standard of review omission | Unverified starter profiles applied to courts with different local rules | Require verified `CourtProfile` before reporting errors; maintain `unmeasured` |
| **Rule Element Audit** | Verifies statutory elements for asserted claims | Topical keywords (*lead abatement*, *deposit*) trigger unasserted claim audits | Require pleading-level claim assertion before triggering element checklist |
| **Offline Pipeline Fallback** | Deterministic smoke testing of data flow | Pure citation presence used as proxy for argument soundness (Perry 0 vs Thomas 7) | Differentiate factual paragraphs from legal propositions in fallback argument mapper |
| **Live Opponent / Judge** | Deep substantive attacks on legal theory, notice standards, and proof gaps | Only evaluates the first 80 units of the brief due to prompt truncation ceiling | Implement section-based chunking or two-pass argument map over entire brief |
| **Synthetic Minimal Pairs** | Controlled isolation of authority hierarchy and entailment reasoning | Brittle formatting failures (string `"none"` vs `null`, evidence array length) | Clarify prompt output schema and support flexible schema normalization |

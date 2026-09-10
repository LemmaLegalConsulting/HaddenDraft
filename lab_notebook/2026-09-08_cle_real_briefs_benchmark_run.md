# Benchmark Run: All CLE Real Briefs (2026-09-08)

## 1. Run Metadata and Reproducibility

- **Execution Date**: 2026-09-08
- **Command**: `/home/quinten/agentic_housing_drafting/.venv/bin/python scripts/benchmark_real_briefs.py --output-dir cle_real_briefs/benchmark_outputs/2026-09-08-all-briefs-offline`
- **Base Git Commit**: `ddb7ff7d5bca890882769a4413d4c2e7c58234ed`
- **Git Status**: `clean`
- **Corpus Path**: `cle_real_briefs/revision_snapshots/word_versions`
- **Input Document Count**: 15 files (nine revision snapshots across three multi-version families, plus six source-copy briefs)
- **Execution Pipeline**: Deterministic offline (`AI_DRAFTING_ENABLED=False`, stub retrieval, isolated SQLite catalog)
- **Output Location**: `cle_real_briefs/benchmark_outputs/2026-09-08-all-briefs-offline/`

## 2. Complete Corpus Results Table

| Family / Subdirectory | Snapshot File | Characters | Units | Pleading Form | Grammar | Confused Words | Court Format | Total Findings | Outcomes (F/R/P/U) | Challenges | Fallback Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `appellate_briefs/A_Hooper` | `2026-03-10_source_copy_no_embedded_track_changes` | 71,450 | 694 | 1 | 8 | 2 | 0 | **11** | 0/6/5/0 | 0 | no challenges raised |
| `appellate_briefs/A_Hooper` | `2026-04-30_source_copy_no_embedded_track_changes` | 23,842 | 290 | 0 | 5 | 0 | 1 | **6** | 0/1/5/0 | 0 | no challenges raised |
| `appellate_briefs/M_Vourliotis` | `2024-10-01_source_copy_no_embedded_track_changes` | 45,330 | 463 | 1 | 3 | 1 | 0 | **5** | 0/2/3/0 | 0 | no challenges raised |
| `appellate_briefs/M_Vourliotis` | `2024-11-22_source_copy_no_embedded_track_changes` | 19,432 | 210 | 0 | 0 | 1 | 2 | **3** | 0/3/0/0 | 2 | exposed on missing element |
| `summary_judgment/L_Moore` | `2017-09-14_after_first_revision_cluster` | 9,205 | 106 | 0 | 2 | 0 | 5 | **7** | 0/6/1/0 | 3 | exposed on missing element |
| `summary_judgment/L_Moore` | `2017-09-19_after_follow_up_revision_cluster` | 9,131 | 106 | 0 | 2 | 0 | 5 | **7** | 0/6/1/0 | 3 | exposed on missing element |
| `summary_judgment/L_Moore` | `2017-09-22_current_accepted` | 9,071 | 106 | 0 | 2 | 0 | 5 | **7** | 0/6/1/0 | 3 | exposed on missing element |
| `summary_judgment/L_Wheeler/against_Gentile` | `current_source_copy_no_embedded_text_revisions` | 33,814 | 240 | 0 | 1 | 1 | 2 | **4** | 0/2/1/1 | 0 | no challenges raised |
| `summary_judgment/L_Wheeler/against_Pine_Creek` | `2025-05-30_after_initial_revision_cluster` | 26,882 | 191 | 4 | 4 | 0 | 2 | **10** | 4/2/3/1 | 0 | no challenges raised |
| `summary_judgment/L_Wheeler/against_Pine_Creek` | `2025-06-02_after_follow_up_revision` | 26,883 | 191 | 4 | 4 | 0 | 2 | **10** | 4/2/3/1 | 0 | no challenges raised |
| `summary_judgment/L_Wheeler/against_Pine_Creek` | `2025-06-03_current_accepted` | 26,885 | 191 | 4 | 4 | 0 | 2 | **10** | 4/2/3/1 | 0 | no challenges raised |
| `summary_judgment/Residents_Perry_Fairgrounds` | `2024-05-20_before_late_revision_cluster` | 56,985 | 412 | 3 | 8 | 0 | 0 | **11** | 3/3/5/0 | 0 | no challenges raised |
| `summary_judgment/Residents_Perry_Fairgrounds` | `2024-05-29_after_review_revision_cluster` | 58,742 | 413 | 2 | 7 | 0 | 0 | **9** | 2/2/5/0 | 0 | no challenges raised |
| `summary_judgment/Residents_Perry_Fairgrounds` | `2024-05-30_current_accepted` | 58,270 | 440 | 0 | 6 | 0 | 0 | **6** | 0/1/5/0 | 0 | no challenges raised |
| `summary_judgment/T_Thomas` | `current_source_copy_no_embedded_text_revisions` | 20,624 | 161 | 0 | 4 | 1 | 0 | **5** | 0/1/4/0 | 7 | exposed on missing element |

*Outcomes Legend: `Fail` (unresolved placeholders, formatting defects); `Review` (warnings, punctuation, vocab alerts); `Pass` (informational passes); `Unmeasured` (unmeasured metrics such as unread font sizes).*

## 3. Family Revision Chronologies

### A. Residents of Perry & Fairgrounds (3 snapshots: 2024-05-20 -> 2024-05-29 -> 2024-05-30)
This family represents a summary-judgment motion challenging manufactured home park conditions and fees under R.C. 4781.
- **Trajectory**: Total findings drop monotonically: **11 -> 9 -> 6**.
- **Pleading Form**: Dropped **3 -> 2 -> 0** as attorneys resolved explicit drafting placeholders:
  - 2024-05-20: Contained `[name the five claims]`, `[ADD]`, and `[EXAMPLES]` (`fail`).
  - 2024-05-29: Resolved `[ADD]`, leaving `[name the five claims]` and `[EXAMPLES]`.
  - 2024-05-30: All placeholders resolved.
- **Grammar/Style**: Doubled word `Auglaize Auglaize` present in May 20 and May 29 was fixed in May 30. Bracket error resolved. 6 closing parentheses persist due to caption format.
- **Challenges**: 0 in offline fallback across all three because every argument unit contained statutory/case citations, triggering none of the citation-absence fallback rules.

### B. Wheeler against Pine Creek (3 snapshots: 2025-05-30 -> 2025-06-02 -> 2025-06-03)
This family represents a tenant summary-judgment motion regarding lead hazard compliance and rent escrow under R.C. 5321.
- **Trajectory**: Flat findings count across all three snapshots: **10 -> 10 -> 10**.
- **Pleading Form**: 4 persistent placeholder errors: `[NAME OF ORDINANCE]`, `[NAME]`, `[Add this section]`, and `[Add facts from affidavits about this]`. The embedded revisions were minor wording adjustments that did not resolve these placeholders.
- **Court Formatting**: Margin warning (bottom margin 0.80" vs. 1.00" generic profile) and unmeasured type size.
- **Grammar**: Closing brackets notice (2 closing brackets with nothing opened) and lowercase sentence start notices.
- **Challenges**: 0 in offline fallback.

### C. L. Moore (3 snapshots: 2017-09-14 -> 2017-09-19 -> 2017-09-22)
This family represents an eviction summary-judgment motion raising a waiver defense based on Section 8 / housing authority rent acceptance.
- **Trajectory**: Flat findings count: **7 -> 7 -> 7**.
- **Pleading Form**: 0 placeholder errors (clean drafting text).
- **Court Formatting**: 5 review warnings: 11pt font (requires 12pt under generic profile) and 0.90" margins on all four sides (requires 1.00").
- **Challenges**: 3 fallback challenges across all three snapshots (`exposed on missing element`):
  - `missing_element`: Argument unit without cited authority.
  - `legal_authority`: Proposition advanced without cited authority.
  - `remedy_scope`: Relief requested reaches further than preceding argument supports.

### D. Single-Snapshot Source Copies
- **T. Thomas (Summary Judgment)**: 5 findings (confused words alert on `complaint` vs `compliant`, 3 unmatched caption parentheses, 3 lowercase sentence notices). 7 fallback challenges (`exposed on missing element`) because introductory/procedural units lacked attached legal citations.
- **Wheeler against Gentile (Summary Judgment)**: 4 findings (confused words alert on `counsel` vs `council`, bottom margin 0.80", 2 unmatched parentheses, unmeasured font size). 0 fallback challenges.
- **Hooper (Appellate Briefs: Opening 2026-03-10 vs. Reply 2026-04-30)**:
  - Opening: 11 findings. Caught real typos: `statue` instead of `statute` and `statues` instead of `statutes`; doubled word `that that`; unclosed opening brackets; relief notice.
  - Reply: 6 findings. Standard of review missing notice (generic appellate profile requires it); lowercase sentence heuristics on citations.
- **Vourliotis (Appellate Briefs: Opening 2024-10-01 vs. Reply 2024-11-22)**:
  - Opening: 5 findings. Caught British spelling `judgement` instead of `judgment`; relief notice.
  - Reply: 3 findings. Caught `judgement`; 11pt font; standard of review missing.

## 4. In-Depth Per-Document Findings Log

### `appellate_briefs/A_Hooper` / `2026-03-10_source_copy_no_embedded_track_changes`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/appellate_briefs/A_Hooper/2026-03-10_source_copy_no_embedded_track_changes.docx`
- **SHA-256**: `689170c1487e034cb02e2f93ee331315bc109893e86dc6ad8a1641493dd6e4ac`
- **Metrics**: 71,450 chars, 694 units, 323 paragraphs, N/A pages
- **Outcomes**: {'review': 6, 'pass': 5}
- **Headline Verdict**: `no challenges raised`

#### Check: `pleading_form` (1 findings)
- `[REVIEW]` No passage asks the court for anything. A filing that does not state the relief it seeks leaves the court to infer it.

#### Check: `grammar` (8 findings)
- `[REVIEW]` 1 closing brace(s) with nothing opened.
- `[REVIEW]` 2 unclosed opening bracket(s).
- `[REVIEW]` "that" appears twice in a row.
- `[PASS]` A sentence begins with "b.There is no other direct conflict or “".
- `[PASS]` A sentence begins with "terminated Appellant Angela Hooper’s ten".
- `[PASS]` A sentence begins with "of Private Detectives v.".
- `[PASS]` A sentence begins with "of Am., Inc.".
- `[PASS]` A sentence begins with "of its violations of R.C.".

#### Check: `confused_words` (2 findings)
- `[REVIEW]` "statue" is almost always "statute" in a filing. A statue is a sculpture.
- `[REVIEW]` "statues" is almost always "statutes" in a filing.

---

### `appellate_briefs/A_Hooper` / `2026-04-30_source_copy_no_embedded_track_changes`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/appellate_briefs/A_Hooper/2026-04-30_source_copy_no_embedded_track_changes.docx`
- **SHA-256**: `9de20ca4267bcf45f6e66afbb394145b1957dfb21d09a67208f1f1b3d89e25ca`
- **Metrics**: 23,842 chars, 290 units, 138 paragraphs, N/A pages
- **Outcomes**: {'pass': 5, 'review': 1}
- **Headline Verdict**: `no challenges raised`

#### Check: `grammar` (5 findings)
- `[PASS]` A sentence begins with "v Williams, 3 Ohio App.3d 288 (2nd Dist.".
- `[PASS]` A sentence begins with "of Ohio, Inc.".
- `[PASS]` A sentence begins with "v Williams, 3 Ohio App.3d 288, 294-299 (".
- `[PASS]` A sentence begins with "of Private Detective Agencies, Inc.".
- `[PASS]` A sentence begins with "a landlord may not retaliate against a t".

#### Check: `court_formatting` (1 findings)
- `[REVIEW]` Standard of review was not found in this document. Ohio court of appeals (generic starter profile) requires it for a reply_brief per an unverified starter profile, not this court's own rules.

---

### `appellate_briefs/M_Vourliotis` / `2024-10-01_source_copy_no_embedded_track_changes`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/appellate_briefs/M_Vourliotis/2024-10-01_source_copy_no_embedded_track_changes.docx`
- **SHA-256**: `ce8affa48aceb6529a7f6536b6e3dbfbe18dd5d2e27d1d4c44af4350811faffb`
- **Metrics**: 45,330 chars, 463 units, 245 paragraphs, N/A pages
- **Outcomes**: {'review': 2, 'pass': 3}
- **Headline Verdict**: `no challenges raised`

#### Check: `pleading_form` (1 findings)
- `[REVIEW]` No passage asks the court for anything. A filing that does not state the relief it seeks leaves the court to infer it.

#### Check: `grammar` (3 findings)
- `[PASS]` A sentence begins with "of Liquor Control v.".
- `[PASS]` A sentence begins with "certified or express mail or by a commer".
- `[PASS]` A sentence begins with "mail or commercial carrier, the service ".

#### Check: `confused_words` (1 findings)
- `[REVIEW]` "judgement" is almost always "judgment" in a filing. American legal usage is "judgment", with no e after the g.

---

### `appellate_briefs/M_Vourliotis` / `2024-11-22_source_copy_no_embedded_track_changes`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/appellate_briefs/M_Vourliotis/2024-11-22_source_copy_no_embedded_track_changes.docx`
- **SHA-256**: `717bacb77946d9eadaf152b723abaf95f78d9d7f583d0f509be3353d3d708c9e`
- **Metrics**: 19,432 chars, 210 units, 123 paragraphs, N/A pages
- **Outcomes**: {'review': 3}
- **Headline Verdict**: `exposed on missing element`

#### Check: `confused_words` (1 findings)
- `[REVIEW]` "judgement" is almost always "judgment" in a filing. American legal usage is "judgment", with no e after the g.

#### Check: `court_formatting` (2 findings)
- `[REVIEW]` Standard of review was not found in this document. Ohio court of appeals (generic starter profile) requires it for a reply_brief per an unverified starter profile, not this court's own rules.
- `[REVIEW]` Text is set in 11 point. Ohio court of appeals (generic starter profile) requires at least 12 point per an unverified starter profile, not this court's own rules.

#### Challenges Generated (2):
- `[missing_element/high]` The weakest step here is exposed: This passage argues without citing authority.
  - *Impact*: An argument fails at its weakest step, not its strongest.
- `[legal_authority/medium]` This proposition is advanced without citing authority, so the court has nothing to check it against.
  - *Impact*: An uncited proposition is the cheapest thing for an opponent to contest.

---

### `summary_judgment/L_Moore` / `2017-09-14_after_first_revision_cluster`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/summary_judgment/L_Moore/2017-09-14_after_first_revision_cluster.docx`
- **SHA-256**: `3dc8ed60e85b15b5831aaaba3345dbe0d8837013ef5731997562f004daee123d`
- **Metrics**: 9,205 chars, 106 units, 66 paragraphs, N/A pages
- **Outcomes**: {'review': 6, 'pass': 1}
- **Headline Verdict**: `exposed on missing element`

#### Check: `grammar` (2 findings)
- `[REVIEW]` 1 unclosed opening parenthesis(s).
- `[PASS]` A sentence begins with "mail, postage prepaid and by electronic ".

#### Check: `court_formatting` (5 findings)
- `[REVIEW]` Text is set in 11 point. Ohio trial court (generic starter profile) requires at least 12 point per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The bottom margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The left margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The right margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The top margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.

#### Challenges Generated (3):
- `[missing_element/high]` The weakest step here is exposed: This passage argues without citing authority.
  - *Impact*: An argument fails at its weakest step, not its strongest.
- `[legal_authority/medium]` This proposition is advanced without citing authority, so the court has nothing to check it against.
  - *Impact*: An uncited proposition is the cheapest thing for an opponent to contest.
- `[remedy_scope/low]` The relief requested reaches further than the argument that precedes it supports.
  - *Impact*: A court that agrees on the merits can still refuse the remedy as framed.

---

### `summary_judgment/L_Moore` / `2017-09-19_after_follow_up_revision_cluster`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/summary_judgment/L_Moore/2017-09-19_after_follow_up_revision_cluster.docx`
- **SHA-256**: `c859651736668385d45c89c3807ff80d623ee13aa5566c137aea736a7b622d7b`
- **Metrics**: 9,131 chars, 106 units, 66 paragraphs, N/A pages
- **Outcomes**: {'review': 6, 'pass': 1}
- **Headline Verdict**: `exposed on missing element`

#### Check: `grammar` (2 findings)
- `[REVIEW]` 1 unclosed opening parenthesis(s).
- `[PASS]` A sentence begins with "mail, postage prepaid and by electronic ".

#### Check: `court_formatting` (5 findings)
- `[REVIEW]` Text is set in 11 point. Ohio trial court (generic starter profile) requires at least 12 point per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The bottom margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The left margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The right margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The top margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.

#### Challenges Generated (3):
- `[missing_element/high]` The weakest step here is exposed: This passage argues without citing authority.
  - *Impact*: An argument fails at its weakest step, not its strongest.
- `[legal_authority/medium]` This proposition is advanced without citing authority, so the court has nothing to check it against.
  - *Impact*: An uncited proposition is the cheapest thing for an opponent to contest.
- `[remedy_scope/low]` The relief requested reaches further than the argument that precedes it supports.
  - *Impact*: A court that agrees on the merits can still refuse the remedy as framed.

---

### `summary_judgment/L_Moore` / `2017-09-22_current_accepted`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/summary_judgment/L_Moore/2017-09-22_current_accepted.docx`
- **SHA-256**: `b60e1521fb8052b1c3dec843473230e177eb63a9a2cf0eb4424465e8dfc19a1b`
- **Metrics**: 9,071 chars, 106 units, 66 paragraphs, N/A pages
- **Outcomes**: {'review': 6, 'pass': 1}
- **Headline Verdict**: `exposed on missing element`

#### Check: `grammar` (2 findings)
- `[REVIEW]` 1 unclosed opening parenthesis(s).
- `[PASS]` A sentence begins with "mail, postage prepaid and by electronic ".

#### Check: `court_formatting` (5 findings)
- `[REVIEW]` Text is set in 11 point. Ohio trial court (generic starter profile) requires at least 12 point per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The bottom margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The left margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The right margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[REVIEW]` The top margin is 0.90 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.

#### Challenges Generated (3):
- `[missing_element/high]` The weakest step here is exposed: This passage argues without citing authority.
  - *Impact*: An argument fails at its weakest step, not its strongest.
- `[legal_authority/medium]` This proposition is advanced without citing authority, so the court has nothing to check it against.
  - *Impact*: An uncited proposition is the cheapest thing for an opponent to contest.
- `[remedy_scope/low]` The relief requested reaches further than the argument that precedes it supports.
  - *Impact*: A court that agrees on the merits can still refuse the remedy as framed.

---

### `summary_judgment/L_Wheeler/against_Gentile` / `current_source_copy_no_embedded_text_revisions`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/summary_judgment/L_Wheeler/against_Gentile/current_source_copy_no_embedded_text_revisions.docx`
- **SHA-256**: `62ce8816758f0021da46890682b26e3569e42d810fae916790950c309e8c784b`
- **Metrics**: 33,814 chars, 240 units, 171 paragraphs, N/A pages
- **Outcomes**: {'review': 2, 'pass': 1, 'unmeasured': 1}
- **Headline Verdict**: `no challenges raised`

#### Check: `grammar` (1 findings)
- `[REVIEW]` 2 unclosed opening parenthesis(s).

#### Check: `confused_words` (1 findings)
- `[PASS]` Both "counsel" and "council" appear. Check that each is the word meant. "counsel" is the lawyer; "council" is the body that meets.

#### Check: `court_formatting` (2 findings)
- `[REVIEW]` The bottom margin is 0.80 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[UNMEASURED]` Type size could not be read from this file, so the 12-point minimum was not checked.

---

### `summary_judgment/L_Wheeler/against_Pine_Creek` / `2025-05-30_after_initial_revision_cluster`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/summary_judgment/L_Wheeler/against_Pine_Creek/2025-05-30_after_initial_revision_cluster.docx`
- **SHA-256**: `61aaa04fb2da7ed0b6f85647e4c91526768666b0860d2d152f33cd6e3a795686`
- **Metrics**: 26,882 chars, 191 units, 142 paragraphs, N/A pages
- **Outcomes**: {'fail': 4, 'review': 2, 'pass': 3, 'unmeasured': 1}
- **Headline Verdict**: `no challenges raised`

#### Check: `pleading_form` (4 findings)
- `[FAIL]` A placeholder is still in the text: [NAME OF ORDINANCE]
- `[FAIL]` A placeholder is still in the text: [NAME]
- `[FAIL]` A placeholder is still in the text: [Add this section]
- `[FAIL]` A placeholder is still in the text: [Add facts from affidavits about this]

#### Check: `grammar` (4 findings)
- `[REVIEW]` 2 closing bracket(s) with nothing opened.
- `[PASS]` A sentence begins with "of Public Health to address the lead haz".
- `[PASS]` A sentence begins with "received a Lead Clearance Examination Re".
- `[PASS]` A sentence begins with "above and Affidavits of Irizarry and All".

#### Check: `court_formatting` (2 findings)
- `[REVIEW]` The bottom margin is 0.80 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[UNMEASURED]` Type size could not be read from this file, so the 12-point minimum was not checked.

---

### `summary_judgment/L_Wheeler/against_Pine_Creek` / `2025-06-02_after_follow_up_revision`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/summary_judgment/L_Wheeler/against_Pine_Creek/2025-06-02_after_follow_up_revision.docx`
- **SHA-256**: `328a5ce3377a283acb5869708f4d9e47aabab903c89ef870e4e4fb5dc1732983`
- **Metrics**: 26,883 chars, 191 units, 142 paragraphs, N/A pages
- **Outcomes**: {'fail': 4, 'review': 2, 'pass': 3, 'unmeasured': 1}
- **Headline Verdict**: `no challenges raised`

#### Check: `pleading_form` (4 findings)
- `[FAIL]` A placeholder is still in the text: [NAME OF ORDINANCE]
- `[FAIL]` A placeholder is still in the text: [NAME]
- `[FAIL]` A placeholder is still in the text: [Add this section]
- `[FAIL]` A placeholder is still in the text: [Add facts from affidavits about this]

#### Check: `grammar` (4 findings)
- `[REVIEW]` 2 closing bracket(s) with nothing opened.
- `[PASS]` A sentence begins with "of Public Health to address the lead haz".
- `[PASS]` A sentence begins with "received a Lead Clearance Examination Re".
- `[PASS]` A sentence begins with "above and Affidavits of Irizarry and All".

#### Check: `court_formatting` (2 findings)
- `[REVIEW]` The bottom margin is 0.80 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[UNMEASURED]` Type size could not be read from this file, so the 12-point minimum was not checked.

---

### `summary_judgment/L_Wheeler/against_Pine_Creek` / `2025-06-03_current_accepted`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/summary_judgment/L_Wheeler/against_Pine_Creek/2025-06-03_current_accepted.docx`
- **SHA-256**: `a3fd10766ba8b36efd778ec87896f491e9b363a68d738215cd3bf3777c75f74c`
- **Metrics**: 26,885 chars, 191 units, 142 paragraphs, N/A pages
- **Outcomes**: {'fail': 4, 'review': 2, 'pass': 3, 'unmeasured': 1}
- **Headline Verdict**: `no challenges raised`

#### Check: `pleading_form` (4 findings)
- `[FAIL]` A placeholder is still in the text: [NAME OF ORDINANCE]
- `[FAIL]` A placeholder is still in the text: [NAME]
- `[FAIL]` A placeholder is still in the text: [Add this section]
- `[FAIL]` A placeholder is still in the text: [Add facts from affidavits about this]

#### Check: `grammar` (4 findings)
- `[REVIEW]` 2 closing bracket(s) with nothing opened.
- `[PASS]` A sentence begins with "of Public Health to address the lead haz".
- `[PASS]` A sentence begins with "received a Lead Clearance Examination Re".
- `[PASS]` A sentence begins with "above and Affidavits of Irizarry and All".

#### Check: `court_formatting` (2 findings)
- `[REVIEW]` The bottom margin is 0.80 inches. Ohio trial court (generic starter profile) requires 1.00 inches per an unverified starter profile, not this court's own rules.
- `[UNMEASURED]` Type size could not be read from this file, so the 12-point minimum was not checked.

---

### `summary_judgment/Residents_Perry_Fairgrounds` / `2024-05-20_before_late_revision_cluster`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/summary_judgment/Residents_Perry_Fairgrounds/2024-05-20_before_late_revision_cluster.docx`
- **SHA-256**: `9572873223ba56e6a9f8104e1c76e4a915790c2463cf2752f2144960cb066577`
- **Metrics**: 56,985 chars, 412 units, 154 paragraphs, N/A pages
- **Outcomes**: {'fail': 3, 'review': 3, 'pass': 5}
- **Headline Verdict**: `no challenges raised`

#### Check: `pleading_form` (3 findings)
- `[FAIL]` A placeholder is still in the text: [name the five claims]
- `[FAIL]` A placeholder is still in the text: [ADD]
- `[FAIL]` A placeholder is still in the text: [EXAMPLES]

#### Check: `grammar` (8 findings)
- `[REVIEW]` 1 unclosed opening bracket(s).
- `[REVIEW]` "Auglaize" appears twice in a row.
- `[REVIEW]` 6 closing parenthesis(s) with nothing opened.
- `[PASS]` A sentence begins with "told to use things like duct tape to mak".
- `[PASS]` A sentence begins with "of Commissioners, 2019-Ohio-3729, 144 N.".
- `[PASS]` A sentence begins with "park operator to fully disclose, in writ".
- `[PASS]` A sentence begins with "of Am., 159 Ohio App.3d 410, 2004-Ohio-7".
- `[PASS]` A sentence begins with "for damages for breach of contract, as t".

---

### `summary_judgment/Residents_Perry_Fairgrounds` / `2024-05-29_after_review_revision_cluster`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/summary_judgment/Residents_Perry_Fairgrounds/2024-05-29_after_review_revision_cluster.docx`
- **SHA-256**: `e3f05b08f473e3cf7f64106b4e622b779f7b43e7b02c0e75bba4c63871f46a27`
- **Metrics**: 58,742 chars, 413 units, 157 paragraphs, N/A pages
- **Outcomes**: {'fail': 2, 'review': 2, 'pass': 5}
- **Headline Verdict**: `no challenges raised`

#### Check: `pleading_form` (2 findings)
- `[FAIL]` A placeholder is still in the text: [name the five claims]
- `[FAIL]` A placeholder is still in the text: [EXAMPLES]

#### Check: `grammar` (7 findings)
- `[REVIEW]` "Auglaize" appears twice in a row.
- `[REVIEW]` 6 closing parenthesis(s) with nothing opened.
- `[PASS]` A sentence begins with "roperty manager Orndoff, does not speak ".
- `[PASS]` A sentence begins with "esidents unable to have work orders and ".
- `[PASS]` A sentence begins with "told to use things like duct tape to mak".
- `[PASS]` A sentence begins with "of Commissioners, 2019-Ohio-3729, 144 N.".
- `[PASS]` A sentence begins with "park operator to fully disclose, in writ".

---

### `summary_judgment/Residents_Perry_Fairgrounds` / `2024-05-30_current_accepted`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/summary_judgment/Residents_Perry_Fairgrounds/2024-05-30_current_accepted.docx`
- **SHA-256**: `75d4c17c0d89fc798b58f68b70c94676b08e1bee95db67e74cee7a769a4edf30`
- **Metrics**: 58,270 chars, 440 units, 161 paragraphs, N/A pages
- **Outcomes**: {'review': 1, 'pass': 5}
- **Headline Verdict**: `no challenges raised`

#### Check: `grammar` (6 findings)
- `[REVIEW]` 6 closing parenthesis(s) with nothing opened.
- `[PASS]` A sentence begins with "of Commissioners, 2019-Ohio-3729, 144 N.".
- `[PASS]` A sentence begins with "and did not disclose the additional fees".
- `[PASS]` A sentence begins with "of Am., 159 Ohio App.3d 410, 2004-Ohio-7".
- `[PASS]` A sentence begins with "for damages for breach of contract, as t".
- `[PASS]` A sentence begins with "is well drained and not subject to recur".

---

### `summary_judgment/T_Thomas` / `current_source_copy_no_embedded_text_revisions`
- **Path**: `cle_real_briefs/revision_snapshots/word_versions/summary_judgment/T_Thomas/current_source_copy_no_embedded_text_revisions.docx`
- **SHA-256**: `f74d99e21f621db3f30cc622de725ca50fc3765305188c63787c01ae62b98ed1`
- **Metrics**: 20,624 chars, 161 units, 71 paragraphs, N/A pages
- **Outcomes**: {'review': 1, 'pass': 4}
- **Headline Verdict**: `exposed on missing element`

#### Check: `grammar` (4 findings)
- `[REVIEW]` 3 closing parenthesis(s) with nothing opened.
- `[PASS]` A sentence begins with "of City of Raleigh, 595 F.".
- `[PASS]` A sentence begins with "of Racine, 713 N.W.2d 670 (Wis.".
- `[PASS]` A sentence begins with "of Camden, 2006 WL 2792784 (D.N.J.".

#### Check: `confused_words` (1 findings)
- `[PASS]` Both "complaint" and "compliant" appear. Check that each is the word meant. A complaint starts a case; compliant means it followed the rule.

#### Challenges Generated (7):
- `[missing_element/high]` The weakest step here is exposed: This passage argues without citing authority.
  - *Impact*: An argument fails at its weakest step, not its strongest.
- `[missing_element/high]` The weakest step here is exposed: This passage argues without citing authority.
  - *Impact*: An argument fails at its weakest step, not its strongest.
- `[missing_element/high]` The weakest step here is exposed: This passage argues without citing authority.
  - *Impact*: An argument fails at its weakest step, not its strongest.
- `[missing_element/high]` The weakest step here is exposed: This passage argues without citing authority.
  - *Impact*: An argument fails at its weakest step, not its strongest.
- `[legal_authority/medium]` This proposition is advanced without citing authority, so the court has nothing to check it against.
  - *Impact*: An uncited proposition is the cheapest thing for an opponent to contest.
- `[legal_authority/medium]` This proposition is advanced without citing authority, so the court has nothing to check it against.
  - *Impact*: An uncited proposition is the cheapest thing for an opponent to contest.
- `[legal_authority/medium]` This proposition is advanced without citing authority, so the court has nothing to check it against.
  - *Impact*: An uncited proposition is the cheapest thing for an opponent to contest.

---

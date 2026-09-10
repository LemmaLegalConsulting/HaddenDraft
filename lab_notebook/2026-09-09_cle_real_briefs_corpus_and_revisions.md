# Corpus Inventory & Revision Provenance: Cleveland Legal Aid Real Briefs

**Date**: 2026-09-09  
**Corpus Root**: `cle_real_briefs/` (git-ignored for client confidentiality)  
**Reconstructed Snapshots**: `cle_real_briefs/revision_snapshots/word_versions/`  
**Related Entries**:
- [`2026-09-08_cle_real_briefs_benchmark_run.md`](./2026-09-08_cle_real_briefs_benchmark_run.md)
- [`2026-09-08_check_suite_remediation.md`](./2026-09-08_check_suite_remediation.md)
- [`2026-09-08_revised_code_experiment.md`](./2026-09-08_revised_code_experiment.md)

---

## 1. Executive Summary

This entry documents the exact composition of the real Cleveland Legal Aid Society ("LASCO") brief collection, detailing the source files provided via SharePoint downloads and filed public court records, the number of distinct legal matters and brief instruments, and the revision counts (both embedded tracked changes and reconstructed logical snapshots).

- **Total Client Matters**: **7 matters** (4 summary judgment matters + 3 appellate matters).
- **Total Brief / Motion Instruments Drafted by Cleveland Legal Aid**:
  - **9 instruments with editable Word (.docx) source files**.
  - **2 instruments with filed PDF copies only** (*Rubalcava* opening and reply).
  - *(Plus 3 opposing counsel Appellee briefs gathered for contextual reference)*.
- **Total Reconstructed Word Benchmark Snapshots**: **15 DOCX files** across:
  - **3 multi-version revision families** (3 snapshots each = 9 snapshots).
  - **6 single-version source copies** (1 snapshot each = 6 snapshots).

---

## 2. Comprehensive Inventory Table

| Category | Client Matter / Directory | Instrument / Document Title | Provided Formats | Embedded Tracked Changes | Logical Snapshots | Snapshot Names / Labels |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **Summary Judgment** | `Residents_Perry_Fairgrounds` | Plaintiff's Motion for Partial Summary Judgment | Word (.docx) & Filed PDF | **2,261 tracked actions** (text & formatting; May 29–30, 2024); attorney comments (May 15 & 20) | **3** | `2024-05-20_before_late_revision_cluster`<br>`2024-05-29_after_review_revision_cluster`<br>`2024-05-30_current_accepted` |
| **Summary Judgment** | `L_Wheeler/against_Pine_Creek` | Plaintiff's Motion for Summary Judgment against Pine Creek | Word (.docx) | **7 tracked actions** (May 30–June 3, 2025); attorney review comments (May 5–22) | **3** | `2025-05-30_after_initial_revision_cluster`<br>`2025-06-02_after_follow_up_revision`<br>`2025-06-03_current_accepted` |
| **Summary Judgment** | `L_Wheeler/against_Gentile` | Plaintiff's Motion for Summary Judgment against Gentile | Word (.docx) & Filed PDF (3 parts) | **0 tracked actions** | **1** | `current_source_copy_no_embedded_text_revisions` |
| **Summary Judgment** | `L_Moore` | Defendant's Motion for Summary Judgment | Word (.docx) & Filed PDF | **49 tracked actions** by Hazel Remesch (Sept 14, 19, and 22, 2017) | **3** | `2017-09-14_after_first_revision_cluster`<br>`2017-09-19_after_follow_up_revision_cluster`<br>`2017-09-22_current_accepted` |
| **Summary Judgment** | `T_Thomas` | Motion for Summary Judgment | Word (.docx) & Filed PDF | **0 tracked actions** (track changes mode was active; filename indicates "version 3") | **1** | `current_source_copy_no_embedded_text_revisions` |
| **Appellate Briefs** | `A_Hooper` | Brief of Appellant (Opening Brief) | Word (.docx) & Filed PDF | **0 tracked actions** (filed 2026-03-10) | **1** | `2026-03-10_source_copy_no_embedded_track_changes` |
| **Appellate Briefs** | `A_Hooper` | Appellant's Reply Brief | Word (.docx) & Filed PDF | **0 tracked actions** (filed 2026-04-30) | **1** | `2026-04-30_source_copy_no_embedded_track_changes` |
| **Appellate Briefs** | `M_Vourliotis` | Opening Brief Appellant-Defendant | Word (.docx) & Filed PDF | **0 tracked actions** (filed 2024-10-01) | **1** | `2024-10-01_source_copy_no_embedded_track_changes` |
| **Appellate Briefs** | `M_Vourliotis` | Appellant's Reply Brief | Word (.docx) & Filed PDF | **0 tracked actions** (filed 2024-11-22) | **1** | `2024-11-22_source_copy_no_embedded_track_changes` |
| **Appellate Briefs** | `T_Rubalcava` | Appellants' Brief & Appellants' Reply Brief | Filed PDFs only | *N/A (PDF only)* | **0** | *None reconstructed as DOCX* |
| **Totals** | **7 Matters** | **9 Word Briefs (+ 2 PDF Briefs)** | | | **15** | **15 DOCX benchmark files** |

---

## 3. Detailed Per-Brief Revision Analysis

### A. Multi-Revision Briefs (3 Briefs / 9 Logical Snapshots)

These three briefs contain internal revision history embedded within Microsoft Word OOXML elements (`<w:ins>`, `<w:del>`, `<w:rPrChange>`, and `<w:comment>`). They were reconstructed into point-in-time snapshots in `cle_real_briefs/revision_snapshots/word_versions/` without modifying the original source files.

#### 1. Residents of Perry and Fairgrounds (Manufactured Home Park Dispute, R.C. 4781)
- **Legal Context**: Tenant association action regarding park maintenance failure, utility fee inflation, and disclosure violations.
- **Embedded Revision Evidence**:
  - **2,261 total tracked actions** (text additions, deletions, formatting changes).
  - Heavy concentration of edits on May 29 and May 30, 2024.
  - Review comments by senior advocates: Eric Zell ("good shape" review on May 15, 2024) and Abigail Staudt (local-rule, line spacing, and exhibit cross-referencing notes on May 20, 2024).
- **Logical Snapshots (3 total)**:
  1. `2024-05-20_before_late_revision_cluster.docx`: Captures the pre-cluster state incorporating initial supervisory comments; contains unresolved drafting placeholders (`[name the five claims]`, `[ADD]`, `[EXAMPLES]`).
  2. `2024-05-29_after_review_revision_cluster.docx`: Mid-revision state; resolves `[ADD]`, leaving remaining placeholders.
  3. `2024-05-30_current_accepted.docx`: Fully resolved state prior to May 31 filing, with all placeholders cleared and citations formatted.

#### 2. L. Wheeler against Pine Creek (Lead Abatement Compliance & Rent Escrow, R.C. 5321)
- **Legal Context**: Tenant affirmative summary-judgment motion regarding lead-hazard orders issued by the Cleveland Department of Public Health and rent escrow compliance.
- **Embedded Revision Evidence**:
  - **7 tracked text actions** (discrete insertions and deletions) dated May 30, 2025 through June 3, 2025.
  - Comment thread spans May 5 through May 22, 2025, debating evidentiary support, municipal ordinance references, and affidavit coverage.
- **Logical Snapshots (3 total)**:
  1. `2025-05-30_after_initial_revision_cluster.docx`: Initial revision pass following the comment review.
  2. `2025-06-02_after_follow_up_revision.docx`: Minor adjustment to factual narrative.
  3. `2025-06-03_current_accepted.docx`: Final local accepted state. (Persistent drafting blanks `[NAME OF ORDINANCE]` and `[Add this section]` remained in the text, providing a reliable test target for placeholder checks).

#### 3. L. Moore (Section 8 Rent Acceptance & Waiver Defense)
- **Legal Context**: Eviction defense asserting waiver of notice to vacate through the housing authority's ongoing acceptance of Section 8 HAP rent subsidies.
- **Embedded Revision Evidence**:
  - **49 tracked insertion and deletion actions**, all authored by supervising attorney Hazel Remesch.
  - Edits form three distinct chronological clusters: September 14, September 19, and September 22, 2017.
- **Logical Snapshots (3 total)**:
  1. `2017-09-14_after_first_revision_cluster.docx`: Snapshot after the first substantive edit pass.
  2. `2017-09-19_after_follow_up_revision_cluster.docx`: Snapshot after follow-up text refinement.
  3. `2017-09-22_current_accepted.docx`: Clean accepted state reflecting the final motion as submitted.

---

### B. Single-Version Briefs (6 Word Briefs / 6 Snapshots)

These Word files did not contain embedded historical revision markup (or contained only the track-changes setting without pending revisions). Each file was retained as a single byte-preserving source copy rather than fabricating intermediate points in time:

4. **T. Thomas MSJ**:
   - Filename: `Draft Motion for Summary Judgment - version 3.docx`.
   - Revision Evidence: Track-changes mode was toggled on in the document settings, but zero `<w:ins>` or `<w:del>` elements were present.
   - Snapshot: 1 source copy (`current_source_copy_no_embedded_text_revisions.docx`).
5. **L. Wheeler MSJ against Gentile**:
   - Filename: `Gentile MSJ Final 09-28-2025.docx`.
   - Revision Evidence: Zero embedded tracked revisions. Accompanied by a 3-part filed PDF.
   - Snapshot: 1 source copy (`current_source_copy_no_embedded_text_revisions.docx`).
6. **A. Hooper — Appellant's Brief (Opening)**:
   - Filename: `2026-03-10 Brief of Appellant (final).docx`.
   - Snapshot: 1 source copy (`2026-03-10_source_copy_no_embedded_track_changes.docx`).
7. **A. Hooper — Appellant's Reply Brief**:
   - Filename: `2026-04-30 Reply Brief.docx`.
   - Snapshot: 1 source copy (`2026-04-30_source_copy_no_embedded_track_changes.docx`).
8. **M. Vourliotis — Opening Brief Appellant-Defendant**:
   - Filename: `Opening Brief Appellant-Defendant 10.1.24.docx`.
   - Snapshot: 1 source copy (`2024-10-01_source_copy_no_embedded_track_changes.docx`).
9. **M. Vourliotis — Appellant's Reply Brief**:
   - Filename: `2024.11.22 Appellant's Reply Brief.docx`.
   - Snapshot: 1 source copy (`2024-11-22_source_copy_no_embedded_track_changes.docx`).

---

### C. PDF-Only Matter (*Acosta v. Rubalcava*)

10. **T. Rubalcava (Eighth District Court of Appeals, 2023-Ohio-1794)**:
    - Provided solely as filed PDFs:
      - `Acosta v. Rubalcava - Appellants' Brief.pdf` (Cleveland Legal Aid opening brief)
      - `Acosta v. Rubalcava - Appellants' Reply Brief.pdf` (Cleveland Legal Aid reply brief)
      - `Acosta v. Rubalcava - Appellee's Brief.pdf` (opposing counsel brief)
      - `2023-Ohio-1794 - published appellate opinion.pdf`
    - Because no Word documents were provided, no tracked-change recovery was possible, and no files from this matter are in the `revision_snapshots/word_versions/` benchmark suite.

---

## 4. Methodological Note on Snapshots

As recorded in `cle_real_briefs/revision_snapshots/README.md`:
1. **Source Preservation**: Downloaded SharePoint files in `sharepoint_originals/` remain byte-intact and unmodified.
2. **Logical Snapshots vs. Server History**: The snapshots are logical reconstructions derived from timestamps inside the OOXML track-change tags and comment metadata. They are not direct exports of SharePoint server-side version history.
3. **Reproducibility**: The deterministic Argument Gym benchmark scripts (`scripts/benchmark_real_briefs.py`) consume the 15 reconstructed snapshot DOCX files under `cle_real_briefs/revision_snapshots/word_versions/`.

# Argument Gym Lab Notebook

This directory records experimental runs, empirical evaluations, and technical audits of the Argument Gym benchmarking pipeline against real-world Cleveland legal briefs (`cle_real_briefs`) and synthetic minimal-pair reasoning suites.

## Notebook Entries

1. [`2026-09-08_cle_real_briefs_benchmark_run.md`](./2026-09-08_cle_real_briefs_benchmark_run.md)
   - **Scope**: Comprehensive deterministic benchmark execution across all 15 Cleveland real-brief snapshots (nine revision snapshots across three multi-version families, plus six source-copy briefs).
   - **Data**: Character counts, structural units, deterministic check findings (pleading form, grammar, legal language, court compliance), rule audits, fallback challenges, and verdicts.
   - **Cross-Run Comparison**: Contrasts the complete 15-document deterministic baseline with prior live-model experiments (`gpt-5.5` runs on Moore, Pine Creek, and Perry) and the 18-scenario synthetic benchmark.

2. [`test_evaluation_and_feedback.md`](./test_evaluation_and_feedback.md)
   - **Scope**: In-depth analysis and technical feedback on what Argument Gym checks and benchmarks capture that is legally and practically meaningful, and what constitutes noise, false alarms, or mechanical proxies.
   - **Sections**:
     - Deterministic Document Checks (Placeholders, Grammar, Confused Words, Court Rules)
     - Rule Element Audits & Keyword Collision
     - Pipeline Fallback vs. Live Adversarial Reasoning
     - Structural Ingestion & The 80-Unit Prompt Ceiling
     - Synthetic Minimal Pairs vs. Real Brief Evaluation
     - Concrete Engineering Recommendations

3. [`2026-09-08_check_suite_remediation.md`](./2026-09-08_check_suite_remediation.md)
   - **Scope**: Remediation of every noise, false-alarm and architectural finding in entry 2, each measured against the same 15 briefs before and after; plus the addition of the persuasive communication suite.
   - **Headline**: grammar findings 60 -> 31 (bogus lowercase sentence starts 71 -> 6, of which 2 are real); appellate prayer-for-relief false negatives 8 -> 0; 20 fabricated unmet elements removed from phrase-only rule matches; spurious offline challenges 18 -> 4; and the 80-unit prompt ceiling replaced by a 60,000-character budget sampled across the document, which took Perry from 4 of its 112 argument units to all 112.
   - **Ceiling raise (§8b)**: budget made configurable and raised to 260,000 characters so all 10 distinct briefs are read whole with no unit truncated; two further 12,000-character truncations removed from the rule audit and checklist; brief input per run rises 1.6x.
   - **Method note**: three fixes were caught *by* the corpus rather than by the tests — an enumerator strip that broke `(Attached as Appendix A)`, and a quiet stand-in that turned false alarms into false reassurance.

4. [`2026-09-08_lexis_mutation_experiment_registration.md`](./2026-09-08_lexis_mutation_experiment_registration.md)
   - **Scope**: Pre-registration of a paired minimal-difference mutation study built from the 2026-09-08 Lexis delivery (`lexis_real_briefs/`): six control/mutant brief pairs, each differing by one legally meaningful change.
   - **Design**: Within-fixture pairing scored on a four-cell table (discriminating / missed / non-discriminating / reversed) rather than an accuracy rate, so a defect the Gym already flagged in the unmodified brief is not counted as a detection.
   - **Provenance**: The mutants were drafted by Claude Opus 5 and reviewed by no attorney; every fixture is `verification_status: "unverified"` and the first run against them is a pilot of the method, not a measurement of the Gym.
   - **OCR recovery (§4)**: 29 scanned filings — 1,371 pages, 2.4M characters — transcribed with Azure Document Intelligence `prebuilt-read`, which unlocked the trial-level stratum (2 fixtures) and, for 3 fixtures, the exhibits filed with the document, held byte-identical across conditions.
   - **Corpus limits recorded before results**: six of eight fixtures are appellate; five have no independent record; F008 carries a known structural tell; n=8, not the planned 25.
   - **Ceiling check (§6)**: all four input ceilings measured against all nineteen study documents — the worst is 41.5% of the unit budget, nothing truncated, nothing sampled, both conditions of every pair read identically. No ceiling needs raising.
   - **Defect found and reported, not fixed (§7)**: `split_brief_and_exhibits` reports a 2-page brief for a 13-page filed motion, because an inline "See attached Exhibit 2" in a page's first lines is read as the start of the attachments. Silent, and far more costly than any character ceiling.

5. [`2026-09-09_judge_2x2_and_mutation_runs.md`](./2026-09-09_judge_2x2_and_mutation_runs.md)
   - **Scope**: 80 live runs — 5 model configurations × 8 fixtures × 2 conditions — covering the mutation baseline and a 2×2 crossing attack model with judge model (gpt-5.6-sol × deepseek-v4-pro). 80/80 complete, 0 degraded.
   - **Headline**: the two judges do different jobs. gpt-5.6-sol answers on 100% of attacks and keeps 34%; deepseek-v4-pro answers on 65% and keeps 59% — its leniency is mostly non-response, and the pipeline counts silence as a drop.
   - **Own-family preference is asymmetric**: gpt-5.6-sol keeps 2.75× more of its own family's attacks than DeepSeek's; DeepSeek prefers its own by 1.09×. Sequencing matters — same two families, opposite seats, 2.5× difference in survival.
   - **Top-3 instability**: re-running one configuration disagrees with itself (Jaccard 0.143) about as much as two different configurations disagree (0.103). The top three are unstable, and not because of the model pairing — this reversed the single-run reading, which had no noise floor to compare against.
   - **Replication**: 4 independent measurements of every cell. Keep and answer rates clear run-to-run noise by 4–5×; three single-run figures quoted earlier were the extreme of their range and are corrected to means with spread.
   - **Three Gym defects fixed first** (§2), all of which reported success while degrading: an unhashable-`unitId` crash, a 6,000-character record cap that made a record-support test impossible, and an exhibit-boundary false positive that cut a 13-page motion to 2 pages.
   - **Not reported**: target detection, pending blind human adjudication of 367 pooled challenges.

6. [`2026-09-08_revised_code_experiment.md`](./2026-09-08_revised_code_experiment.md)
   - **Scope**: Re-execution of the complete 15-document suite against the newly revised codebase (`cle_real_briefs/benchmark_outputs/2026-09-08-revised-code-all-briefs/`), validating full empirical parity with remediation targets.

6. [`2026-09-09_cle_real_briefs_corpus_and_revisions.md`](./2026-09-09_cle_real_briefs_corpus_and_revisions.md)
   - **Scope**: Exhaustive inventory and revision provenance for the real Cleveland Legal Aid briefs corpus (`cle_real_briefs/`): mapping the 7 client matters, 9 Word brief instruments (+ Rubalcava PDF-only appeal), and exact revision counts (embedded tracked changes vs. 15 reconstructed logical snapshots).

## Execution Artifacts Reference

- **Latest Revised 15-Brief Output**: `cle_real_briefs/benchmark_outputs/2026-09-08-revised-code-all-briefs/`
- **Full-Read 15-Brief Deterministic Output**: `cle_real_briefs/benchmark_outputs/2026-09-08-all-briefs-offline-full-read/`
  - After the ceiling raise (entry 3, §8b). Identical in findings to the run below, which is the point: the budget governs only what model stages are given.
- **Post-Remediation 15-Brief Deterministic Output**: `cle_real_briefs/benchmark_outputs/2026-09-08-all-briefs-offline-after-fixes/`
- **Baseline 15-Brief Deterministic Output**: `cle_real_briefs/benchmark_outputs/2026-09-08-all-briefs-offline/`
- **Historical Live Model Outputs**:
  - `cle_real_briefs/benchmark_outputs/2026-09-06-live-moore/`
  - `cle_real_briefs/benchmark_outputs/2026-09-06-live-pine/`
  - `cle_real_briefs/benchmark_outputs/2026-09-06-live-perry/`
- **Synthetic Benchmark Results**:
  - `cle_real_briefs/benchmark_outputs/2026-09-06-synthetic-live.json`

# Held-out authority-support: 4 independent replicates (rep1–rep4)

**Date:** 2026-09-13

**Branch:** `feature-argument-gym-correctness-mode`

**Evaluation:** Held-out attorney-approved authority support suite (H001–H008)

**Total Runs:** 64 document runs (4 independent replicates × 8 pairs × 2 conditions)

**Artifacts:**
- Rep 1: `lexis_real_briefs/experiment/results/heldout-authority-terra-mistral-rep1-20260913/`
- Rep 2: `lexis_real_briefs/experiment/results/heldout-authority-terra-mistral-rep2-20260913/`
- Rep 3: `lexis_real_briefs/experiment/results/heldout-authority-terra-mistral-rep3-20260913/`
- Rep 4: `lexis_real_briefs/experiment/results/heldout-authority-terra-mistral-rep4-20260913/`

---

## 1. Protocol & Execution Conditions

Each replicate executed all eight attorney-verified authentic-control / one-span-mutant pairs under identical frozen parameters:
- **Opponent / Base model:** `gpt-5.6-terra`
- **Judge model:** `mistral-large-3`
- **Reasoning level:** `medium`
- **Check enabled:** `authority_support` only (Correctness Mode)
- **External quota protection:** CourtListener API disabled in workers (`ARGUMENT_GYM_COURTLISTENER_MAX_CITATIONS=0`); local case law, official Ohio reported decisions, CAP, and local statutory tiers available.

### Concurrency and Rate-Limit Handling
An initial attempt to launch replicates 2, 3, and 4 simultaneously with 8 workers each (24 concurrent workers) triggered transient Azure endpoint rate limits (`OpenAIBackendError`), causing the pipeline's strict integrity guard to reject degraded fallbacks. Shards were subsequently executed through bounded-concurrency worker pools (3–4 concurrent workers), running cleanly to 100% non-degraded completion with 0 failed shards.

---

## 2. Replicate-by-Replicate Target Dispositions

Target disposition on the registered citation vulnerability across all 4 independent runs:

| Fixture | Target ID | Cited Authority | Rep 1 | Rep 2 | Rep 3 | Rep 4 | Consistent? |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **H001** | `u90:authority1` | *Robb v. Chagrin Lagoons* | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | **YES (100%)** |
| **H002** | `u86:authority1` | *Marsol Apt. Co. v. Vannuci* | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | **YES (100%)** |
| **H003** | `u51:authority2` | *Boone Coleman Constr.* | REVIEW $\rightarrow$ REVIEW | REVIEW $\rightarrow$ REVIEW | REVIEW $\rightarrow$ REVIEW | REVIEW $\rightarrow$ REVIEW | **YES (100%)** |
| **H004** | `u24:authority1` | R.C. 5321.01(A) | REVIEW $\rightarrow$ REVIEW | REVIEW $\rightarrow$ REVIEW | REVIEW $\rightarrow$ REVIEW | REVIEW $\rightarrow$ REVIEW | **YES (100%)** |
| **H005** | `u62:authority1` | *Armstrong v. Best Buy Co.* | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | **YES (100%)** |
| **H006** | `u76:authority1` | *Grava v. Parkman Twp.* | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | **YES (100%)** |
| **H007** | `u5:authority2` | *Estate of Jacob* / R.C. 2113 | REVIEW $\rightarrow$ REVIEW | REVIEW $\rightarrow$ REVIEW | REVIEW $\rightarrow$ REVIEW | REVIEW $\rightarrow$ REVIEW | **YES (100%)** |
| **H008** | `u99:authority2` | *Wilson v. Garcia* | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | PASS $\rightarrow$ MUST_FIX | **YES (100%)** |

---

## 3. Aggregate Performance Across Replicates

Four independent runs of 16 documents each ($N=64$ document runs, 32 paired tests):

| Metric | Rep 1 | Rep 2 | Rep 3 | Rep 4 | Mean $\pm$ s.d. |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Paired Discrimination ($0\!\rightarrow\!1$)** | 5 / 8 (62.5%) | 5 / 8 (62.5%) | 5 / 8 (62.5%) | 5 / 8 (62.5%) | **62.5% $\pm$ 0.0%** |
| **Control Specificity (ctrl $\ne$ MUST_FIX)** | 8 / 8 (100%) | 8 / 8 (100%) | 8 / 8 (100%) | 8 / 8 (100%) | **100.0% $\pm$ 0.0%** |
| **Exact Control Pass Rate** | 5 / 8 (62.5%) | 5 / 8 (62.5%) | 5 / 8 (62.5%) | 5 / 8 (62.5%) | **62.5% $\pm$ 0.0%** |
| **Unresolved Pairs (REVIEW $\rightarrow$ REVIEW)** | 3 / 8 (37.5%) | 3 / 8 (37.5%) | 3 / 8 (37.5%) | 3 / 8 (37.5%) | **37.5% $\pm$ 0.0%** |
| **Reversals ($1\!\rightarrow\!0$)** | 0 / 8 (0.0%) | 0 / 8 (0.0%) | 0 / 8 (0.0%) | 0 / 8 (0.0%) | **0.0% $\pm$ 0.0%** |
| **Non-degraded Runs** | 16 / 16 | 16 / 16 | 16 / 16 | 16 / 16 | **100% (64/64)** |

---

## 4. Key Findings

1. **Deterministic Stability ($s.d. = 0.0\%$)**:
   Unlike Experiment 1's discursive pipeline—which exhibited severe run-to-run instability (a Jaccard agreement of only 0.143 between identical runs)—the revised Correctness Mode produced **100% identical paired outcomes across all four independent replicates**. Every single fixture yielded the exact same target disposition in every run.
2. **Zero False Alarms on Clean Controls**:
   In all 32 control brief runs across the four replicates, zero clean target authorities were flagged as `MUST_FIX` (100% specificity).
3. **Fail-Closed Retrieval Gaps (H003, H004, H007)**:
   The three missed mutations (H003 standard of review, H004 statutory definition, H007 nested attribution) were consistently classified as `REVIEW` in both control and mutant across all four replicates. The system faithfully adhered to its fail-closed design: unretrieved authority text produced an unverifiable `REVIEW` state rather than a hallucinated defect.
4. **Conclusion**:
   Replication confirms that stochasticity is negligible under bounded, evidence-anchored judging. The 62.5% discrimination rate is capped entirely by upstream retrieval and target-span resolution, not by model judgment variability.

## 5. Reproduction

The committed fixture directories contain only extracted text of public court
filings and their one-span mutations; the original Lexis PDFs and DOCX files
are excluded. Each result shard's `report.public.json` contains both conditions
and the fields used below, without raw prompts, database copies, or retrieved
corpus dumps.

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/score_authority_stability.py \
  --fixtures-dir lexis_real_briefs/experiment/fixtures-heldout-authority-20260913 \
  --run lexis_real_briefs/experiment/results/heldout-authority-terra-mistral-rep1-20260913 \
  --run lexis_real_briefs/experiment/results/heldout-authority-terra-mistral-rep2-20260913 \
  --run lexis_real_briefs/experiment/results/heldout-authority-terra-mistral-rep3-20260913 \
  --run lexis_real_briefs/experiment/results/heldout-authority-terra-mistral-rep4-20260913
```

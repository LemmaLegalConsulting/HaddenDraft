# F008 — reviewer packet

**Defendant Carolyn Baker's Motion for Summary Judgment**  
Court of Common Pleas of Ohio, Geauga County · filed 2024-03-07 · defendant  
Case family `friese-v-baker--23p000020` · stratum `trial_eviction`

> You are reviewing the **fixture**, not the Argument Gym. No Gym output
> appears in this packet, and you should not seek any out before you answer.
> If you have already seen results for this fixture, say so on the
> adjudication form instead of answering.

## What is in front of you

| File | What it is |
|---|---|
| `01-control.txt` | the filing as filed, normalized but not edited |
| `02-mutant.txt` | the same filing with one change |
| `03-the-change.diff` | that change, in context — read this first |
| `04-the-claim.md` | what the change is asserted to have done, and why |
| `05-record/` | the 1 record document(s) filed with it, **byte-identical in both conditions** |

The change is **1343 characters** of a 15345-character filing (8.75%), in III.B -- no statutory duty to install handrails.

## The four questions

**1. Are the control and the mutant identical except for the intended change?**

> Read 03-the-change.diff. Anything else that differs -- a heading that no longer follows its neighbour, a renumbered section, a dangling cross-reference -- is a second change and disqualifies the fixture.

**2. Is the control free of the targeted defect?**

> If the unmodified filing already has this problem, the mutation did not introduce it and the pair cannot demonstrate sensitivity.

**3. Does the mutant actually contain the targeted defect?**

> Read 04-the-claim.md against the mutant and, where there is one, the record. The claim has to be true, not just plausible.

**4. Is the defect material enough that competent opposing counsel could reasonably raise it?**

> Not 'would a machine notice it' -- would a lawyer on the other side use it. A defect nobody would argue is not a useful test.

Answer all four in `review/ADJUDICATION.yaml`. **Only yes / yes / yes / yes
admits this fixture to the held-out benchmark.** A `no` is not a failure —
it is the packet doing its job, and the fixture moves to the development set.

## What you are not being asked

- whether the mutation is the *best* one available in this filing
- whether the control is a good brief
- whether the Gym will catch it

---

*Mutations drafted by a language model (Claude Opus 5) on 2026-09-08; no attorney has reviewed them. Control text: ocr_scan.*

# Attorney-reviewed rule-floor micro experiment, replicate 1

Date: 2026-09-13  
Branch: `feature-argument-gym-correctness-mode`  
Frozen-system commit at launch: `88bac11` plus the uncommitted generator-only
review hardening later committed with this note  
Artifact: `lexis_real_briefs/experiment/results/heldout-rule-floor-llama-sol-attorney-reviewed-rep1-20260913/`

## Protocol

Azure `llama-4-maverick` authored ten synthetic rule-element control/mutant
pairs. An independent `gpt-5.6-sol` agent rejected generations until each
registered pair passed its substantive pre-attorney review. The user then
expressly approved the validity of all scenarios and planted omissions. Review
forms were completed before exposure, and the approved corpus was copied to
`fixtures-rule-floor-attorney-reviewed-20260913` before execution.

Only `rule_elements` ran. `gpt-5.6-terra` was the challenger/base model and
different-family `mistral-large-3` was Judge, with medium reasoning. Ten
isolated pair workers ran concurrently, with control and mutant sequential
inside each worker. No gold labels or condition names reached the models.

The 20 documents completed in 78.8 seconds wall time. The 54 model calls totaled
375.6 seconds when concurrent elapsed times are summed.

## Registered target outcomes

| Fixture | Registered target | Control | Mutant | Discriminated? |
| --- | --- | --- | --- | --- |
| R001 | `rc-1923-04-waiver-rent:future_rent` | PASS | MUST_FIX | yes |
| R002 | `rc-5321-11-notice-to-cure:specific_act` | PASS | MUST_FIX | yes |
| R003 | `rc-5321-11-notice-to-cure:condition_not_remedied` | PASS | MUST_FIX | yes |
| R004 | `rc-5321-15-self-help:resulting_damage` | PASS | MUST_FIX | yes |
| R005 | `rc-5321-02-retaliation:causal_connection` | PASS | MUST_FIX | yes |
| R006 | `rc-5321-04-landlord-duties:condition_described` | PASS | MUST_FIX | yes |
| R007 | `vawa-eviction-protection:direct_result` | REVIEW | MUST_FIX | yes |
| R008 | `hud-project-based-24-cfr-247-notice:ten_day_discussion_advisement` | PASS | MUST_FIX | yes |
| R009 | `hud-public-housing-termination-grievance:notice_content` | REVIEW | MUST_FIX | yes |
| R010 | `common-law-timely-rent-tender:timely_full_tender` | PASS | MUST_FIX | yes |

Primary paired results:

- mutation detection: 10/10;
- matched specificity (control target not MUST_FIX): 10/10;
- exact control PASS: 8/10;
- paired discrimination: 10/10;
- reversed pairs: 0/10; and
- registered control targets at REVIEW: 2/10.

This is a perfect first-run result for the preregistered target-level paired
outcome. It supports mutation sensitivity and matched target specificity on
these synthetic, selected, attorney-approved examples. One run does not
establish repeatability, and synthetic omissions do not establish performance
on natural attorney drafting.

## Technical integrity

- Results completed and non-degraded: 20/20.
- Judge calls: 20.
- Missing candidate rulings: 0.
- Extra candidate rulings: 0.
- Blank Judge reasons: 0.
- Adverse rulings without evidence references: 0.
- Saved model transcripts: 54.
- Maximum conservative prompt estimate: 4,064 tokens.
- Prompts exceeding the 128,000-token window with a 16,000-token reserve: 0.

## Global-cleanliness caveat

The registered outcome is per target, but the checker evaluated every element
of each invoked profile. Four controls produced seven additional MUST_FIX
findings outside the planted target:

- R001 omitted the notice's service date from the brief, although the record
  contained it.
- R003 referred generically to the covered breach, specification, and timing
  rather than stating the covered obligation, health/safety effect, and dates.
- R008 did not independently establish program coverage in its record; its
  separate timing finding may reflect an overstrict interpretation of the
  profile's program-and-ground-specific timing requirement.
- R010 did not independently connect the eviction complaint to the same March
  rent period in the fictional record.

There were seven additional control MUST_FIX findings and six additional mutant
MUST_FIX findings after excluding the ten registered targets. Thus the
experiment shows excellent target discrimination but does not show a low-noise
globally clean lint run. The extra findings must be reported separately rather
than treated as target-level false positives or ignored.

## Interpretation and next step

The strongest justified statement is: in this first run, the named
`rule_elements` test detected all ten attorney-approved planted omissions and
did not assign MUST_FIX to any matched control at the same test identity. The
Judge contract and context budget held. Before claiming that clean briefs pass
quietly, either attorney-adjudicate all additional findings or construct controls
that are independently complete for every item in the invoked profile. A second
unchanged replicate is needed for a stability claim.

# Registered rule-elements micro experiment — 2026-09-13

Status: **registered before execution; proposed fixtures await attorney review**

## Question

Can the correctness-mode `rule_elements` check distinguish a complete
application of a verified housing-law rule from the same memorandum after the
only paragraph applying one required element is deleted?

This is a synthetic micro experiment and not part of the authentic H001–H008
authority-support corpus. It is a narrow correctness-floor probe, not evidence
of performance on natural omissions in attorney-authored briefs.

## Corpus and authorship

Ten new fictional pairs, R001–R010, are authored by the Azure deployment
`llama-4-maverick`. Llama receives the applicable source-controlled, verified
profile from `content/legal-rules/`, but receives no Argument Gym prompt,
implementation, or output. The program mechanically creates the mutant by
deleting one standalone target paragraph; the fictional record is identical in
both arms.

The generator, exact prompts, raw responses, parsed responses, hashes, and
review forms are preserved. Generated legal documents remain in the ignored
private review workspace
`lexis_real_briefs/experiment/rule-floor-review-20260913/` and must not be
committed. They are proposals, not gold labels, until attorney review.

| Pair | Verified profile | Deleted target |
|---|---|---|
| R001 | `rc-1923-04-waiver-rent` | `future_rent` |
| R002 | `rc-5321-11-notice-to-cure` | `specific_act` |
| R003 | `rc-5321-11-notice-to-cure` | `condition_not_remedied` |
| R004 | `rc-5321-15-self-help` | `resulting_damage` |
| R005 | `rc-5321-02-retaliation` | `causal_connection` |
| R006 | `rc-5321-04-landlord-duties` | `condition_described` |
| R007 | `vawa-eviction-protection` | `direct_result` |
| R008 | `hud-project-based-24-cfr-247-notice` | `ten_day_discussion_advisement` |
| R009 | `hud-public-housing-termination-grievance` | `notice_content` |
| R010 | `common-law-timely-rent-tender` | `timely_full_tender` |

These scenarios and target applications differ from prior Q001–Q014
development fixtures. The IDs, texts, and case families are new.

## Attorney acceptance gate

Before any Gym execution, an attorney reviews both arms and the record for each
pair and sets every field in `attorney-review.json`. Approval requires all of:

1. The control correctly and expressly applies every applicable profile item.
2. The fictional record supports every factual application.
3. The deletion removes only the registered target application.
4. The mutant clearly omits that target while still invoking the rule.
5. The expected `rule_elements/<profile>:<target> → MUST_FIX` label is legally
   correct.

Any rejected pair is excluded or regenerated before execution. It is not fixed
after seeing Gym output. The audit command is:

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/generate_rule_floor_review_fixtures.py --audit
```

## Frozen execution and outcomes

Only the `rule_elements` check runs. The intended production routing is frozen
for this micro experiment: `gpt-5.6-terra` challenger/base and
`mistral-large-3` Judge, reasoning `medium`. Neither model authored the briefs.
Each pair's control and mutant remain sequential within a worker; pairs may run
in parallel.

The primary unit is the registered `checkId + targetId`. For each accepted pair:

- mutation detection: mutant target is `MUST_FIX`;
- matched specificity: control target is not `MUST_FIX`;
- paired discrimination: both conditions above hold;
- reversal: control is `MUST_FIX` while mutant is not;
- noise: additional `MUST_FIX` findings outside the registered target.

Report counts out of the number accepted, every disposition, all degraded or
unavailable checks, and all additional findings. Do not silently count a check
that could not run as PASS. Given the small synthetic sample, results are
descriptive; no broad claim about natural attorney drafting follows.

## Stop rule

Registration and attorney review occur before execution. Once any R fixture has
been run, no prompt, profile, target, filing, record, or gold label may be tuned
in response and still count as this experiment. A code or provider failure may
be rerun under the identical frozen condition, with the failed attempt retained
and disclosed.

## Generation record (added after generation, before Gym execution)

The ten proposed pairs were generated through the repository's configured
Azure OpenAI-compatible endpoint using deployment `llama-4-maverick`. All ten
have an exact request prompt, raw successful response, parsed response, model
name, and content hashes in the private `authorship.json`/`fixture.json` files.
No credential is recorded. The hardened audit revalidates the saved model
response as well as pair shape. It currently admits seven proposals to attorney
review and rejects R006, R009, and R010 for leaked unit-test vocabulary; those
three require fresh Llama generations. Every retained pair remains
`PENDING_ATTORNEY_REVIEW`.

Generation command:

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/generate_rule_floor_review_fixtures.py
```

An additional stricter regeneration pass rejected draft replacements that did
not meet its schema or filing-language gates. Rejected output is not a gold
fixture; the original proposed response remains available for attorney
acceptance or rejection. This underscores why the attorney gate is mandatory.

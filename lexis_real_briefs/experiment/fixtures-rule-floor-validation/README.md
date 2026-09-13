# Fresh synthetic rule-floor validation fixtures

Q005–Q014 are ten fictional matched pairs for checking whether the Argument
Gym's `rule_elements` test generalizes beyond the four development fixtures.
Azure `llama-4-maverick` authored each scenario, filing, target paragraph, and
record from a verified rule contract. The author model did not see the Gym
prompts or implementation. A script then creates the mutant by deleting exactly
one target paragraph and supplies byte-identical record material to both arms.

The set spans ten verified profiles: late-rent course of dealing, timely rent
tender, counterclaim offset, two Housing Choice Voucher rules, two
project-based HUD procedures, public-housing grievance process, reasonable
accommodation, and security deposits. It is synthetic qualification material,
not attorney-adjudicated benchmark data.

`authorship.json` preserves the author prompt, raw response, parsed response,
and any pre-run researcher normalization. `fixture.json` records hashes and the
expected stable `checkId + targetId`. Researcher normalization occurred before
the first Gym run and was limited to removing duplicate target-specific prose
outside the marked paragraph and one inaccurate court-level characterization.

Regenerate or reapply the recorded normalizations with:

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/generate_rule_floor_validation_fixtures.py
.venv/bin/python lexis_real_briefs/experiment/tools/generate_rule_floor_validation_fixtures.py --renormalize-existing
```

Do not tune the checker against these fixtures and then continue to describe
them as fresh validation data. If a fixture proves invalid, preserve its result
and document the exclusion before creating a new validation set.

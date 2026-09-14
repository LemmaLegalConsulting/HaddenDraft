# R001–R010 attorney review workspace

These are **proposed, unverified, Llama-authored** synthetic fixtures. They have
not been run through Argument Gym. Do not move them into a runnable/frozen
corpus until every accepted pair passes attorney review.

For each `Rxxx` directory, review in this order:

1. `fixture.json` — confirm the named verified profile, target, and expected
   `MUST_FIX` result are legally right.
2. `normalized/brief.txt` and its `attachments/record-01.txt` — confirm the
   control applies every applicable profile item and the record supports it.
3. `mutant/brief.txt` — confirm it differs only by loss of the target paragraph,
   remains coherent, and now clearly omits that one required application.
4. `authorship.json` — provenance containing the exact prompt and raw Azure
   `llama-4-maverick` response; it contains no credential.
5. `attorney-review.json` — add your name/date and set each criterion and
   `approved` to `true`, or leave approval false and explain rejection in
   `notes`.

Llama output is intentionally not silently repaired. Reject a fixture if it
uses internal identifiers, repeats target facts elsewhere, misstates a rule,
has inconsistent party posture, lacks support, or omits another required item.
Regenerate rejected fixtures before any Gym run; never repair them after seeing
Gym output.

Check readiness from the repository root:

```bash
.venv/bin/python lexis_real_briefs/experiment/tools/generate_rule_floor_review_fixtures.py --audit
```

The strict audit now reports ten mechanically eligible proposals. An
independent `gpt-5.6-sol` substantive review also accepted all ten for the
user's legal review. They intentionally remain `PENDING_ATTORNEY_REVIEW`;
`APPROVED` means only that every attorney-review field is true and is not
inferred from the agent review.

The source-controlled preregistration is
`lexis_real_briefs/experiment/RULE_FLOOR_MICRO_REGISTER_20260913.md`.

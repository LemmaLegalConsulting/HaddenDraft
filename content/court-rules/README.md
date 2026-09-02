# Court filing-rule profiles

One YAML file per court or tribunal. A profile carries two things: how to
recognize that this is the court a document is headed to, and the deterministic
filing requirements a document for that court has to meet — required elements,
type size, spacing, margins, page limits.

These are **format** rules, not law. Nothing here decides a case; it decides
whether a clerk would reject the paper.

## Verification is part of the record

Local rules change, courts amend them without notice, and a rule that is wrong
is worse than a rule that is absent: it tells an advocate their filing is fine
when it is not. So every profile states its own verification status, and the
checker says which status a finding came from.

- `verification: verified` — someone read the court's own published local rules
  and recorded the citation in `source` and `source_url`, with the date in
  `verified_on`. Only then are its findings reported as errors.
- `verification: unverified` — a starter profile built from widely shared
  conventions rather than from a specific court's rules. Its findings are
  reported as warnings and labelled as coming from an unverified profile.

The two profiles shipped here are deliberately generic and unverified. They
exist so the check runs on a fresh checkout, not so an office relies on them.
Add your own court, cite its local rules, and mark it verified.

## Managing profiles

- Files here are seeded into the database with
  `.venv/bin/python backend/manage.py sync_content_library`.
- Seeding never overwrites a profile edited in Django admin. Editing one in
  admin sets `is_locally_edited`, and re-seeding skips it. Use
  `--update-court-rules` to intentionally overwrite from the files.
- Profiles are edited day to day in Django admin under **Court profiles**.

## Schema

```yaml
schema_version: 1
slug: cleveland-municipal-housing          # unique, kebab-case
name: Cleveland Municipal Court, Housing Division
court_type: municipal                      # municipal | county | common_pleas |
                                           # appellate | supreme | federal_district |
                                           # federal_appellate | administrative
state: Ohio
county: Cuyahoga                           # blank where it does not apply
municipality: Cleveland                    # blank for appellate and state-wide courts
division: Housing Division                 # blank where it does not apply

# Strings that identify this court in a caption or a case record. Matching is
# punctuation- and case-insensitive.
aliases:
  - Cleveland Housing Court

verification: unverified
source: ""                                 # the local rule these requirements come from
source_url: ""
verified_on: ""                            # YYYY-MM-DD

# Which kinds of paper these rules cover. A pleading type absent here is
# reported as "no rules on file", never as a pass.
pleading_types: [motion, memorandum, answer, brief]

formatting:
  fonts:
    allowed_families: [Times New Roman, Arial]   # empty list means no restriction
    min_size_pt: 12
    footnote_min_size_pt: 10
  spacing:
    body: double                            # double | one_and_a_half | single | any
  margins_in:
    top: 1.0
    bottom: 1.0
    left: 1.0
    right: 1.0
  page_limits:
    - pleading_types: [motion, memorandum]
      max_pages: 15
    - pleading_types: [reply]
      max_pages: 10

# Text that has to be present. `patterns` are case-insensitive regular
# expressions; any one of them satisfies the element.
required_elements:
  - id: caption
    label: Case caption naming the court and case number
    severity: error
    pleading_types: []                      # empty means every pleading type
    patterns:
      - "in the .{0,60}court"
      - "case (no\\.?|number)"
```

# Template field mappings

`legalserver.yaml` contains reviewed defaults for **Fill template — no AI**.
These are independent of `legalserver-field-maps/`, which writes triage outcomes
back to LegalServer. This directory only reads matter data.

Run `.venv/bin/python backend/manage.py seed_template_field_maps`. Preparation
also inserts missing defaults. Existing administrator edits, including disabled
rows, are preserved. Provider precedence follows `apps.core.content_library`.

In Django admin, **Template field mappings** is an editable table attached to the
installation's Organization settings. `field` is the complete template expression,
for example `fields.hearing_date` or `clients[0].name.first`. `source_path` is
relative to `Matter.raw_payload`, such as `custom_fields["hearing date"]` or
`litigations[0].docket`. Dot notation, quoted dictionary keys, and literal list
indexes (0–999) are supported; functions and expressions are not.

An optional `template_slug` restricts a mapping to one template. Its row overrides
an organization-wide mapping. Human answers override mappings, including a
human's intentional blank. Disabled or unresolved mappings leave a prompt and
report the reason; they do not fall back to another guessed value. Mapping changes
apply to new sessions. Existing sessions retain their values and provenance.

Formatters: **Display value** unwraps LegalServer lookup names or display/raw
value wrappers; **Raw value** keeps the scalar as supplied; **Address** renders a
postal address object. Objects/lists can populate collection inputs, but are never
silently printed in a scalar field. Zero and false are values.

The defaults follow WorkflowDocs `support_legalserver.yml` and the corresponding
LegalServerLink `populate_client`, `populate_case`, `populate_litigations`, and
`populate_adverse_parties` assignments. They cover common scalar names and literal
first-party/litigation indexes. Collection mappings expose LegalServer's raw array
shape; they do not implement Docassemble objects or their methods. Site-specific
fields and additional indexes belong in admin. A LegalServer matter number is not
a court docket number; the defaults keep them distinct.

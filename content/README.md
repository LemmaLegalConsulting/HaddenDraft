# Maintained legal content library

This directory is the public, source-controlled seed library for reusable
legal-content assets. Organization-specific templates are not stored here.
They use the same logical layout under `ORGANIZATION_CONTENT_LIBRARY_DIR`
(default: the git-ignored `private-content/` directory). Keeping both providers
behind the same layout allows a future SharePoint folder to replace the private
local provider without changing drafting, triage, or retrieval workflows.

## Layout

```text
content/                       # public, safe-to-commit defaults
├── docx-snippets/
│   └── _shared/blocks/       # generic, non-confidential defaults only
├── treatises/
│   ├── source/               # authoritative incoming PDFs; do not edit PDFs here
│   └── markdown/             # deterministic Markdown derivatives, organized by treatise slug
├── drafting-rules/
│   ├── style-guides/source/  # court manuals and drafting guidance, not substantive authority
│   └── checks/               # versioned machine-readable drafting/quality rules
├── statutes/
│   └── ohio-revised-code/    # configured official-code scope and generated section index
├── research-sources/         # reviewable Auto-research routing policy
└── triage-rubrics/           # YAML files seeded into TriageRubric records

private-content/               # organization provider; ignored by git
├── original_templates/         # received private source DOCX files
├── document-templates/         # generated DOCX/Jinja packages and manifests
├── template-overrides/         # private YAML corrections/field schemas by template slug
└── docx-snippets/
    └── <template-slug>/blocks/ # organization/pathway-specific blocks
```

Use lowercase kebab-case directory and file names. Keep each source file small,
reviewable, and jurisdiction- or organization-specific where applicable. Do not
place client documents, credentials, or other confidential material in this
repository.

## DOCX snippets

Public `docx-snippets/_shared/blocks/` may hold generic defaults such as a
non-organization-specific caption or signature. Organization and pathway
overrides belong under
`ORGANIZATION_CONTENT_LIBRARY_DIR/docx-snippets/<template-slug>/blocks/`.

The current resolver checks, in order: an admin-uploaded block, the private
organization provider, the public shared provider, then the block text stored
in the database. Existing package-local Word files remain a legacy fallback
while assets are migrated. Never commit organization-specific DOCX files.

## Document templates

The private provider's `original_templates/` retains received source documents.
Runtime drafting uses private prepared packages under
`document-templates/<template-slug>/` when available, with private
`docx-snippets/<template-slug>/blocks/` as the durable fallback. Each prepared package contains a formatting-preserving
`template.docx` and `manifest.yaml` defining its blocks, fields, checksums, and
provenance.

Run `.venv/bin/python backend/manage.py ingest_document_templates` after adding
or changing a source DOCX. The converter modifies OOXML in place, preserving
headers, footers, tables, numbering, styles, sections, and embedded media.
Correct source documents or converter logic and regenerate derived packages;
do not hand-edit generated manifests or block files.

Prepared packages are read from `ORGANIZATION_CONTENT_LIBRARY_DIR` before the
public `CONTENT_LIBRARY_DIR`. The ingestion command writes only to the private
organization provider. If a provider is unavailable, existing indexed records
remain active rather than treating provider absence as deletion.

Private `template-overrides/<template-slug>.yaml` files may correct template
metadata or blocks when an organization needs to maintain fixes separately
from the public application. Overrides use `schema_version: 1`, a `slug`, an
optional `template` mapping, and a `blocks` list keyed by existing block key.
They are applied after prepared packages and database seeds. A block override
may use `create: true` for a new block or `delete: true` for an obsolete
ingestion artifact. Keep these files in the private provider, not this repo.

Maintained DOCX and block-body Jinja supports `comma_and_list`, `as_noun`,
`does_verb`, `did_verb`, `pronoun_subjective`, `pronoun_objective`,
`pronoun_possessive`, `pronoun_reflexive`, `possessive`, and `answered`.
Pronoun filters read an explicit `client_pronouns` value such as
`they/them/theirs`; they do not infer pronouns from names. Template metadata can
declare `fieldSchema` entries of type `pronouns`, `list`, or `select` so the UI
collects structured values.

## Treatises

Place received, authoritative PDFs under
`treatises/source/<treatise-slug>/`. Preserve original file names and record
the version/date in a companion `metadata.yaml` when available. A treatise may
be one versioned PDF or a configured set of section-level PDFs. The ingestion
job writes heading-preserving Markdown under
`treatises/markdown/<treatise-slug>/<version>/`, then chunks it by headings for
retrieval. Do not hand-edit generated Markdown; correct the source PDF or the
converter and regenerate it.

Run `python scripts/chunk_legal_sources.py --all` to generate the Markdown
derivative and its retrieval chunks. Each generated version directory contains
a `manifest.yaml` with the source digest, generation time, page ranges, and
chunk paths. Each chunk repeats its complete heading ancestry as a
table-of-contents context block, so it remains intelligible when retrieved on
its own. Do not hand-edit generated Markdown; correct the source PDF or the
converter and regenerate it.

This separation makes the input, deterministic derivative, and later
database/vector records independently auditable.

## Statutes

`statutes/ohio-revised-code/scope.yaml` is the reviewable acquisition policy
for the Ohio Revised Code housing corpus. It separates the prioritized rings
from the mechanically executable targets: an `all_sections` target follows
every section linked by the official chapter page; a range target follows only
the inclusive numerical range; and a `sections` target follows the named
sections.

Run `python scripts/ingest_ohio_revised_code.py --all` for an initial or
periodic complete refresh, or `--ring 1` for one ring. The normal refresh uses
one expanded official chapter page per configured chapter and derives
section-level records/chunks locally; it therefore avoids a high-volume
section-by-section crawl. Use `--chapter 5321` for a targeted chapter refresh
or `--section 5321.04` when one known section needs immediate checking. The job
compares a normalized source hash with `manifest.yaml` and rewrites only
changed section records and chunks. `--force` rebuilds selected records even
if their text is unchanged; `--dry-run` reports the proposed work without
writing. Do not hand-edit `sections/`, `chunks/`, `manifest.yaml`, or
`ohio_orc_housing_consumer.jsonl`: they are generated evidence and retrieval
derivatives.

The saved section record retains the official page/PDF URLs, effective date,
latest legislation, official last-updated timestamp, fetch timestamp, and both
raw and normalized hashes. This is required provenance for a law that is
updated on an ongoing basis. A scheduled job should run a normal refresh (for
example nightly or weekly) and alert on fetch/parse failures; it must not treat
a failed fetch as a deletion. The official code is a research source, not a
substitute for checking current law and session legislation before filing.

For example, a scheduler can run `python scripts/ingest_ohio_revised_code.py
--ring 1` after deploying the content library, then run rings 2 and 3 on a less
frequent cadence. The command exits nonzero when any selected section could not
be fetched or parsed, so the scheduler should alert and retry rather than
publishing a partial refresh as successful.

## Triage rubrics

One YAML file represents one default rubric. Required fields are `slug`, `name`,
`standard`, and `criteria`; `description` and `active` are optional. Rubrics are
seeded into the database only when their slug does not already exist, so an
admin-managed record is never silently overwritten. To intentionally apply a
changed file to an existing database record, use the content synchronization
command with its explicit update option.

## Auto research sources

`research-sources/auto-source-guidance.yaml` is the reviewable policy used by
Research mode's **Auto sources** setting. Each source declares its connector
kind, label, optional default role, and term-based routing rules with a
plain-language reason. The API returns those reasons and the number of results
from each selected source, so a user can see both why a source was searched and
when it returned no matches. Keep source IDs aligned with the Research source
picker and use logical IDs rather than file paths or connector internals.

## Future SharePoint provider

Public local files are configured by `CONTENT_LIBRARY_DIR`; private organization
files are configured by `ORGANIZATION_CONTENT_LIBRARY_DIR`. A
future admin-selected SharePoint provider should expose this exact logical layout
and read files into a staging area before validation/processing. It must retain
the SharePoint item ID, ETag, modified time, source path, checksum, and import
time with every derived database or retrieval record. The provider must not
replace public repository defaults merely because SharePoint is configured;
selection should be explicit at the organization/package level. Remote private
content must retain the same provenance and must never be copied into a tracked
repository path.

# Maintained legal content library

This directory is the source-controlled seed library for reusable legal-content
assets. It is deliberately separate from Django application packages: the same
layout can later be supplied by a SharePoint folder or another content provider
without changing the drafting, triage, or retrieval workflows.

## Layout

```text
content/
├── docx-snippets/
│   ├── _shared/blocks/       # default snippets for every template pathway
│   └── <template-slug>/blocks/ # pathway-specific overrides
├── treatises/
│   ├── source/               # authoritative incoming PDFs; do not edit PDFs here
│   └── markdown/             # deterministic Markdown derivatives, organized by treatise slug
├── drafting-rules/
│   ├── style-guides/source/  # court manuals and drafting guidance, not substantive authority
│   └── checks/               # versioned machine-readable drafting/quality rules
└── triage-rubrics/           # YAML files seeded into TriageRubric records
```

Use lowercase kebab-case directory and file names. Keep each source file small,
reviewable, and jurisdiction- or organization-specific where applicable. Do not
place client documents, credentials, or other confidential material in this
repository.

## DOCX snippets

`docx-snippets/_shared/blocks/` holds defaults such as `caption.docx` and
`signature.docx`. A template pathway can override a shared block by placing the
same file name in `docx-snippets/<template-slug>/blocks/`.

The current resolver checks, in order: an admin-uploaded block, the
pathway-specific repository block, the shared repository block, then the block
text stored in the database. Existing package-local Word files remain a legacy
fallback while assets are migrated. New or changed reusable assets belong here.

## Treatises

Place the received, authoritative PDF at
`treatises/source/<treatise-slug>/<version>.pdf`. Preserve the original file
name and version/date in a companion `metadata.yaml` when available. A future
ingestion job will write heading-preserving Markdown to
`treatises/markdown/<treatise-slug>/<version>.md`, then chunk it by headings for
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

## Triage rubrics

One YAML file represents one default rubric. Required fields are `slug`, `name`,
`standard`, and `criteria`; `description` and `active` are optional. Rubrics are
seeded into the database only when their slug does not already exist, so an
admin-managed record is never silently overwritten. To intentionally apply a
changed file to an existing database record, use the content synchronization
command with its explicit update option.

## Future SharePoint provider

Local files are the default provider configured by `CONTENT_LIBRARY_DIR`. A
future admin-selected SharePoint provider should expose this exact logical layout
and read files into a staging area before validation/processing. It must retain
the SharePoint item ID, ETag, modified time, source path, checksum, and import
time with every derived database or retrieval record. The provider must not
replace local repository defaults merely because SharePoint is configured;
selection should be explicit at the organization/package level, with local
files remaining the safe development default.

# Fill template — no AI

Choose **Fill template** after selecting a case. Choose an existing library
DOCX template or upload a DOCX (maximum 15 MB, 40 MB expanded). Review the detected
fields and values from LegalServer and the author profile. Save partial progress,
then prepare and download a DOCX. Unanswered text becomes yellow-highlighted
`[Enter …]` prompts, including tables, headers, and footers. Word, Word Online,
and other DOCX editors can replace the prompts directly.

The screen groups fields by what still has to happen: **Answer before
download** (condition inputs and collections, which stop the export when
blank), **Blank — type now or finish in Word** (which become prompts), and
**Filled in** (values from LegalServer, the profile, or earlier entries, with
their source). Groups come from the saved session so a field does not move while
it is being typed in; each row's status updates as it is edited.

Fields are listed in document order. Each row shows the paragraph its blank
sits in, parsed from the template's `{{ … }}` expressions rather than matched
by substring, with that field's blank marked and every other blank showing its
current value or name. A blank alone on its line (a signature line) borrows the
neighbouring lines. A generation slot the document never prints is not offered:
text typed into it would go nowhere.

Short one-line text blanks (sentence up to about 200 characters) are typed
straight into their sentence; **Type short blanks inside their sentence** turns
that off, and the browser remembers the choice. Multi-line answers, choices,
and JSON always use the side-by-side layout.

**Preview** renders the document exactly as an export would -- conditions
resolved, loops expanded -- from the saved answers plus anything typed since,
without saving. It is a reading view, not a layout: paragraphs, tables, bold,
italic, alignment, and the first section's header and footer. Supplied values
are marked green and prompts yellow. Selecting either opens it in a dialog
that shows its sentence; **Next blank** (or Enter) moves to the next prompt in
document order, so a document can be filled top to bottom from the preview.
Answers from the dialog join the same unsaved edits as the field list. A
condition nobody has answered is previewed as not included and listed at the
top (each name opens its field), while the export still refuses it. Rendering takes tens of milliseconds, so
the preview answers inline instead of through a job.

No model, retrieval, plan, or automatic revision runs in this workflow. Existing
AI drafting remains available separately. Generated-content slots become manual
text fields. Optional sections are off until the author includes them. Prepared exports are immutable documents with component provenance;
changing answers and preparing again produces another version.

The open session and any unsaved answers are remembered per case in the
browser (`src/state/templateFillDraft.js`). Leaving the screen, reloading, or a
deploy reopens the session with the typing restored and says so. A draft typed
against an older revision is discarded, with a notice, rather than laid over
answers saved from another window; **Reload saved values** discards it on
purpose. Nothing leaves the browser until **Save progress** or **Prepare DOCX**.

## Templates and compatibility

Uploads use the existing bracket, underscore, and highlight conversion rules.
Maintained prose and run formatting survive. Either/or alternatives become named
choices, with the first alternative selected by default. Uploaded originals are
stored in `raw/template-fill/uploads/`; prepared assets, per-session template
snapshots, and exports are in `published/template-fill/`. All access goes through
`apps.core.storage`; files are served only after case authorization.

Basic Jinja variables, literal indexes, loops, conditions, and the application's
existing deterministic language filters work. WorkflowDocs field-name defaults
are documented in `content/template-field-maps/README.md`. Docassemble methods,
rich-text/subdocument expressions, imports, includes, macros, computed indexes, private attributes, multiplication,
and exponentiation are rejected with preparation diagnostics. Unresolved control
inputs must be supplied before export; false and an empty collection (`[]`) are
explicit answers. Collection editing uses JSON with the fields referenced by the
loop. This is not a Docassemble interview runtime.

Private uploads are listed only on their case. To share one, an administrator
opens **Fill template uploads**, downloads the prepared DOCX for review, checks
**Reviewed for sharing**, and uses **Publish reviewed templates**. Review the
content and metadata for case-specific material before sharing. The raw original
is never served. Withdrawal removes the upload from the shared picker; existing
case sessions retain their immutable snapshots.

## API and operation

- `GET /api/template-fill/?matterId=…`: authorized template catalog and saved sessions.
- `POST /api/template-fill/start/`: JSON `{matterId, templateId, templateType,
  authorProfile}` or multipart `{matterId, file}`; returns 202 with a preparation job.
- `GET /api/template-fill/sessions/<id>/`: fields, values, sources, preparation
  report, revision, and recent jobs.
- `PATCH /api/template-fill/sessions/<id>/`: `{answers, revision}` saves partial
  answers; a stale revision fails rather than replacing another window's changes.
- `POST` to that session URL: `{answers, revision, saveToLegalServer}` starts an
  export and returns 202. LegalServer saving keeps the installation's document
  default and records failures without losing the downloadable file.
- `POST /api/template-fill/sessions/<id>/preview/`: `{answers}` returns the
  rendered document as blocks and segments; nothing is saved.
- `GET /api/template-fill/jobs/<id>/`: poll preparation/export status and delivery result.
- `GET /api/template-fill/jobs/<id>/file/`: download a completed export.

`TEMPLATE_FILL_BACKGROUND=true` is the production default. Like existing drafting
jobs, work runs on a background thread and records its result in the database.
Jobs still pending/running after 15 minutes are reported as failed on polling.
Tests set the setting false to execute deterministically. Apply migrations with
`.venv/bin/python backend/manage.py migrate`, then seed mappings using
`.venv/bin/python backend/manage.py seed_template_field_maps`.

# End-to-end verification findings — 2026-09-23

Findings from running every existing suite and driving the app in a
production-shaped local deployment (the production Docker image, Postgres,
`DJANGO_DEBUG=false`, split app/API origins over HTTPS with a parent-domain CSRF
cookie). Each entry says how it was found and how to reproduce it.

Severity: **high** = a feature is broken or wrong in production; **medium** = a
feature degrades or a check can pass while something is broken; **low** =
hygiene, test gaps, or confusing behaviour.

## Summary

| # | Severity | Status | Finding |
|---|---|---|---|
| F1 | medium | fixed | CI skips 263 backend tests |
| F2 | high | fixed | a local deploy uploads real briefs into the production image |
| F3 | low | fixed | every deploy re-imports the whole case-law corpus, twice |
| F4 | high | fixed | after every cold start, gunicorn workers share one Postgres socket |
| F5 | high | fixed | draft generation over 60 s fails as "Failed to fetch" while the draft is created anyway |
| F6 | medium | fixed | four upload forms throw after a successful save |
| F7 | low | fixed | every case shows "Answer and Counterclaims" as its selected document |
| F8 | low | fixed | internal codename in user-facing text |
| F9 | high | fixed | a repealed ordinance is invisible; search leads with the stale treatise instead |
| F10 | low | fixed | the case catalog's "Treatment" facet mixes in non-treatment values |
| F11 | medium | fixed | a reload silently switches the active case to a different client |
| F12 | low | fixed | "Clear" deletes a chat conversation with one click |
| F13 | medium | fixed | an advice letter downloads with a blank phone number and a login as the signature |
| F14 | high | fixed | a deployment built by bootstrap letters on no letterhead at all |
| F15 | high | fixed | for a few seconds after "Make active", every screen acts on the previous client |
| F16 | high | fixed | one answer fills every date in a court filing |
| F17 | high | fixed | the tool's own drafts and chat transcripts come back as "facts" in the next filing |
| F18 | medium | fixed | "Let AI suggest template(s)" recommended by alphabet |
| F19 | medium | fixed | three advocates waiting on the model stall everyone else |
| F20 | high | fixed | when LegalServer rate-limits, the case file silently reads as empty |
| F21 | high | fixed | updated private content never reached production |

"Fixed" means changed in this working tree and shown to work: by a regression
test that fails on the old code or, for configuration (F1, F2), by measurement; "mitigated" means the immediate failure is addressed and the
underlying design issue is still open.

## Baseline: existing suites

| Suite | Result |
|---|---|
| Backend, all 13 apps (`manage.py test ...`) | 958 tests, all pass |
| Frontend unit (`npm run test`) | 209 tests, all pass |
| Screen smoke (`npm run test:smoke`, stubbed API) | 2 tests, pass |
| Credentialed case matrix (`template-case-matrix.spec.js`), as first run against the rig | 3 of 7 pass; 4 time out because the spec assumed AI off |

## After the fixes

| Suite | Result |
|---|---|
| Backend (`cd backend && manage.py test`) | 988 tests pass (965 before the fixes, plus their regression tests) |
| Frontend unit (`npm run test`) | 222 pass |
| Screen smoke | 2 pass |
| Browser suite, rig rebuilt from the working tree (`E2E_RIG_REF=WORKTREE scripts/e2e_production_rig.sh up`) | 52 tests: **51 pass**, 1 skipped (live LegalServer writes, not authorized) |

The browser suite did not pass in one sitting. The demo LegalServer site began
answering **429 Request rate limit exceeded** after a day of test runs; with
F20 fixed the app said so ("LegalServer sync failed", `documentsUnavailable`)
instead of showing empty case files, and the five tests that need LegalServer
data were rerun after a pause and passed. The tests now say "LegalServer
returned the case's documents" when that is what failed. A full run makes
many LegalServer calls; space runs out or expect this.

## Findings

### F1 (medium, fixed) — CI skips 263 backend tests

`.github/workflows/deploy.yml` runs `manage.py test apps.ai apps.sources
apps.core apps.matters apps.caselaw apps.drafting apps.templates_app`. It omits
`apps.argument_gym`, `apps.validation`, `apps.exporting`, `apps.rules`,
`apps.facts` and `apps.issues`, which hold 263 tests (all currently passing).
A regression in the argument gym or validation deploys without a failing check.
AGENTS.md's own command list omits them too.

Fix: run the whole suite — `cd backend && python manage.py test` with no labels (from the repository root, label-less discovery finds **0 tests** and still exits 0) — or list every app.

Fixed: CI now runs `python manage.py test` from `backend/` (965 tests; verified
to pass with no `private-content`, as CI has none). AGENTS.md and README updated.

### F2 (high, fixed) — a local deploy uploads real briefs into the production image

`.dockerignore` excludes `private-content` but not `cle_real_briefs/` (893 MB),
`lexis_real_briefs/` (19 GB) or `downloaded_opinions/` (46 MB). All three are
git-ignored, so CI's checkout never has them and CI-built images are clean. But
`scripts/deploy_azure_containerapps.sh` runs `az acr build ... .` from the
developer's working tree, and the Dockerfile does `COPY . .`: the real filed
briefs are uploaded to ACR and baked into the image that serves traffic.
Found when a local `docker build .` reported a 1.7 GB context after 20 s and
still climbing. Latent rather than observed: the one production image cached
on this machine (`agentic-housing-drafting:1c24389b8b1e`) does not contain them,
so it was built before the directories existed or from a clean tree. The next
script deploy from this machine would include them.

Fix: add those directories to `.dockerignore` — or, more robustly, invert it
to an allow-list (`*` then `!backend`, `!frontend`, `!content`, `!prompts`,
`!docker`, `!scripts`, `!nginx.conf`, `!requirements.txt`), so the next
git-ignored research directory is excluded by default.

Fixed (narrowly): the three directories are now in `.dockerignore`. The
allow-list is still the more durable fix.

### F3 (low, fixed) — every deploy re-imports the whole case-law corpus, twice

`docker/bootstrap.sh` says re-running is cheap because "ingest_group skips any
decision whose source_sha256 is already recorded". It does not:
`backend/apps/caselaw/importing.py:466` checks for an existing decision and
then `pass`es, so every decision is re-imported. And production's
`CASELAW_INGEST_DIR=/app/storage/published/caselaw` is the output of the
preceding `--from-raw-storage` step, so the same 665 decisions are imported a
second time from there. Both passes report all 665 as `"status": "imported"` on
an unchanged corpus.

Verified: bootstrap run twice against the same Postgres. Row counts in every
table are identical afterwards (only `caselawimportbatch` grows, 2 → 4), so
nothing is duplicated — the cost is time on a job with a 20-minute deploy
ceiling, over an Azure Files share, and a report that cannot distinguish "new"
from "already had it". Either make the comment true (return
`{"status": "unchanged"}` unless `force`) or correct the comment and drop the
redundant second pass in production.

Fixed: `ingest_group` returns `"status": "unchanged"` when the scan, OCR text
and sidecars match the stored artifacts' checksums byte for byte (`--force`
still re-imports), and the report has an `unchanged` bucket. Verified in the
rig: a fresh database imports 665 on the first pass and the second reports
**665 unchanged**. Tests: `apps.caselaw.tests` (`test_an_unchanged_corpus_is_not_reimported`,
which also checks a correction made since import survives).

### F4 (high, fixed) — after every cold start, gunicorn workers share one Postgres socket

`backend/config/wsgi.py` drives a warm-up request through the app at import
time, and `docker/web.sh` runs gunicorn with `--preload`, so that request runs
in the master. The first request in any process fires
`apps/templates_app/signals.py:sync_on_first_request`, which syncs prepared
templates — opening (and writing through) a database connection. With
`CONN_MAX_AGE=60` the connection stays open, and every forked worker inherits
it. Three processes then share one Postgres socket and read each other's
results.

Seen first as a 500 on the very first sign-in against the rig
(`psycopg.ProgrammingError: the last operation didn't produce records (command
status: COMMIT)`). Reproduced on demand: restart the API container, sign in,
fire 60 concurrent `GET /api/auth/me/`:

| | 200 | 500 | 504 |
|---|---|---|---|
| Image as built (3 runs) | 42 / 44 / 41 | 16 / 14 / 17 | 2 / 2 / 2 |
| With the fix (3 runs) | 60 / 60 / 60 | 0 | 0 |

With `/api/cases/` instead, one run returned 49 × **401** to a signed-in user:
the session lookup read another worker's result and came back empty. Production
scales to zero, so every cold start is exposed; a result read by the wrong
process is also, in principle, one user's row answering another's query.

Fixed: `connections.close_all()` after the warm-up in `config/wsgi.py`.
Regression test: `apps.core.tests.PreloadWarmupTests` (fails without the fix).
The warm-up also means every replica's master writes to the database on start,
contrary to `web.sh`'s "nothing here writes to the database"; that is
harmless now but worth knowing.

### F5 (high, fixed) — draft generation over 60 s fails as "Failed to fetch" while the draft is created anyway

`POST /api/drafting-sessions/<id>/drafts/` runs the model inline. `nginx.conf`
sets no `proxy_read_timeout`, so nginx's 60 s default is the real ceiling —
not gunicorn's `--timeout 120`, which is the number everything else is sized
against. Past 60 s nginx answers 504 with no CORS headers; the browser reports
a CORS failure and the app shows **"Failed to fetch"**. Gunicorn carries on and
commits the draft.

Observed on the existing matrix's *Patricia Taylor → CLE Motion to Dismiss -
Lack of Specificity in 30 Day - Lease Violation* with AI on:

```
nginx    21:04:05  POST /api/drafting-sessions/9/drafts/  504   upstream timed out ... reading response header
gunicorn 17:04:18  POST /api/drafting-sessions/9/drafts/  201   125127 bytes   (75 s after the request)
```

So the advocate sees a failure, the draft exists, and the obvious response —
clicking Generate again — makes a second one. This is the failure AGENTS.md
describes ("never hold a request open for work that runs longer than the worker
timeout"), reached through a timeout nobody set. The existing matrix only ever
ran with `AI_DRAFTING_ENABLED=false`, where the same request returns in seconds.

Fix: move plan-draft generation to the 202-and-poll pattern the argument gym
already uses. Until then, at minimum set `proxy_read_timeout` (and
`proxy_send_timeout`) in `nginx.conf` above gunicorn's timeout so the two agree,
and have nginx attach CORS headers to its own error responses (`add_header ...
always` on a `error_page` location) so a timeout reads as a timeout.

Mitigated: `nginx.conf` now sets `proxy_read_timeout`/`proxy_send_timeout
230s` on `/api/` (under Container Apps' 240 s ingress limit), and with the
threaded workers from F19 gunicorn's `--timeout` no longer bounds a single
request. Still open: generation is synchronous, so a draft slower than ~4
minutes fails the same way, and nginx's error responses still carry no CORS
headers.

After the mitigation the same test passed — and that generation took **161 s**
(`PATCH …/plan/` at 19:14:55, `POST …/drafts/` 201 at 19:17:36), against 75 s
for the same template earlier. Model latency varies by 2× run to run, so 230 s
is headroom, not a guarantee; generation belongs in the background.

Fixed: `POST …/drafts/` now creates a `DraftGenerationJob`, answers **202**
at once, and generates on a background thread (`apps/drafting/generation_jobs.py`,
the argument gym's pattern). The app polls `GET …/drafts/?job=<id>`
(`frontend/src/state/draftJobs.js`). A second POST while a job runs returns the
same job, so a repeat click cannot make a second draft; a job that stops
reporting for 15 minutes is marked failed with a message to retry. Tests:
`apps.drafting.test_generation_jobs`, `frontend/test/draft-jobs.test.js`; the
e2e journey asserts 202. The nginx timeout from the mitigation stays as a
backstop. Block regeneration is still synchronous but short.

### F6 (medium, fixed) — four upload forms throw after a successful save

`event.currentTarget.reset()` was called after an `await` in four submit
handlers. React clears `currentTarget` once a handler yields, so each threw
`Cannot read properties of null (reading 'reset')` after the server had
already saved:

| Form | What the advocate saw |
|---|---|
| Case → New quick case (`CaseSelector.jsx`) | Case created; uncaught exception; form stays open |
| Triage → Upload case docs (`TriagePanel.jsx`) | Same; source toggle never returns to "Existing case" |
| Research → reference upload (`ResearchPanel.jsx`) | **"Reference upload failed"-style error after the upload worked** |
| Draft → Fact review → upload document (`FactReview.jsx`) | **Error shown after the facts were created; dialog stays open, inviting a duplicate upload** |

Found by the new `e2e/cases.spec.js` quick-case journey, whose network guard
fails on any uncaught page error. Fixed by reading the form before the first
`await`. Regression test: `frontend/test/event-after-await.test.js` scans
`src/` and fails on the old code at all four sites.

### F7 (low, fixed) — every case shows "Answer and Counterclaims" as its selected document

On load `App.jsx` pre-selects the `answer-counterclaims-cleveland` template,
and the header pill and sidebar then label it **"Selected document: Answer and
Counterclaims"** on every case — a Medicare matter included — before the
advocate has chosen anything. It reads as though a document is already in
progress. Show the pill only once a template has been chosen or a draft exists.

Fixed: the header and sidebar show a selected document only once the
advocate picks a template (or a suggestion picks one) or a draft exists; the
pre-selected default no longer counts.

### F8 (low, fixed) — internal codename in user-facing text

The argument gym says "Test the brief against the documents already on a
**HaddenDraft** case", and `argument_gym/views.py:526` returns "This brief is
not a HaddenDraft document"; `models.py:148` labels a source type "HaddenDraft
document". The app is branded "Drafting Tool" everywhere else.

Fixed: user-facing text now says "this tool"; the source-type label is
"Draft from this tool" (migration `argument_gym.0004`). Internal docstrings keep
the codename.

### F9 (high, fixed) — a repealed ordinance is invisible; search leads with the stale treatise instead

`content/ordinances` records that Newburgh Heights repealed its pay-to-stay
chapter (Ord. 2024-27) and Chauncey has no provision in force, as
`status: no_current_provision`. The record carries the repeal and a warning
written for exactly this case: *"This repeal post-dates the treatise, which still
describes Newburgh Heights as an ordinance where tender creates a right …
Any advice drawn from that description is now wrong as to current law."*

No reader ever sees it:

- **Library → Local ordinances → Newburgh Heights** shows "0 sections — This
  document has no readable sections." Nothing about a repeal.
- **Search "Newburgh Heights pay to stay"** ranks first the treatise section
  the note says is now wrong, then other cities' pay-to-stay chapters. The
  repeal record produces no chunk, so it cannot be a result.
- `frontend/src` never references `no_current_provision`; only
  `/api/ordinances/coverage/` returns it.

This is the failure AGENTS.md warns about for `pending` — an absent record
reading as "no local law here" — with a worse twist: the one source that does
come back gives the old answer. Fix: render `no_current_provision` sections
(citation, repeal, `notInForceReason`, `notes`) in the library document view,
and index them as a searchable, clearly labelled "not in force" record so a
query about the ordinance returns the repeal alongside the treatise.
`e2e/research.spec.js` has an expected-failure test for the library half.

Fixed: a shared `_section_notice` builds the notice for any pending or
not-in-force section. `GET /api/library/<slug>/` returns `coverageNotices` and
the library shows them (the repeal, its reason, the treatise warning, and where
to confirm), and `POST /api/research/search/` returns `coverageNotices` for a
query naming the municipality, shown above the results. Tests:
`apps.sources.tests.RepealedOrdinanceVisibilityTests`; `e2e/research.spec.js`
now asserts both instead of expecting failure. Writing that test also exposed
a latent `KeyError` in `apps/core/jurisdictions.py` on the first lookup when
the county vocabulary file is absent; fixed, with a test.

### F10 (low, fixed) — the case catalog's "Treatment" facet mixes in non-treatment values

Library → Cases → Treatment lists `unchecked 501`, `reviewed 19`,
`published 12`, `affirmed 11`, `checked 4`, `final 4`, `positive 3`,
`reversed and remanded 3`, `good law 1`, `none 1`, `original 1`. Only some of
those are subsequent treatment; "published", "final", "original" and "none"
are publication or review states, and "reviewed"/"checked"/"unchecked" are
the editorial workflow. Model-read metadata landing in a free-text field, so
the shelf splits. Canonicalize on ingestion as `content/jurisdictions/` does
for counties.

Fixed: `content/caselaw-vocabulary/treatment-status.yaml` groups the values
(unchecked; checked; good law; and "not a treatment value" for dispositions and
publication states — a disposition is deliberately not read as negative
treatment). The catalog groups and filters by it at read time; stored values
are unchanged and an unlisted value keeps its own wording. Marked
`verification: unverified`. Tests: `apps.caselaw.test_treatment_facet`.

### F11 (medium, fixed) — a reload silently switches the active case to a different client

The active case is React state only (`App.jsx:103`), and on load
`applyCaseResponse` activates `incoming[0]` — whichever case sorts first
(`App.jsx:251`). So signing in, reloading, or reopening a tab makes an
arbitrary client's case active without the advocate choosing it. Observed:
Christopher Anderson was active, the page was reloaded, and every screen was
then working against "E2E Quick …", a quick case another test had created.
Chat, triage, drafting, advice letters and the argument gym all use the active
case, and the client's name in the header is the only cue.

Fix: remember the active case per user (server-side, or at least in
`localStorage` keyed by user) and restore it; when there is nothing to
restore, activate nothing and ask, rather than picking the first row.

Fixed: the active case is remembered per user in this browser
(`frontend/src/state/activeCase.js`) and restored after a reload; with nothing
to restore, no case is activated and the Case screen asks. A remembered case
that no longer opens is forgotten. Tests: `frontend/test/active-case.test.js`;
the screen smoke test and `e2e/case-work.spec.js` now assert it.

### F12 (low, fixed) — "Clear" deletes a chat conversation with one click

Case chat's **Clear** sits beside **New chat** and permanently deletes the
current conversation's messages (`DELETE /api/cases/<id>/chat/` →
`clear_messages`) with no confirmation and no undo. It is correctly disabled
while an older thread is being viewed. "New chat" already archives rather than
deletes; Clear could do the same, or ask first.

Fixed: Clear asks first, in both case chat and research chat, and says New
chat keeps the thread instead. `e2e/case-work.spec.js` checks that declining
keeps it.

### F13 (medium, fixed) — an advice letter downloads with a blank phone number and a login as the signature

The letter's closing interpolates the advocate's profile with no check that it
is filled in. With an incomplete profile, the downloaded client letter says
**"If you have questions about the advice in this letter, please call me at: ."**
and is signed **"Sincerely, e2e-browser@example.invalid"** — the account login
standing in for a name. Nothing in the advice-letter panel warns before the
download (`AdviceLetterPanel.jsx` has no profile check). A client letter is
the one document that goes out without an attorney re-reading a filing
around it.

Fix: before download (and before a LegalServer save), list the profile fields
the chosen wrapper uses that are empty, and offer the Profile dialog; never
fall back to the username in a signature.

Fixed: the advice-letter panel lists what the letter would go out missing
(a real name — not empty, not a login or email address — and a phone number)
and holds Download and Save to LegalServer until the advocate fixes the profile
or ticks "Send it without them". New profiles no longer take the login as
their display name. Tests: `frontend/test/adviceLetter.test.js`;
`e2e/advice-letter.spec.js` checks the gate and that a complete profile's name
and number reach the letter.

### F14 (high, fixed) — a deployment built by bootstrap letters on no letterhead at all

`sync_letterheads()` was called only from `prepare_letterhead` and
`build_placeholder_letterhead`, never from `docker/bootstrap.sh` or
`sync_content_library`. After a clean bootstrap the letterhead files were
published but the `Letterhead` table was empty, so every advice letter
downloaded with **no header, no footer and no logo** — plain text starting at
the date — and nothing said so. The README's promise that "a fresh install can
draft and export a letter" on the placeholder did not hold for any deployment
built by the pipeline. (Production may have been hand-fixed by running one of
the commands; a rebuilt environment would not be.)

Verified in the rig: 0 letterheads after bootstrap; the exported letter's
package had no `word/header*.xml`; after `sync_letterheads()` the same export
carried the Cleveland Legal Aid letterhead.

Fixed: `sync_content_library` now calls `sync_letterheads()` (which skips
admin-uploaded records and is a no-op when nothing changed). Tests:
`apps.templates_app.test_letterheads.DeploymentIndexesLetterheadsTests`.
Still open: when no letterhead resolves, the export should say so rather than
silently produce a bare letter; and a staff edit made *in place* on a synced
record keeps `source_kind=content_library`, so a later manifest change would
overwrite it.

### F15 (high, fixed) — for a few seconds after "Make active", every screen acts on the previous client

Clicking **Make active** updated `selectedMatterId` at once — the row showed
*Active* — but the loaded `matter` stayed the previous case until
`GET /api/cases/<id>/` came back from LegalServer (about 3 s in the rig).
Triage, planning and drafting all send `matter.id`, so in that window they
acted on the case just left behind. Found by accident: an exploration script
clicked Make active on Christopher Anderson, opened Draft and made a plan —
and the plan was created for a different client. The triage history, loaded
by `selectedMatterId`, showed the new client while **Run triage** would have
scored the old one.

Fixed in `App.jsx`: the case-detail effect drops a `matter` that is not the
selected one before fetching, so screens show "select a case" until the right
one arrives. Test: `e2e/cases.spec.js` "while a newly active case loads,
nothing acts on the previous one" holds the detail response open; it fails on
the old build (the previous client stays in the header) and passes on the fix.

### F16 (high, fixed) — one answer fills every date in a court filing

The maintained originals write a generic `[DATE]` for every date, and
`apps/templates_app/placeholders.py` binds each one it cannot classify to a
hard-coded `{{ fields.filing_date }}` (`placeholder_expression`, the date
branch's final `return`). A second defect widens it: `context_label` keeps the
words before a blank only if that sentence fragment is ≤ 80 characters, and
**discards** a longer one rather than keeping its tail — so even a sentence
containing "hearing", which has a hint, is classified with no context at all.

Result in **CLE Emergency Motion for Heat**: the plan's questions ask *"What
date was the eviction case filed?"*, and that one answer is printed as

- the first-cause **hearing** date ("set for a first cause hearing … on ____ at [Time]"),
- the **filing** date ("Plaintiff filed the instant action on ____"),
- the **move-in** date ("Defendant has lived in the premises … since ____"),
- the date the **heat went out** ("without heat in the premises since at least ____").

Found by reading the questions the drafting UI asked for this template; the
original DOCX (`private-content/original_templates/CLE Emergency Motion for
Heat.docx`) has four separate `[DATE]` blanks. Converter reproduction:

```
This matter is … hearing on the virtual general call docket on {{ fields.filing_date }} at {{ fields.time }}.
Defendant has lived in the premises with {{ fields.describe_occupants }} since {{ fields.filing_date }}.
Defendant has been without heat in the premises since at least {{ fields.filing_date }}, if not longer.
```

`filing_date` recurs across the prepared templates — 9 uses in *CMHA Admin
Appeal – Motion for Stay* (decision date, effective date, informal-hearing
date, "HCVP participant since", CMHA service date…), 5 in *CLE Payment Plan
AJE*, 4 in the *Motion to Dismiss – Lack of Specificity* and *Notice of
Administrative Appeal*, 3 in both *Motion to Bench* templates.

A generated motion with every date the same is wrong on its face, and the
failure is quiet: each question looks sensible, and an advocate who answers it
correctly still gets a wrong filing. Existing tests lock the behaviour in
(`tests.py` expects "Served on … [DATE]" → `filing_date`).

Not fixed here, because the fix changes the prepared private templates and
the questions they ask, which need review: keep the tail of a long sentence in
`context_label`; for an unclassified date, derive the field from its own
sentence (as blanks already are) instead of defaulting to `filing_date`; then
re-prepare the templates and re-read each one's questions. Expected-failure
tests: `apps.templates_app.tests.DistinctDatesStayDistinctTests`.

Fixed in `apps/templates_app/placeholders.py`, for dates only (every other
kind of fill-in converts exactly as before — checked by regenerating all 17
templates and comparing their variable sequences):

- a long sentence keeps the words nearest the blank instead of being discarded,
  and an already-converted `{{ fields.x }}` reads as its name rather than
  splitting the sentence at its dots;
- an explicitly labelled date (`[Hearing Date]`) keeps its own name;
- "was held on" is a prior hearing, "…general call docket on" is the hearing;
- an unclassified `[DATE]` is named from its own sentence, or from the words
  after it when it opens the sentence ("On [DATE], CMHA issued a decision…"),
  or `document_date` when it stands alone on a letter's date line.

The 11 affected templates were regenerated with `ingest_document_templates`
(in the `private-content` submodule, uncommitted); every changed line is a date
getting its own name. The heat motion now asks separately for the filing date,
the prior hearing, the upcoming hearing (date and time), the move-in date and
the date the heat went out. Trade-off: a date referred to twice in different
wording may be asked for twice, which is safe where one answer filling
different dates was not. `field_questions.py` gains questions for the new
common fields. Tests: `apps.templates_app.tests.DistinctDatesStayDistinctTests`
(no longer expected failures), plus the corrected "Served on … [DATE]" →
`service_date`.

### F17 (high, fixed) — the tool's own drafts and chat transcripts come back as "facts" in the next filing

Saving to LegalServer is on by default for documents, and chat transcripts can
be saved as case notes. Both then reappear in the case materials exactly like
the client's evidence, and fact recommendation draws on them. On Christopher
Anderson (26-0000085) the case file now holds four *CLE Emergency Motion for
Heat* DOCX files, a *Client advice letter*, three *AI usage audit* notes and a
*Case chat: …* note, all written by this tool. A new Emergency Motion for Heat
drafted in the rig had one recommended fact, sourced **"Case document: CLE
Emergency Motion for Heat, excerpt 2"** — an earlier generated motion — and
its **Relevant Facts** section, the part a court reads as the client's facts,
said verbatim:

> 1. Christopher Anderson and their family from their residence at [Premises
> Address], the premises at issue in this case. … AI: I found these case
> documents: Gas_Company_Inspection_Report.txt [LegalServer case note: Case
> chat: LS write validation 1786504307236: summarize the documented lack of
> heat in one sentence., 26-0000085, [Case document:... [Case document: CLE
> Emergency Motion for Heat, excerpt 2]

That is an unfilled placeholder from the old draft, a chat reply, and a
citation to the tool's own work product presented as a source of fact. The
editor then flags the citation's bracket text as **"Missing: Case document:…"**,
as though it were a template blank. The loop compounds: each saved draft feeds
the next.

The live-write e2e spec created these particular artifacts on the demo site,
but they are exactly what the default "save a copy to the LegalServer case
file" produces in production.

Fix: `LegalServerDelivery` already records every note and document this tool
wrote, with remote ids. Exclude those from fact recommendation and label them
as work product in the case-materials view (they are still worth reading).
`e2e/drafting.spec.js` asserts no recommended fact is sourced from the tool's
own output, and is marked expected-to-fail where such output exists.

Fixed: `apps/matters/work_product.py` marks what this tool wrote, by
`LegalServerDelivery` record (remote id or title) and by the titles it gives
its own notes and documents, since a case file also holds what other
deployments wrote. Case materials carry `workProduct` and the UI labels it
"Written by this tool · not used as a source of fact". Fact recommendation and
the argument gym's case record exclude it. Facts already created from work
product before this fix remain on their cases. The re-run then showed triage
citing "Summary of CLE Emergency Motion for Heat…" as evidence: triage
flattens the raw LegalServer payload, notes included, so the tool's AI-usage
audit note reached it. `matter_triage_text` now drops the tool's own notes
(`without_work_product_notes`). Tests: `apps.matters.test_work_product`
(including triage); `e2e/drafting.spec.js` asserts the fact-recommendation
side.

### F18 (medium, fixed) — "Let AI suggest template(s)" recommended by alphabet

The button is labelled AI, but `recommend_templates`
(`apps/templates_app/recommendations.py`) is a deterministic keyword overlap —
and it counted stopwords. Every prepared template's goal is the same generated
sentence ("Draft the <title> filing with case-specific facts, legal grounds,
and requested relief"), so a goal containing "the", "facts" or "relief" matched
every template equally, and ties break by title. For *"The landlord shut off
the heat in January; get it restored now."* the Emergency Motion for Heat
(matched on "heat") and the Affidavit (matched on "the") both scored 8, and the
plan recommended **Affidavit** — every time, as the only document. No template
has `aliases` configured, which is the signal meant to carry this.

Fixed: goal matching ignores stopwords and the generated boilerplate. Tests:
`apps.templates_app.tests.TemplateRecommendationTests` (both fail on the old
code); `e2e/drafting.spec.js` "the AI recommends a template for a goal" now
passes against the rig. Still open: the control says "AI" for a ranking no
model takes part in — AGENTS.md asks every response to say in words what a
model did — and the templates should be given aliases.

### F19 (medium, fixed) — three advocates waiting on the model stall everyone else

`docker/web.sh` ran gunicorn with 3 single-threaded sync workers per replica.
Model-backed requests hold a worker for their whole duration (research 7 s,
plans ~20 s, draft generation up to 75 s), so three concurrent ones leave no
worker for anything else. Measured in the rig: `GET /api/auth/me/` took 13 ms
idle and **3.8 s** while three 7 s research answers were in flight. With plan
or draft generation in flight the queue wait is 20–75 s, and past nginx's 60 s
it becomes a 504 — another "Failed to fetch" (see F5). Container Apps' default
HTTP scale rule (10 concurrent requests) does not add a replica at 3.

Fixed: `--threads "${GUNICORN_THREADS:-4}"` (gthread workers). Same load,
same request: 7–15 ms. The cold-start burst from F4 is still 60/60, and the
full browser suite was re-run against the threaded server. Mind the
database: each thread can hold a connection for `CONN_MAX_AGE`, so workers ×
threads × max replicas (3 × 4 × 3 = 36) must stay under the Postgres server's
`max_connections` (50 on the smallest Azure flexible tier).

### F20 (high, fixed) — when LegalServer rate-limits, the case file silently reads as empty

`get_case_documents` (`apps/matters/document_context.py:249-256`) fetches a
case's documents from LegalServer on every request and treats a
`LegalServerError` as "try the next identifier", then as "no documents". When
LegalServer answers **429 "Request rate limit exceeded"**, the API returns
200 with `documentCount: 0`, logs nothing, and the case preview says **"No
case documents were returned."** Fact recommendation, case chat and drafting
all read the same list, so they proceed as though the client's file were empty.

Found when `e2e/cases.spec.js` "a case document opens in the in-app preview"
failed on a fresh deployment (the dialog showed *Documents (0)* for a case with
22). Reproduced with six concurrent loads of Christopher Anderson's materials:

```
round 1  22 22 22 22 22 22
round 4  22 22  0 22  0  0
```

and confirmed by temporarily logging the swallowed exception:
`LegalServer request failed with status 429: Request rate limit exceeded`.

Two things make the limit easy to hit:

- **Nothing is cached.** `raw_payload` never keeps the document list, so every
  preview, materials load and fact recommendation refetches it.
- **Every fetch starts with a guaranteed 404.** `_legalserver_identifiers`
  yields the case number first, and the documents endpoint answers
  `404 Matter not found` for it every time; only the UUID works. Each load
  costs two LegalServer calls.

Fix: distinguish "could not fetch" from "none" all the way to the screen
(AGENTS.md: "could not run" and "ran and found nothing" are different states);
log the failure; try the UUID first; cache the document list per matter with a
short TTL; back off on 429.

Fixed: `get_case_documents_with_status` reports why a list may be
incomplete; materials and documents responses carry `documentsUnavailable`, and
the case preview and fact review show it instead of "No case documents were
returned". The failure is logged. Documents are fetched by UUID first (no
guaranteed 404), cached per process for `LEGALSERVER_DOCUMENT_CACHE_SECONDS`
(120), and on failure the last good list is shown and labelled as such. Tests:
`apps.matters.tests` (all three fail on the old code).

### F21 (high, fixed) — updated private content never reached production

`copy_area` (`apps/core/storage.py`), which `publish_private_content` and
`publish_local_ordinances` use in every bootstrap, skipped any object whose key
already existed in `published/` — without comparing content — and bootstrap
never passes `--overwrite`. So a changed file uploaded to `raw/` (a regenerated
template, a replaced letterhead, an edited advice-letter catalog) was reported
"skipped … already present" on every deploy while production kept serving the
old one. Found while deploying the F16 fix: the regenerated templates were in
`raw/` and the rig still served the old ones.

Fixed: an object is skipped only when the destination holds identical content
(SHA-256; the filesystem store hashes in place, others stream). Verified in the
rig over a `published/` area from an earlier deploy: `Published 122 object(s),
skipped 1427 already present`, and the live heat-motion template carries
`prior_hearing_date`. Tests: `apps.core.test_storage_publish` (two of three
fail on the old code).

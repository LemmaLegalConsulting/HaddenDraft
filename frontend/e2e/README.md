# Browser end-to-end checks

## Against a production-shaped deployment

The feature journeys below run against any deployment, but they were written
to run against one shaped like production, because several production faults
exist only there: the app and the API on separate HTTPS origins, a
parent-domain CSRF cookie, `DJANGO_DEBUG=false`, Postgres, gunicorn
`--preload` behind nginx, and content published by `docker/bootstrap.sh`.
`scripts/e2e_production_rig.sh` builds exactly that locally, with Docker:

```bash
scripts/e2e_production_rig.sh up            # image from HEAD, Postgres, bootstrap, API, TLS edge
export E2E_LEGALSERVER_IDENTIFIER=your-legalserver-login
eval "$(scripts/e2e_production_rig.sh env)"
npm --prefix frontend run test:e2e          # every spec below
scripts/e2e_production_rig.sh spa           # after a frontend change: rebuild only the app
scripts/e2e_production_rig.sh down
```

The rig serves `https://app.cle.test:8443` and `https://api.cle.test:8443` from
Caddy's internal CA; the env output maps `*.cle.test` to loopback for Chromium
(`E2E_HOST_RESOLVER_RULES`) and for Playwright's Node side
(`e2e/support/dns-map.cjs`), and accepts the private certificate
(`E2E_IGNORE_HTTPS_ERRORS`). AI is on, as in production, so model-backed steps
wait up to `E2E_MODEL_TIMEOUT_MS` (default 180 s).

| Spec | Covers |
|---|---|
| `platform.spec.js` | SPA fallback, missing assets, sign-in errors, cross-origin session and CSRF (including a forged request being refused), profile, admin link, sign-out |
| `cases.spec.js` | Case list paging, search, filters, case preview, framed PDF preview (`frame-ancestors`), document excerpts, quick cases, and the active case never lagging behind "Make active" |
| `case-work.spec.js` | Triage with its stated LegalServer outcome; case chat answers, persistence across reloads, clearing |
| `research.spec.js` | Deterministic search and its "No AI" statement, facets, citations, unmatched phrases, case catalog and scans, every library document, ordinance coverage, cited Q&A |
| `advice-letter.spec.js` | Sections and review reasons, a letter downloaded with its maintained wording and letterhead, AI section suggestions |
| `drafting.spec.js` | Plan → blanks → generate → human edit → validate → history → Word export carrying the edit; AI refinement of one section; AI goal and template suggestions |
| `argument-gym.spec.js` | Upload, background run (202 + poll), challenges and dispositions, artifacts, checklists, courts and rules |

Every journey runs under `guardNetwork`, which fails the test on any 5xx, any
request that got no response, and any uncaught page error — in the split
deployment a server error arrives without CORS headers and the app can only
say "Failed to fetch", so the screen alone cannot be trusted. API assertions
go through the page (`apiCall`), so they exercise CORS and CSRF too.

`docs/e2e-findings-2026-09-23.md` records what the first run of these journeys
found and how each finding was fixed. To document a new, unfixed bug, mark
its test `test.fail` with the finding's number: it passes while the bug exists
and fails once it is fixed, as a prompt to remove the marker.

## LegalServer case matrix

The Playwright matrix uses the application's ordinary login, LegalServer case
search, live case-material endpoints, planning UI, document generation, and
validation UI. It is intentionally read-only in LegalServer: the configured
backend command forces `LEGALSERVER_ALLOW_WRITES=false`, and no test invokes a
save-to-LegalServer action.

Create a dedicated local Django user outside source control, then run:

```bash
.venv/bin/python backend/manage.py shell -c "from django.contrib.auth import get_user_model; u,_=get_user_model().objects.get_or_create(username='e2e-browser', defaults={'email':'e2e-browser@example.invalid','is_staff':True,'is_superuser':True}); u.set_password('choose-a-local-secret'); u.is_staff=True; u.is_superuser=True; u.save()"
E2E_USERNAME=e2e-browser E2E_PASSWORD=choose-a-local-secret E2E_LEGALSERVER_IDENTIFIER=your-legalserver-login npm --prefix frontend run test:e2e
```

The current matrix samples nonpayment with conditions, subsidized-rent
accounting, pending rental assistance, an allegedly vague 30-day notice, and an
emergency heat case. A separate journey checks the live note/document inventory
for eleven housing sample matters. The journeys also verify that source-cited
fact suggestions reach fact-drafting sections, that validation completes, and
that spreadsheet templates download as native `.xlsx` workbooks rather than
empty Word documents. Update the expected minimum counts only when the
intentional sample corpus changes.

## Live LegalServer writes

The live-write spec is skipped unless writes and one exact demo target are
explicitly supplied. It creates and updates one scoped chat note, then uploads
one generated document and its AI-audit note. Allow for up to six write
requests: browsers can retry the export download, and the document/audit writes
are deliberately idempotent for that reason. The expected result is three
remote artifacts, not six. Use only a non-production LegalServer site:

```bash
E2E_ALLOW_LEGALSERVER_WRITES=1 \
E2E_USERNAME=e2e-browser \
E2E_PASSWORD=choose-a-local-secret \
E2E_LEGALSERVER_IDENTIFIER=your-legalserver-login \
E2E_WRITE_CASE_NUMBER=26-0000085 \
E2E_WRITE_CLIENT_NAME="Christopher Anderson" \
npm --prefix frontend run test:e2e -- e2e/legalserver-live-write.spec.js
```

The test reads the case file after each write phase and checks the remote note
body, document inventory, and AI-audit note. Do not run it against production.

# Browser end-to-end checks

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

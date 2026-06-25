# LegalServer permission mapping

LegalServer APIs authenticate as a LegalServer user, not as the application's signed-in Office365 user. LegalServer supports Bearer token and Basic authentication for API calls. The token or username/password represents the underlying LegalServer API user and has that user's permissions.

LegalServer recommends creating a separate API user and a separate API Access user role for each integration, granting only the API permissions needed for that integration. Administrator accounts with API access are disfavored. This application should therefore be configured with the narrowest LegalServer API account that can support the intended workflow.

Because LegalServer API calls do not enforce SSO requirements, this application must explicitly map the signed-in Office365/Django user to a LegalServer identity and enforce app-side permission boundaries.

## Access levels

The app derives a LegalServer access profile for each signed-in user.

- Django staff, Django superusers, and users in configured `LEGALSERVER_SUPERUSER_GROUPS` are treated as application superusers and may access anything the configured LegalServer API user can access.
- LegalServer users whose API profile contains a configured `LEGALSERVER_SUPERUSER_ROLES` value are also treated as superusers.
- Regular users must have a LegalServer identity mapping and, by default, that mapping must match the Office365 or Django login email.
- Regular users are additionally constrained to matters whose assignment fields match their LegalServer identifier, even if the LegalServer API user can see more.

## LegalServer API authentication

Set `LEGALSERVER_BASE_URL` and one of the following credential options:

- Preferred: `LEGALSERVER_API_TOKEN` for Bearer token authentication.
- Alternative: `LEGALSERVER_API_USERNAME` and `LEGALSERVER_API_PASSWORD` for Basic authentication.

Bearer token authentication is preferred because credentials stay in the `Authorization` header and are not sent in query strings. Basic authentication is supported for deployments that do not use personal access tokens.

## Office365 default mapping

When `LEGALSERVER_AUTO_MAP_OFFICE365_EMAIL=true`, Office365 sign-in creates a LegalServer identity mapping from the Office365 email if the user does not already have one. Existing manual mappings are not overwritten.

Set `LEGALSERVER_AUTO_MAP_OFFICE365_EMAIL=false` for deployments where LegalServer identifiers do not match Office365 emails. Administrators can also disable or edit individual mappings in Django admin under User source identities.

## Configurable LegalServer API shape

The defaults assume conventional endpoints and payloads, but deployments may differ.

- `LEGALSERVER_MATTERS_PATH` defaults to `/api/v1/matters`.
- `LEGALSERVER_MATTER_DOCUMENTS_PATH` defaults to `/api/v1/matters/{matter_id}/documents`.
- `LEGALSERVER_USERS_PATH` defaults to `/api/v1/users`.
- `LEGALSERVER_USER_FILTER_PARAM` defaults to `assigned_user_email`.

If the users endpoint is unavailable or not included in the API user's permissions, regular users can still proceed when the saved LegalServer identifier matches the signed-in email. LegalServer role-based elevation requires a reachable users endpoint or a Django-side superuser group/staff assignment.

## Premium API note

Search and get operations are available outside the Premium API set. Creating or updating matters, events, timeslips, or clinics usually requires Premium API access, so this prototype's read/search workflow should stay separate from any future writeback integration.

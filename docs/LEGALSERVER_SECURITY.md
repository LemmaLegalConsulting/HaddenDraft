# LegalServer permission mapping

LegalServer does not provide per-user OAuth in this prototype. The application therefore connects to LegalServer with a server-side API credential and then narrows access back down to the signed-in application user.

## Access levels

The app derives a LegalServer access profile for each signed-in user.

- Django staff, Django superusers, and users in configured `LEGALSERVER_SUPERUSER_GROUPS` are treated as application superusers and may access anything the LegalServer API credential can access.
- LegalServer users whose API profile contains a configured `LEGALSERVER_SUPERUSER_ROLES` value are also treated as superusers.
- Regular users must have a LegalServer identity mapping and, by default, that mapping must match the Office365 or Django login email.
- Regular users are additionally constrained to matters whose assignment fields match their LegalServer identifier.

## Office365 default mapping

When `LEGALSERVER_AUTO_MAP_OFFICE365_EMAIL=true`, Office365 sign-in creates a LegalServer identity mapping from the Office365 email if the user does not already have one. Existing manual mappings are not overwritten.

Set `LEGALSERVER_AUTO_MAP_OFFICE365_EMAIL=false` for deployments where LegalServer identifiers do not match Office365 emails. Administrators can also disable or edit individual mappings in Django admin under User source identities.

## Configurable LegalServer API shape

The defaults assume conventional endpoints and payloads, but deployments may differ.

- `LEGALSERVER_MATTERS_PATH` defaults to `/api/v1/matters`.
- `LEGALSERVER_MATTER_DOCUMENTS_PATH` defaults to `/api/v1/matters/{matter_id}/documents`.
- `LEGALSERVER_USERS_PATH` defaults to `/api/v1/users`.
- `LEGALSERVER_USER_FILTER_PARAM` defaults to `assigned_user_email`.

If the users endpoint is unavailable, regular users can still proceed when the saved LegalServer identifier matches the signed-in email. LegalServer role-based elevation requires a reachable users endpoint or a Django-side superuser group/staff assignment.

/**
 * Clearing a CSRF cookie left behind by the previous topology.
 *
 * The app used to be served from the same host as the API, and Django set its
 * `csrftoken` cookie *host-only* for that hostname. The API now lives on a
 * sibling subdomain and scopes the cookie to the parent domain instead, so a
 * browser that used the old site is holding two cookies of the same name with
 * different scopes.
 *
 * Only one of them is real. The browser sends the parent-domain one to the API,
 * because a host-only cookie for the app's hostname does not match the API's.
 * But `document.cookie` shows both, and reading a cookie by name returns
 * whichever the browser lists first — the older one, in practice. The app then
 * sends a header token that does not match the cookie the API received, and
 * Django rejects the write with a 403.
 *
 * That fails in a nasty shape: reads all work, writes all fail, and it only
 * affects people who used the site before the move. Clearing cookies fixes it,
 * which is not something to ask of everyone.
 *
 * So drop the stale one on the way in. This is only correct when the API is on
 * another origin: then the app's own hostname has no business holding a
 * `csrftoken` at all, and any it does hold can only be left over. Same-origin,
 * that cookie is the live one and must not be touched.
 */

/** Whether API calls leave the origin the page was served from. */
export function apiIsCrossOrigin(apiBase, pageOrigin) {
  try {
    return new URL(apiBase, pageOrigin).origin !== new URL(pageOrigin).origin;
  } catch {
    return false;
  }
}

/**
 * Expire any host-only `csrftoken` on the page's own origin.
 *
 * Deleting a cookie requires matching its name, path and domain. Writing one
 * with no `Domain` attribute therefore targets the host-only cookie precisely
 * and leaves the parent-domain cookie -- a different cookie -- alone. If no
 * stale cookie exists this writes an already-expired one, which is a no-op.
 *
 * Returns whether it acted, for the test to assert on.
 */
export function clearStaleCsrfCookie({
  apiBase,
  pageOrigin,
  cookieName = "csrftoken",
  cookieStore = typeof document === "undefined" ? null : document,
} = {}) {
  if (!cookieStore) return false;
  if (!apiIsCrossOrigin(apiBase, pageOrigin)) return false;
  cookieStore.cookie = `${cookieName}=; Max-Age=0; Path=/; SameSite=Lax`;
  return true;
}

/**
 * Where the API lives, which is not always where the page came from.
 *
 * Same-origin deployments serve the app and the API from one host and every
 * path can be relative. The split deployment serves the built app from a static
 * host that is warm even when the API's container is asleep, so the API is on a
 * sibling subdomain and anything that is not routed through `API_BASE` has to
 * be resolved against it explicitly — a bare path would address the static
 * host, which has no Django on it.
 */

/** The Django admin, which is served by the API rather than by the app host. */
export function adminUrlFrom(apiBase, pageOrigin) {
  return new URL("../admin/", new URL(apiBase, pageOrigin)).href;
}

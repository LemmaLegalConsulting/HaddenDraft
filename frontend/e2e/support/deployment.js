import { expect, test } from "@playwright/test";

// Shared plumbing for the journeys that run against a real deployment: a
// production-shaped rig (e2e/README.md), a staging host, or the dev servers.

export const credentials = {
  username: process.env.E2E_USERNAME,
  password: process.env.E2E_PASSWORD,
  legalserverIdentifier: process.env.E2E_LEGALSERVER_IDENTIFIER,
};

// Planning, generation, triage and chat call the model when AI is enabled, as
// it is in production. With AI off the same requests answer in a second or two.
export const modelTimeout = Number(process.env.E2E_MODEL_TIMEOUT_MS || 180_000);

export function requireCredentials() {
  test.skip(
    !credentials.username || !credentials.password || !credentials.legalserverIdentifier,
    "Set E2E_USERNAME, E2E_PASSWORD, and E2E_LEGALSERVER_IDENTIFIER for a dedicated test user.",
  );
}

// Everything the browser saw go wrong while a test ran. A 5xx, a request that
// never got a response, and an uncaught exception each fail the test that
// caused them, even when the screen happens to look fine: in the split
// deployment a server error arrives without CORS headers, so the app shows only
// "Failed to fetch" and the real cause is invisible unless something records it.
export function guardNetwork(page, { allowStatuses = [] } = {}) {
  const problems = [];
  page.on("pageerror", (error) => problems.push(`uncaught: ${error.message}`));
  page.on("response", (response) => {
    const status = response.status();
    if (status >= 500 && !allowStatuses.includes(status)) {
      problems.push(`HTTP ${status} ${response.request().method()} ${response.url()}`);
    }
  });
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText || "";
    // A download the browser hands off, and a request a navigation superseded,
    // both end as ERR_ABORTED without anything having gone wrong.
    if (/ERR_ABORTED|NS_BINDING_ABORTED/.test(reason)) return;
    problems.push(`no response: ${request.method()} ${request.url()} (${reason})`);
  });
  return {
    problems,
    assertClean() {
      expect(problems, "network and page errors seen during the test").toEqual([]);
    },
  };
}

// Calls the API from inside the page, exactly as the app does: same origin
// rules, same cookies, same CSRF header read from document.cookie. On the split
// deployment that makes every API assertion also a check that CORS and the
// parent-domain CSRF cookie work, which a Node-side request would skip.
export async function apiCall(page, method, path, body) {
  // Same-origin by default; on the split deployment the API is a sibling host.
  const base = process.env.E2E_API_BASE || "/api";
  return page.evaluate(
    async ({ method, url, body }) => {
      const csrf = document.cookie
        .split("; ")
        .find((item) => item.startsWith("csrftoken="))
        ?.split("=")
        .slice(1)
        .join("=");
      const unsafe = !["GET", "HEAD"].includes(method);
      const response = await fetch(url, {
        method,
        credentials: "include",
        headers: {
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...(unsafe && csrf ? { "X-CSRFToken": decodeURIComponent(csrf) } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
      const type = response.headers.get("content-type") || "";
      const headers = Object.fromEntries(response.headers.entries());
      const data = type.includes("application/json") ? await response.json() : await response.text();
      return { status: response.status, ok: response.ok, headers, data };
    },
    { method, url: `${base}${path}`, body },
  );
}

export async function signIn(page) {
  requireCredentials();
  await page.goto("/");
  await page.getByLabel("Username").fill(credentials.username);
  await page.getByLabel("Secret").fill(credentials.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Cases" })).toBeVisible();
  const account = await apiCall(page, "GET", "/legalserver/account/");
  expect(account.status, "read the LegalServer account").toBe(200);
  if (!account.data.legalserver?.connected) {
    const connected = await apiCall(page, "POST", "/legalserver/account/", {
      identifier: credentials.legalserverIdentifier,
    });
    expect(connected.ok, `connect the test user to LegalServer: ${JSON.stringify(connected.data)}`).toBeTruthy();
    await page.reload();
  }
  await expect(page.getByLabel("Search LegalServer matters")).toBeVisible();
}

export async function selectCase(page, { caseNumber, client }) {
  await page.locator("nav.mode-list button", { hasText: "Case" }).click();
  await page.getByLabel("Search LegalServer matters").fill(caseNumber);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: caseNumber }).filter({ hasText: client });
  await expect(row).toBeVisible();
  const activate = row.getByRole("button", { name: "Make active" });
  if (await activate.count()) await activate.click();
  await expect(page.locator(".topbar-case")).toContainText(caseNumber);
}

export async function openScreen(page, name) {
  await page.locator("nav.mode-list button", { hasText: name }).first().click();
}

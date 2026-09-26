import { expect, test } from "@playwright/test";

import { apiCall, guardNetwork, openScreen, selectCase, signIn } from "./support/deployment.js";

// The case list, the case file behind each case, and quick cases. Read-only in
// LegalServer; a quick case is local to this deployment.

const HEAT_CASE = { caseNumber: "26-0000085", client: "Christopher Anderson" };

test.describe("case list", () => {
  test("lists LegalServer cases and pages through them", async ({ page }) => {
    const guard = guardNetwork(page);
    await signIn(page);
    const rows = page.getByRole("table", { name: "Cases" }).getByRole("row");
    await expect(rows.nth(1)).toBeVisible();
    const firstPage = await rows.count();

    const more = page.getByRole("button", { name: /^Show \d+ more$/ });
    if (await more.count()) {
      await more.click();
      await expect.poll(() => rows.count()).toBeGreaterThan(firstPage);
    }
    guard.assertClean();
  });

  test("search finds a case by number and makes it active", async ({ page }) => {
    const guard = guardNetwork(page);
    await signIn(page);
    await selectCase(page, HEAT_CASE);
    await expect(page.locator(".topbar-case")).toContainText(HEAT_CASE.client);
    // Every other screen works against the active case, so it has to survive
    // moving between them.
    await openScreen(page, "Chat");
    await expect(page.locator(".topbar-case")).toContainText(HEAT_CASE.caseNumber);
    guard.assertClean();
  });

  test("while a newly active case loads, nothing acts on the previous one", async ({ page }) => {
    // The case detail comes from LegalServer and takes seconds. Every screen
    // acts on the loaded case, so if the previous one lingers while the next
    // loads, "Make active" then "Make plan" drafts for the client just left.
    // Holding the response open makes the window as wide as a slow LegalServer.
    const guard = guardNetwork(page);
    await signIn(page);
    const other = { caseNumber: "26-0000084", client: "Patricia Taylor" };
    await selectCase(page, other);

    let release;
    const held = new Promise((resolve) => { release = resolve; });
    // The case opens through the route-key lookup the URL drives.
    const caseLookup = (url) => url.pathname.endsWith("/cases/by-route-key/") && url.searchParams.get("key") === HEAT_CASE.caseNumber;
    await page.route(caseLookup, async (route) => {
      if (route.request().method() === "GET") await held;
      await route.continue();
    });
    await page.getByLabel("Search LegalServer matters").fill(HEAT_CASE.caseNumber);
    await page.getByRole("button", { name: "Search", exact: true }).click();
    const row = page.getByRole("row").filter({ hasText: HEAT_CASE.caseNumber });
    await row.getByRole("button", { name: "Make active" }).click();

    await expect(page.locator(".topbar-case", { hasText: other.client })).toHaveCount(0);
    // With no case loaded the draft screen must not offer to plan at all.
    await openScreen(page, "Draft");
    const makePlan = page.getByRole("button", { name: "Make plan" });
    if (await makePlan.count()) await expect(makePlan).toBeDisabled();

    release();
    await expect(page.locator(".topbar-case")).toContainText(HEAT_CASE.client);
    guard.assertClean();
  });

  test("filters narrow the list and reset restores it", async ({ page }) => {
    const guard = guardNetwork(page);
    await signIn(page);
    await page.getByRole("button", { name: /Filter/ }).click();
    const problem = page.locator("#case-filter-panel label", { hasText: "Legal problem" }).locator("select");
    const options = await problem.locator("option").allTextContents();
    const landlordTenant = options.find((option) => /Landlord\/Tenant/i.test(option));
    test.skip(!landlordTenant, "no landlord/tenant problem code in this LegalServer site");
    const filtered = page.waitForResponse((response) => /\/cases\/\?.*problem=/.test(response.url()));
    await problem.selectOption({ label: landlordTenant });
    await filtered;
    const rows = page.getByRole("table", { name: "Cases" }).getByRole("row");
    await expect(rows.nth(1)).toBeVisible();
    const problems = await page.getByRole("table", { name: "Cases" }).getByRole("row").allInnerTexts();
    for (const row of problems.slice(1)) expect(row).toMatch(/Landlord\/Tenant/i);

    await page.getByRole("button", { name: "Reset search and filters" }).click();
    await expect(rows.nth(1)).toBeVisible();
    guard.assertClean();
  });
});

test.describe("case file", () => {
  test("the case preview shows the LegalServer notes and documents", async ({ page }) => {
    const guard = guardNetwork(page);
    await signIn(page);
    await selectCase(page, HEAT_CASE);
    await page.locator(".topbar-case-preview").click();
    const dialog = page.getByRole("dialog").first();
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(HEAT_CASE.client);
    await expect(dialog.getByText(/Loading case notes and documents/)).toHaveCount(0, { timeout: 60_000 });
    await expect(dialog.locator(".support-tabs button", { hasText: /Documents/ })).toBeVisible();
    guard.assertClean();
  });

  test("a case document opens in the in-app preview", async ({ page }) => {
    // The preview is an iframe of the API's file endpoint, which on the split
    // deployment is another origin. It needs the session cookie sent with a
    // cross-origin frame request and a frame-ancestors policy naming the app;
    // either one missing shows a blank frame and no error anywhere.
    const guard = guardNetwork(page);
    await signIn(page);
    await selectCase(page, HEAT_CASE);
    const materials = await apiCall(page, "GET", `/cases/${HEAT_CASE.caseNumber}/materials/`);
    expect(materials.status).toBe(200);
    const pdf = materials.data.documents.find((item) => item.hasFile && /pdf/i.test(`${item.mimeType || ""} ${item.filename || ""}`));
    // The sample case is known to hold one. A skip here would read as a pass;
    // if LegalServer could not be asked, say that rather than "no PDF".
    expect(materials.data.documentsUnavailable, "LegalServer returned the case's documents").toBe("");
    expect(pdf, "the sample case should hold a PDF with a file").toBeTruthy();

    await page.locator(".topbar-case-preview").click();
    const dialog = page.getByRole("dialog").first();
    await dialog.locator(".support-tabs button", { hasText: /Documents/ }).click();
    const fileResponse = page.waitForResponse((response) => /\/documents\/[^/]+\/file\/$/.test(new URL(response.url()).pathname));
    await dialog.getByRole("button", { name: /Preview PDF/ }).first().click();
    const response = await fileResponse;
    expect(response.status()).toBe(200);
    const headers = response.headers();
    expect(headers["content-type"]).toMatch(/pdf/);
    const appOrigin = new URL(page.url()).origin;
    const policy = headers["content-security-policy"] || "";
    expect(policy, "the file must be allowed to be framed by the app").toMatch(/frame-ancestors/);
    expect(policy).toContain(appOrigin);
    await expect(page.locator(".document-preview iframe, dialog iframe, [role=dialog] iframe").first()).toBeVisible();
    guard.assertClean();
  });

  test("document text and excerpts load for a case document", async ({ page }) => {
    const guard = guardNetwork(page);
    await signIn(page);
    await selectCase(page, HEAT_CASE);
    const documents = await apiCall(page, "GET", `/cases/${HEAT_CASE.caseNumber}/documents/`);
    expect(documents.status).toBe(200);
    const materials = await apiCall(page, "GET", `/cases/${HEAT_CASE.caseNumber}/materials/`);
    expect(materials.data.documentsUnavailable, "LegalServer returned the case's documents").toBe("");
    const document = materials.data.documents[0];
    expect(document, "the sample case should hold documents").toBeTruthy();
    const context = await apiCall(page, "POST", `/cases/${HEAT_CASE.caseNumber}/documents/${document.id}/context/`, {
      mode: "search",
      query: "heat",
    });
    expect(context.status, JSON.stringify(context.data).slice(0, 300)).toBe(200);
    guard.assertClean();
  });
});

test.describe("quick cases", () => {
  test("a quick case is created from typed notes and becomes the active case", async ({ page }) => {
    const guard = guardNetwork(page);
    await signIn(page);
    const client = `E2E Quick ${Date.now()}`;
    await page.getByRole("button", { name: "New quick case" }).click();
    const form = page.locator("form.manual-case-form");
    await form.getByPlaceholder("Client name").fill(client);
    await form.getByPlaceholder("Eviction, conditions, subsidy...").fill("Eviction");
    await form.getByPlaceholder(/Type the facts/).fill(
      "Tenant received a 3-day notice on March 3. The furnace has not worked since January and the landlord was told in writing on January 12.",
    );
    await form.getByRole("button", { name: /Create|Save|Start/ }).click();
    await expect(page.locator(".topbar-case")).toContainText(client, { timeout: 60_000 });
    guard.assertClean();
  });
});

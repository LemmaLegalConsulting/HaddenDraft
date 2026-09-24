import { expect, test } from "@playwright/test";

import { apiCall, guardNetwork, modelTimeout, openScreen, selectCase, signIn } from "./support/deployment.js";

// Triage and case chat: the model-backed screens that work against the active
// case file. Both answer from LegalServer material, so both need the case's
// notes and documents to have reached the model.

const HEAT_CASE = { caseNumber: "26-0000085", client: "Christopher Anderson" };
const writesAllowed = process.env.E2E_ALLOW_LEGALSERVER_WRITES === "1";

test.describe("triage", () => {
  test("a case is scored against the rubric with its evidence", async ({ page }) => {
    test.setTimeout(modelTimeout * 2);
    const guard = guardNetwork(page);
    await signIn(page);
    await selectCase(page, HEAT_CASE);
    await openScreen(page, "Triage");
    await expect(page.getByRole("heading", { name: "Triage case" })).toBeVisible();
    await expect(page.getByLabel("Rubric standard")).not.toHaveValue("");

    // Ask for the LegalServer save as an advocate would. Whatever the site
    // allows, the answer must be a stated outcome, never an error or silence.
    const save = page.getByLabel("Save this assessment to the LegalServer case file");
    if (await save.isEnabled()) await save.check();

    const ran = page.waitForResponse(
      (response) => /\/triage\/$/.test(new URL(response.url()).pathname) && response.request().method() === "POST",
      { timeout: modelTimeout },
    );
    await page.getByRole("button", { name: "Run triage" }).click();
    const response = await ran;
    expect(response.ok(), `triage answered ${response.status()}`).toBeTruthy();
    const body = await response.json();

    const result = page.locator(".triage-result-panel");
    await expect(result).toBeVisible();
    await expect(result.locator("h2")).not.toBeEmpty();
    await expect(result.getByText("Summary", { exact: true })).toBeVisible();
    if (!writesAllowed) {
      // Writes are off in this run: the delivery must say it did not save.
      expect(JSON.stringify(body)).not.toMatch(/"status":\s*"saved"/);
    }

    const history = await apiCall(page, "GET", `/cases/${HEAT_CASE.caseNumber}/triage/`);
    expect(history.status).toBe(200);
    expect(history.data.assessments.length).toBeGreaterThan(0);
    guard.assertClean();
  });
});

test.describe("case chat", () => {
  test("a question about the case is answered from the case file", async ({ page }) => {
    test.setTimeout(modelTimeout * 2);
    const guard = guardNetwork(page);
    await signIn(page);
    await selectCase(page, HEAT_CASE);
    await openScreen(page, "Chat");
    await page.getByRole("button", { name: "New chat", exact: true }).click();

    const composer = page.getByPlaceholder("Ask about documents, case posture, parties, or drafting strategy");
    await composer.fill("What did the gas company inspection find about the heat?");
    const answered = page.waitForResponse(
      (response) => /\/chat\/$/.test(new URL(response.url()).pathname) && response.request().method() === "POST",
      { timeout: modelTimeout },
    );
    await page.getByRole("button", { name: "Send", exact: true }).click();
    expect((await answered).status()).toBe(200);

    const reply = page.locator(".chat-message.assistant").last();
    await expect(reply).toBeVisible({ timeout: modelTimeout });
    await expect(reply).toContainText(/heat|furnace|gas|inspect/i);
    guard.assertClean();
  });

  test("threads persist, switch, and clear", async ({ page }) => {
    test.setTimeout(modelTimeout * 2);
    const guard = guardNetwork(page);
    await signIn(page);
    await selectCase(page, HEAT_CASE);
    await openScreen(page, "Chat");
    await page.getByRole("button", { name: "New chat", exact: true }).click();
    const composer = page.getByPlaceholder("Ask about documents, case posture, parties, or drafting strategy");
    await composer.fill("Who is the landlord?");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.locator(".chat-message.assistant").last()).toBeVisible({ timeout: modelTimeout });

    // A reload keeps the advocate on the case they chose, and brings the
    // conversation back from the server.
    await page.reload();
    await expect(page.locator(".topbar-case")).toContainText(HEAT_CASE.client);
    await openScreen(page, "Chat");
    await expect(page.locator(".chat-message.user").filter({ hasText: "Who is the landlord?" })).toBeVisible();

    const threads = page.getByLabel("Case chat threads");
    expect(await threads.locator("option").count()).toBeGreaterThan(1);

    // Clear deletes, so it asks first (F12). Declining keeps the thread.
    page.once("dialog", (dialog) => dialog.dismiss());
    await page.getByRole("button", { name: "Clear", exact: true }).click();
    await expect(page.locator(".chat-message.user").filter({ hasText: "Who is the landlord?" })).toBeVisible();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Clear", exact: true }).click();
    await expect(page.locator(".chat-message.user").filter({ hasText: "Who is the landlord?" })).toHaveCount(0);
    guard.assertClean();
  });
});

import { expect, test } from "@playwright/test";

const writesAllowed = process.env.E2E_ALLOW_LEGALSERVER_WRITES === "1";
const username = process.env.E2E_USERNAME;
const password = process.env.E2E_PASSWORD;
const legalserverIdentifier = process.env.E2E_LEGALSERVER_IDENTIFIER;
const caseNumber = process.env.E2E_WRITE_CASE_NUMBER;
const clientName = process.env.E2E_WRITE_CLIENT_NAME;

async function login(page) {
  await page.goto("/");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Secret").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Cases" })).toBeVisible();
  const accountResponse = await page.request.get("/api/legalserver/account/");
  expect(accountResponse.ok(), "read the connected LegalServer account").toBeTruthy();
  const account = await accountResponse.json();
  expect(account.legalserver?.connected).toBeTruthy();
  expect(account.legalserver?.identifier).toBe(legalserverIdentifier);
}

async function selectCase(page) {
  await page.getByLabel("Search LegalServer matters").fill(caseNumber);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: caseNumber }).filter({ hasText: clientName });
  await expect(row).toBeVisible();
  const activate = row.getByRole("button", { name: "Make active" });
  if (await activate.count()) await activate.click();
  await expect(page.getByRole("button", { name: clientName, exact: true })).toBeVisible();
}

async function materials(page, { refresh = false } = {}) {
  const response = await page.request.get(`/api/cases/${caseNumber}/materials/${refresh ? "?refresh=1" : ""}`);
  expect(response.ok(), "read the LegalServer case file").toBeTruthy();
  return response.json();
}

test("creates and updates an audit note, then files a generated document with its AI audit", async ({ page }) => {
  test.skip(
    !writesAllowed || !username || !password || !legalserverIdentifier || !caseNumber || !clientName,
    "Live writes require E2E_ALLOW_LEGALSERVER_WRITES=1 and explicit account/case environment variables.",
  );
  test.setTimeout(180_000);
  const marker = `LS write validation ${Date.now()}`;

  await login(page);
  await selectCase(page);
  const before = await materials(page);
  const initialDocumentIds = new Set(before.documents.map((item) => String(item.id)));

  await page.getByRole("button", { name: "Chat", exact: true }).click();
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  const composer = page.getByPlaceholder("Ask about documents, case posture, parties, or drafting strategy");
  await composer.fill(`${marker}: summarize the documented lack of heat in one sentence.`);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".chat-message.assistant").last()).toBeVisible();

  await page.getByRole("button", { name: "Save to LegalServer", exact: true }).click();
  await expect(page.locator(".legalserver-save-result.success")).toBeVisible();
  let caseFile = await materials(page, { refresh: true });
  expect(caseFile.notes.some((note) => `${note.title} ${note.text}`.includes(marker))).toBeTruthy();

  await composer.fill(`${marker}: add that the gas-company inspection is in the case file.`);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".chat-message.assistant").last()).toBeVisible();
  await page.getByRole("button", { name: "Update in LegalServer", exact: true }).click();
  await expect(page.locator(".legalserver-save-result.success")).toBeVisible();
  caseFile = await materials(page, { refresh: true });
  const auditNotes = caseFile.notes.filter((note) => `${note.title} ${note.text}`.includes(marker));
  expect(auditNotes).toHaveLength(1);
  expect(auditNotes[0].text).toContain("gas-company inspection");

  await page.getByRole("button", { name: /^Draft(?:\s|$)/ }).click();
  await page.getByRole("button", { name: /I already know the template/ }).click();
  await page.getByLabel("Template").selectOption({ label: "CLE Emergency Motion for Heat" });
  await page.getByLabel("Goal or extra instructions").fill(
    `${marker}: prepare a narrowly scoped emergency motion using the reviewed case-file facts.`,
  );
  await page.getByRole("button", { name: "Make plan" }).click();
  await expect(page.getByLabel("Recommended template")).toHaveValue(
    await page.getByLabel("Recommended template").locator("option", { hasText: "CLE Emergency Motion for Heat" }).getAttribute("value"),
  );
  await page.getByText("Pause to review the template's blanks before generating").click();
  await page.getByRole("button", { name: "Generate draft" }).click();
  await expect(page.locator(".draft-block-header h4", { hasText: "Relevant Facts" })).toBeVisible();

  const exportResponsePromise = page.waitForResponse((response) => /\/api\/drafts\/\d+\/export\//.test(response.url()));
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export to Word", exact: true }).click();
  const [exportResponse, download] = await Promise.all([exportResponsePromise, downloadPromise]);
  expect(exportResponse.headers()["x-legalserver-delivery"]).toBe("saved");
  expect(exportResponse.headers()["x-legalserver-ai-audit"]).toBe("saved");
  expect(download.suggestedFilename()).toMatch(/\.docx$/);

  caseFile = await materials(page, { refresh: true });
  const createdDocuments = caseFile.documents.filter((item) => !initialDocumentIds.has(String(item.id)));
  expect(createdDocuments.filter((item) => /Emergency Motion for Heat/i.test(item.title))).toHaveLength(1);
  expect(caseFile.notes.some((note) => /AI usage audit — CLE Emergency Motion for Heat/i.test(note.title))).toBeTruthy();
});

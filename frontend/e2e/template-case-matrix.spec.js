import { expect, test } from "@playwright/test";

const username = process.env.E2E_USERNAME;
const password = process.env.E2E_PASSWORD;
const legalserverIdentifier = process.env.E2E_LEGALSERVER_IDENTIFIER;

const caseFiles = [
  { caseNumber: "26-0000045", client: "Eleanor Vance", notes: 1, documents: 4 },
  { caseNumber: "26-0000076", client: "Marcus Vance", notes: 1, documents: 4 },
  { caseNumber: "26-0000077", client: "Linda Thompson", notes: 1, documents: 4 },
  { caseNumber: "26-0000078", client: "Robert Garcia", notes: 1, documents: 4 },
  { caseNumber: "26-0000079", client: "James Miller", notes: 1, documents: 3 },
  { caseNumber: "26-0000080", client: "Sarah Jenkins", notes: 1, documents: 3 },
  { caseNumber: "26-0000081", client: "Charles Davis", notes: 1, documents: 2 },
  { caseNumber: "26-0000082", client: "Donna Evans", notes: 1, documents: 3 },
  { caseNumber: "26-0000083", client: "Thomas Wilson", notes: 1, documents: 3 },
  { caseNumber: "26-0000084", client: "Patricia Taylor", notes: 1, documents: 2 },
  { caseNumber: "26-0000085", client: "Christopher Anderson", notes: 1, documents: 3 },
];

const draftingMatrix = [
  {
    caseNumber: "26-0000045",
    client: "Eleanor Vance",
    template: "Answer and Counterclaims",
    goal: "Answer the eviction and preserve habitability counterclaims based on the leak and mold.",
    expectedBlock: "Facts",
  },
  {
    caseNumber: "26-0000076",
    client: "Marcus Vance",
    template: "Rent Ledger Template - Subsidy",
    goal: "Prepare a subsidized rent ledger separating the tenant share from CMHA payments.",
    exportLabel: "Export workbook",
    downloadExtension: ".xlsx",
  },
  {
    caseNumber: "26-0000079",
    client: "James Miller",
    template: "Motion for Continuance",
    goal: "Continue the eviction hearing while the documented rental assistance application is processed.",
    expectedBlock: "Motion body",
  },
  {
    caseNumber: "26-0000084",
    client: "Patricia Taylor",
    template: "CLE Motion to Dismiss - Lack of Specificity in 30 Day - Lease Violation",
    goal: "Challenge the nonspecific lease-violation notice described in the case file.",
    expectedBlock: "Statement Of The Case",
  },
  {
    caseNumber: "26-0000085",
    client: "Christopher Anderson",
    template: "CLE Emergency Motion for Heat",
    goal: "Seek emergency relief to restore heat based on the gas-company inspection and intake note.",
    expectedBlock: "Relevant Facts",
  },
];

async function login(page) {
  test.skip(
    !username || !password || !legalserverIdentifier,
    "Set E2E_USERNAME, E2E_PASSWORD, and E2E_LEGALSERVER_IDENTIFIER for a dedicated local test user.",
  );
  await page.goto("/");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Secret").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Cases" })).toBeVisible();
  const status = await page.request.get("/api/legalserver/account/");
  const account = await status.json();
  if (!account.legalserver?.connected) {
    const connected = await page.evaluate(async (identifier) => {
      const csrfToken = document.cookie
        .split("; ")
        .find((item) => item.startsWith("csrftoken="))
        ?.split("=")
        .slice(1)
        .join("=");
      const response = await fetch("/api/legalserver/account/", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": decodeURIComponent(csrfToken || ""),
        },
        body: JSON.stringify({ identifier }),
      });
      return { ok: response.ok, body: await response.text() };
    }, legalserverIdentifier);
    expect(connected.ok, `connect the dedicated browser user to LegalServer: ${connected.body}`).toBeTruthy();
    await page.reload();
    await expect(page.getByLabel("Search LegalServer matters")).toBeVisible();
  }
}

async function selectCase(page, item) {
  await page.getByLabel("Search LegalServer matters").fill(item.caseNumber);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: item.caseNumber }).filter({ hasText: item.client });
  await expect(row).toBeVisible();
  const activate = row.getByRole("button", { name: "Make active" });
  if (await activate.count()) {
    await activate.click();
  } else {
    await expect(row.getByText("Active", { exact: true })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: item.client, exact: true })).toBeVisible();
}

test.describe("LegalServer sample case files", () => {
  test("representative housing matters expose their live v2 notes and documents", async ({ page }) => {
    await login(page);
    for (const item of caseFiles) {
      const response = await page.request.get(`/api/cases/${item.caseNumber}/materials/`);
      expect(response.ok(), `${item.caseNumber} materials response`).toBeTruthy();
      const payload = await response.json();
      expect(payload.summary.noteCount, `${item.caseNumber} note count`).toBeGreaterThanOrEqual(item.notes);
      expect(payload.summary.documentCount, `${item.caseNumber} document count`).toBeGreaterThanOrEqual(item.documents);
      expect(payload.notes.some((note) => /intake/i.test(`${note.title} ${note.text}`))).toBeTruthy();
      expect(payload.documents.every((document) => document.title && document.id)).toBeTruthy();
    }
  });

  test("searching and opening representative sample cases keeps the selection coherent", async ({ page }) => {
    await login(page);
    for (const item of [caseFiles[0], caseFiles[4], caseFiles[10]]) {
      await selectCase(page, item);
      await expect(page.locator(".topbar-case")).toContainText(item.caseNumber);
    }
  });
});

test.describe("template and case combinations", () => {
  for (const combination of draftingMatrix) {
    test(`${combination.client} → ${combination.template}`, async ({ page }) => {
      await login(page);
      await selectCase(page, combination);
      await page.getByRole("button", { name: /^Draft(?:\s|$)/ }).click();
      await page.getByRole("button", { name: /I already know the template/ }).click();
      await page.getByLabel("Template").selectOption({ label: combination.template });
      await page.getByLabel("Goal or extra instructions").fill(combination.goal);
      await page.getByRole("button", { name: "Make plan" }).click();

      await expect(page.getByRole("heading", { name: combination.goal })).toBeVisible();
      await expect(page.getByLabel("Recommended template")).toHaveValue(
        await page.getByLabel("Recommended template").locator("option", { hasText: combination.template }).getAttribute("value"),
      );
      await page.getByText("Pause to review the template's blanks before generating").click();
      await page.getByRole("button", { name: "Generate draft" }).click();

      await expect(page.locator(".draft-editor")).toBeVisible();
      if (combination.expectedBlock) {
        await expect(page.locator(".draft-block-header h4", { hasText: combination.expectedBlock }).first()).toBeVisible();
        await expect(page.locator(".draft-editor")).not.toContainText("No facts selected for this section.");
      }
      const exportButton = page.getByRole("button", { name: combination.exportLabel || "Export to Word" });
      await expect(exportButton).toBeVisible();
      if (combination.downloadExtension) {
        const downloadPromise = page.waitForEvent("download");
        await exportButton.click();
        const download = await downloadPromise;
        expect(download.suggestedFilename()).toMatch(new RegExp(`${combination.downloadExtension.replace(".", "\\.")}$`));
      }
      await page.getByRole("button", { name: "Validate", exact: true }).click();
      await expect(page.getByRole("button", { name: "Recheck", exact: true })).toBeVisible();
    });
  }
});

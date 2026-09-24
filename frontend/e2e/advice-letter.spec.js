import { expect, test } from "@playwright/test";

import { docxPartNames, docxText } from "./support/docx.js";
import { apiCall, guardNetwork, modelTimeout, openScreen, selectCase, signIn } from "./support/deployment.js";

// Client advice letters: pick maintained sections, see the letter, download it
// on the organization's letterhead. Assembly is deterministic -- the wording is
// the working group's -- so the downloaded letter must carry it verbatim.

const DEPOSIT_CASE = { caseNumber: "26-0000045", client: "Eleanor Vance" };

async function openAdviceLetter(page) {
  await signIn(page);
  await selectCase(page, DEPOSIT_CASE);
  await openScreen(page, "Advice letter");
  await expect(page.getByRole("heading", { name: "Client advice letter" })).toBeVisible();
}

test.describe("advice letter", () => {
  test("every section is offered, and the ones needing review say why", async ({ page }) => {
    const guard = guardNetwork(page);
    await openAdviceLetter(page);
    const sections = await apiCall(page, "GET", "/advice-letters/sections/?region=&letterType=brief_advice&reviewedOnly=");
    expect(sections.status).toBe(200);
    expect(sections.data.sections.length).toBeGreaterThan(0);
    for (const section of sections.data.sections.filter((item) => item.needsAttorneyReview)) {
      expect(section.reviewReason || section.attorneyReviewReason, `${section.slug} says why it needs review`).toBeTruthy();
    }
    await page.getByLabel("Region").selectOption({ label: "Anywhere" });
    await expect(page.locator(".advice-catalog summary")).toContainText(/\d+ of \d+ chosen/);
    guard.assertClean();
  });

  test("chosen sections become a letter that downloads with their wording", async ({ page }) => {
    const guard = guardNetwork(page);
    await openAdviceLetter(page);
    // A complete profile, so the letter's closing has what it needs.
    const before = await apiCall(page, "GET", "/author-profile/");
    await apiCall(page, "PATCH", "/author-profile/", { ...before.data.profile, displayName: "Dana E2E Advocate", phone: "216-555-0100" });
    await page.reload();
    await selectCase(page, DEPOSIT_CASE);
    await openScreen(page, "Advice letter");
    await page.getByLabel("Region").selectOption({ label: "Anywhere" });

    const deposit = page.getByRole("checkbox", { name: /^Security Deposit/ });
    const drafted = page.waitForResponse((response) => /\/advice-letters\/drafts\/$/.test(new URL(response.url()).pathname));
    await deposit.check();
    const draftResponse = await drafted;
    expect(draftResponse.ok()).toBeTruthy();
    const { draft } = await draftResponse.json();
    const sectionText = (draft.plainText || "").replace(/\s+/g, " ");
    expect(sectionText.length, "the letter has body text").toBeGreaterThan(200);

    await expect(page.locator(".advice-editor-section")).toBeVisible();

    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download letter" }).click();
    const file = await download;
    expect(file.suggestedFilename()).toMatch(/\.docx$/);
    const path = await file.path();
    const text = docxText(path).replace(/\s+/g, " ");
    // A distinctive run of the maintained wording must survive to the file.
    const sample = sectionText.split(/(?<=\.) /).find((sentence) => sentence.length > 60 && !/^[A-Z ]{4,}\b/.test(sentence));
    expect(text).toContain(sample.trim().slice(0, 60));
    // The letterhead rides in a header part.
    expect(docxPartNames(path).some((name) => /^word\/header\d*\.xml$/.test(name)), "a letterhead header").toBeTruthy();
    expect(text).toContain("216-555-0100");
    expect(text).toContain("Dana E2E Advocate");
    await apiCall(page, "PATCH", "/author-profile/", before.data.profile || {});
    guard.assertClean();
  });

  // A letter is not sent with blanks where the advocate's contact details
  // belong, nor signed with a login (F13), unless the advocate says so.
  test("an incomplete profile holds the letter back until the advocate decides", async ({ page }) => {
    await openAdviceLetter(page);
    const before = await apiCall(page, "GET", "/author-profile/");
    await apiCall(page, "PATCH", "/author-profile/", { ...before.data.profile, phone: "", displayName: "" });
    try {
      await page.reload();
      await selectCase(page, DEPOSIT_CASE);
      await openScreen(page, "Advice letter");
      await page.getByLabel("Region").selectOption({ label: "Anywhere" });
      const drafted = page.waitForResponse((response) => /\/advice-letters\/drafts\/$/.test(new URL(response.url()).pathname));
      await page.getByRole("checkbox", { name: /^Security Deposit/ }).check();
      await drafted;

      const gaps = page.locator(".letter-contact-gaps");
      await expect(gaps).toContainText(/your name/);
      await expect(gaps).toContainText(/your phone number/);
      await expect(page.getByRole("button", { name: "Download letter" })).toBeDisabled();

      await gaps.getByLabel("Send it without them").check();
      await expect(page.getByRole("button", { name: "Download letter" })).toBeEnabled();
    } finally {
      await apiCall(page, "PATCH", "/author-profile/", before.data.profile || {});
    }
  });

  test("sections are suggested from what the letter is about", async ({ page }) => {
    test.setTimeout(modelTimeout * 2);
    const guard = guardNetwork(page);
    await openAdviceLetter(page);
    await page.getByLabel("What is this letter about?").fill(
      "The tenant moved out in June and the landlord kept the whole security deposit without an itemized list.",
    );
    const suggested = page.waitForResponse((response) => /\/advice-letters\/recommend\/$/.test(new URL(response.url()).pathname), {
      timeout: modelTimeout,
    });
    await page.getByRole("button", { name: "Suggest sections" }).click();
    const response = await suggested;
    expect(response.ok()).toBeTruthy();
    await expect(page.getByRole("heading", { name: "Suggested for this case" })).toBeVisible();
    await expect(page.getByText(/Security Deposit/).first()).toBeVisible();
    guard.assertClean();
  });
});

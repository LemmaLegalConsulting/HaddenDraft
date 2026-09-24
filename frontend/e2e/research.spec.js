import { expect, test } from "@playwright/test";

import { apiCall, guardNetwork, modelTimeout, openScreen, signIn } from "./support/deployment.js";

// Research: deterministic corpus search, the library behind it, and the cited
// question-answering chat. Search must work -- and say it used no model --
// whether or not AI is available; the chat is the only part that needs it.

async function openResearch(page) {
  await signIn(page);
  await openScreen(page, "Research");
  await expect(page.getByRole("tablist", { name: "Research view" })).toBeVisible();
}

async function search(page, query) {
  const box = page.getByRole("textbox", { name: /Search the corpus/ });
  await box.fill(query);
  const answered = page.waitForResponse((response) => /\/research\/search\/$/.test(new URL(response.url()).pathname) && response.request().method() === "POST");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const response = await answered;
  expect(response.status()).toBe(200);
  return response.json();
}

// The framing policy has to be read from the network, not from fetch: a
// cross-origin fetch cannot see Content-Security-Policy, so it looks absent.
async function expectFrameableByApp(page, response) {
  const policy = (await response.allHeaders())["content-security-policy"] || "";
  expect(policy, `${response.url()} must allow the app to frame it`).toContain(new URL(page.url()).origin);
}

test.describe("corpus search", () => {
  test("a plain query returns results and says no model was used", async ({ page }) => {
    const guard = guardNetwork(page);
    await openResearch(page);
    const payload = await search(page, "security deposit");
    expect(payload.total).toBeGreaterThan(0);
    await expect(page.getByRole("status").filter({ hasText: /No AI/ })).toBeVisible();
    await expect(page.locator("main article").first()).toBeVisible();
    guard.assertClean();
  });

  test("a facet narrows the results", async ({ page }) => {
    const guard = guardNetwork(page);
    await openResearch(page);
    const payload = await search(page, "security deposit");
    const sourceType = payload.facets.find((facet) => /source|corpus/i.test(`${facet.field} ${facet.label}`));
    expect(sourceType, "a source-type facet").toBeTruthy();
    const narrower = sourceType.values.find((value) => value.count < payload.total);
    expect(narrower, "a facet value narrower than the whole result set").toBeTruthy();

    const panel = page.getByRole("complementary", { name: "Narrow these results" });
    const group = panel.getByRole("group").filter({ hasText: sourceType.label });
    await group.locator("summary, button").first().click();
    const narrowed = page.waitForResponse((response) => /\/research\/search\/$/.test(new URL(response.url()).pathname));
    await group.getByText(narrower.label || narrower.value, { exact: false }).first().click();
    const body = await (await narrowed).json();
    expect(body.total).toBe(narrower.count);
    guard.assertClean();
  });

  test("a citation puts the section itself first", async ({ page }) => {
    await openResearch(page);
    const payload = await search(page, "R.C. 5321.16");
    expect(payload.results[0].corpus).toBe("statutes");
    expect(payload.results[0].citation).toMatch(/5321\.16/);
  });

  test("an exact phrase that matches nothing is named, not papered over", async ({ page }) => {
    const guard = guardNetwork(page);
    await openResearch(page);
    const payload = await search(page, '"zzqx flibbertigibbet" security deposit');
    expect(payload.total).toBe(0);
    await expect(page.getByText(/No source in this corpus contains the phrase “zzqx flibbertigibbet”/)).toBeVisible();
    guard.assertClean();
  });

  test("the search status reports the index and that AI is optional", async ({ page }) => {
    await openResearch(page);
    const status = await apiCall(page, "GET", "/research/search/status/");
    expect(status.status).toBe(200);
    expect(status.data.index.documentCount).toBeGreaterThan(0);
    expect(status.data.index.stale).toBe(false);
    // Every corpus the deployment ships must be in the index; an empty one is
    // a publishing step that silently did nothing.
    for (const corpus of ["treatises", "statutes", "cases", "ordinances"]) {
      expect(status.data.index.documentsByCorpus[corpus], `${corpus} indexed`).toBeGreaterThan(0);
    }
    expect(status.data.expansion.usesAi).toBe(false);
  });

  test("a case-law result previews and opens its source", async ({ page }) => {
    const guard = guardNetwork(page);
    await openResearch(page);
    await search(page, "security deposit itemized list");
    const first = page.locator("main article").first();
    await first.getByRole("button", { name: "Preview" }).click();
    const dialog = page.getByRole("dialog").last();
    await expect(dialog).toBeVisible();
    await expect(dialog).not.toBeEmpty();
    guard.assertClean();
  });
});

test.describe("library", () => {
  test("the case catalog opens a decision and serves its scan", async ({ page }) => {
    const guard = guardNetwork(page);
    await openResearch(page);
    await page.getByRole("tab", { name: "Browse the library" }).click();
    await expect(page.getByRole("tab", { name: "Cases" })).toBeVisible();
    await expect(page.getByText(/^1–25 of \d+/)).toBeVisible();

    const pdf = page.waitForResponse((response) => /\/caselaw\/decisions\/\d+\/pdf\/$/.test(new URL(response.url()).pathname));
    await page.getByRole("button", { name: "View full source" }).first().click();
    await expect(page.getByRole("dialog").last()).toBeVisible();
    const response = await pdf;
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toMatch(/pdf/);
    await expectFrameableByApp(page, response);
    guard.assertClean();
  });

  test("catalog facets narrow the case list", async ({ page }) => {
    const guard = guardNetwork(page);
    await openResearch(page);
    await page.getByRole("tab", { name: "Browse the library" }).click();
    const summary = page.getByText(/^1–\d+ of \d+/);
    await expect(summary).toBeVisible();
    const total = Number((await summary.innerText()).match(/of (\d+)/)[1]);
    // Treatment values are grouped by the reviewed vocabulary (F10).
    const reviewed = page.getByRole("complementary", { name: "Narrow by metadata" }).getByRole("button", { name: /^Treatment checked \d+$/ });
    const expected = Number((await reviewed.innerText()).match(/(\d+)$/)[1]);
    await reviewed.click();
    await expect(page.getByText(new RegExp(`^1–${expected} of ${expected}\\b`))).toBeVisible();
    expect(expected).toBeLessThan(total);
    guard.assertClean();
  });

  test("every library document opens, and its sources and PDFs are served", async ({ page }) => {
    const guard = guardNetwork(page);
    await openResearch(page);
    const library = await apiCall(page, "GET", "/library/");
    expect(library.status).toBe(200);
    const kinds = new Set(library.data.documents.map((document) => document.contentKind));
    for (const kind of ["treatise", "statute", "ordinance"]) {
      expect([...kinds].some((value) => value?.startsWith(kind)), `a ${kind} in the library`).toBeTruthy();
    }

    // A municipality whose only record is "no provision in force" has, rightly,
    // nothing to read; every other document must have something.
    const coverage = await apiCall(page, "GET", "/ordinances/coverage/");
    const nothingInForce = new Set(
      coverage.data.municipalities
        .filter((item) => item.sections.every((section) => section.status === "no_current_provision"))
        .map((item) => item.slug),
    );
    for (const document of library.data.documents) {
      const detail = await apiCall(page, "GET", `/library/${document.slug}/`);
      expect(detail.status, `${document.slug} opens`).toBe(200);
      if (nothingInForce.has(document.slug)) continue;
      expect(detail.data.tree?.length, `${document.slug} has a table of contents`).toBeGreaterThan(0);
    }

    // One source passage and its PDF page, from a document that has a PDF.
    const withPdf = library.data.documents.find((document) => document.pdfPages > 0);
    expect(withPdf, "a library document with a PDF").toBeTruthy();
    const detail = await apiCall(page, "GET", `/library/${withPdf.slug}/`);
    const leaf = JSON.stringify(detail.data.tree).match(/"chunkId":"([^"]+)"/);
    expect(leaf, `a source passage in ${withPdf.slug}`).toBeTruthy();
    const source = await apiCall(page, "GET", `/sources/content/${withPdf.slug}/${encodeURIComponent(leaf[1])}/`);
    expect(source.status).toBe(200);
    const pdf = await page.request.get(`${process.env.E2E_API_BASE || "/api"}/sources/content/${withPdf.slug}/${encodeURIComponent(leaf[1])}/pdf/`);
    expect(pdf.status()).toBe(200);
    expect(pdf.headers()["content-type"]).toMatch(/pdf/);
    guard.assertClean();
  });

  test("local ordinance coverage lists each municipality and what is pending", async ({ page }) => {
    const guard = guardNetwork(page);
    await openResearch(page);
    const coverage = await apiCall(page, "GET", "/ordinances/coverage/");
    expect(coverage.status).toBe(200);
    expect(coverage.data.municipalities.length).toBeGreaterThan(0);
    for (const municipality of coverage.data.municipalities) {
      expect(municipality.sections?.length, `${municipality.municipality} has sections`).toBeGreaterThan(0);
    }
    await page.getByRole("tab", { name: "Browse the library" }).click();
    await page.getByRole("tab", { name: "Local ordinances" }).click();
    await expect(page.getByText(coverage.data.municipalities[0].municipality).first()).toBeVisible();
    guard.assertClean();
  });
});

test.describe("repealed local law", () => {
  // A repeal produces no text to list; the library used to show an empty
  // document, which reads as "no local law here" (F9).
  test("a repealed ordinance says so in the library", async ({ page }) => {
    await openResearch(page);
    const coverage = await apiCall(page, "GET", "/ordinances/coverage/");
    const repealed = coverage.data.municipalities.find((item) =>
      item.sections.some((section) => section.status === "no_current_provision" && section.repealedBy),
    );
    expect(repealed, "a municipality with a repealed provision in the corpus").toBeTruthy();
    const section = repealed.sections.find((item) => item.repealedBy);

    await page.getByRole("tab", { name: "Browse the library" }).click();
    await page.getByRole("tab", { name: "Local ordinances" }).click();
    await page.getByText(repealed.documentTitle, { exact: true }).click();
    await expect(page.getByText(section.repealedBy).first()).toBeVisible({ timeout: 10_000 });
  });

  test("a search naming a city with a repealed ordinance states the repeal first", async ({ page }) => {
    await openResearch(page);
    const coverage = await apiCall(page, "GET", "/ordinances/coverage/");
    const repealed = coverage.data.municipalities.find((item) =>
      item.sections.some((section) => section.status === "no_current_provision" && section.repealedBy),
    );
    const section = repealed.sections.find((item) => item.repealedBy);
    const payload = await search(page, `${repealed.municipality} ${section.topicLabel.split("/")[0].trim()}`);
    expect(payload.coverageNotices.map((notice) => notice.municipality)).toContain(repealed.municipality);
    await expect(page.locator(".coverage-notice").first()).toContainText(/provision is in force/);
  });
});

test.describe("ask a question", () => {
  test("a question gets an answer that cites its sources", async ({ page }) => {
    test.setTimeout(modelTimeout * 2);
    const guard = guardNetwork(page);
    await openResearch(page);
    const status = await apiCall(page, "GET", "/research/search/status/");
    test.skip(!status.data.ai?.available, `AI is not available here: ${status.data.ai?.reason}`);

    await page.getByRole("tab", { name: "Ask a question" }).click();
    await page.locator(".research-question textarea").fill(
      "When must an Ohio landlord return a security deposit, and what must the itemized list include?",
    );
    const answered = page.waitForResponse(
      (response) => /\/research\/$/.test(new URL(response.url()).pathname) && response.request().method() === "POST",
      { timeout: modelTimeout },
    );
    await page.getByRole("button", { name: /Ask sources|Search sources/ }).click();
    const response = await answered;
    expect(response.status()).toBe(200);
    const transcript = page.getByLabel("Research conversation");
    await expect(transcript).toContainText(/5321\.16|security deposit/i, { timeout: modelTimeout });
    guard.assertClean();
  });
});

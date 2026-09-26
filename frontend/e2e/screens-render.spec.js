import { expect, test } from "@playwright/test";

// Every screen, opened and rendered, against a stubbed API.
//
// A component that is used but never defined compiles and deploys perfectly
// well and then throws "X is not defined" the moment React renders it. The
// Argument gym shipped that way -- a rewrite deleted CheckSelector while
// leaving the JSX that renders it -- and nothing in the build, the unit tests
// or the deploy checks noticed, because nothing rendered the screen.
//
// So this walks the sidebar, opens each screen, and fails on any uncaught
// exception or React error. The API is stubbed rather than served, so the run
// needs no Django, no database and no LegalServer credentials, and cannot fail
// for reasons that have nothing to do with the app rendering.

const MATTER = {
  id: 1,
  routeCaseKey: "26-0001",
  caseNumber: "26-0001",
  client: "Sample Client",
  matter: "Summary process",
  posture: "Answer due",
  sourceSystem: "Sample",
  facts: [],
  documents: [],
  notes: [],
};

// Only the shapes the screens actually read. Anything not listed answers {},
// which is the honest stand-in for an endpoint with nothing in it yet -- and a
// screen that cannot render an empty response is a screen with a real bug.
const RESPONSES = {
  "/auth/me/": { user: { isAuthenticated: true, name: "Smoke Test", username: "smoke", profile: {} } },
  "/bootstrap/": { sources: [], legalserverSave: {}, modes: [] },
  "/cases/": { cases: [MATTER], legalserver: null, meta: { total: 1 } },
  "/cases/1/": { case: MATTER },
  "/cases/1/triage/": { assessments: [] },
  "/templates/": { templates: [] },
  "/template-fill/": { templates: [], sessions: [] },
  "/triage/rubrics/": { rubrics: [] },
  "/author-profile/": { profile: {} },
  "/user-resources/": { resources: [] },
  "/library/": { documents: [] },
  "/argument-gym/checks/": { checks: [], defaults: [] },
  "/argument-gym/legal-rules/": { rules: [] },
  "/argument-gym/checklists/": { checklists: [] },
  "/argument-gym/workspaces/": { workspaces: [] },
};

function bodyFor(url) {
  const path = new URL(url).pathname.replace(/^\/api/, "");
  if (path in RESPONSES) return RESPONSES[path];
  if (path.startsWith("/advice-letters/sections")) return { sections: [], regions: [] };
  // The real endpoint always returns this key (advice_letter_views.py), so the
  // stub does too -- the check is whether the screen renders a real response,
  // not whether it survives one the server never sends.
  if (path.startsWith("/advice-letters/addressing")) return { addressing: {} };
  if (path.includes("/chat")) return { messages: [], threads: [] };
  if (path.startsWith("/research/search/status")) {
    return {
      index: { documentCount: 0, documentsByCorpus: {}, stale: false },
      expansion: { thesaurus: { available: true }, distributional: { available: false, reason: "Not built." }, usesAi: false },
      corpora: [],
      facetFields: [],
      querySyntax: [],
      ai: { available: false, reason: "AI features are switched off.", default: { rerank: false, synthesis: false } },
    };
  }
  if (path.startsWith("/research/search")) return { results: [], total: 0, facets: [], query: {}, unmatched: [] };
  if (path.startsWith("/research")) return { messages: [], threads: [] };
  return {};
}

// The screens reachable from the sidebar, and one thing on each that only that
// screen renders -- so a screen that silently renders nothing still fails.
const SCREENS = [
  { name: "Case", marker: "heading", text: "Cases" },
  { name: "Triage", marker: "heading", text: "Triage case" },
  { name: "Chat", marker: "combobox", text: "Case chat threads" },
  { name: "Research", marker: "tab", text: "Search the corpus" },
  { name: "Advice letter", marker: "heading", text: "Client advice letter" },
  { name: "Fill template", marker: "heading", text: "Fill template — no AI" },
  { name: "Draft", marker: "heading", text: "What do you want to file or accomplish?" },
  { name: "Argument gym", marker: "button", text: "Open session" },
];

// One saved drafting session on the stub case, with one generated document.
const SAVED_DRAFT = {
  id: 391, sessionId: 184, templateId: null, title: "Answer to complaint", exportFormat: "docx",
  sections: [{ key: "intro", label: "Introduction", body: "The tenant answers." }],
  plainText: "The tenant answers.", editorState: {}, validationFlags: [], updatedAt: "2026-09-25T12:00:00Z",
  revision: 3, validation: { state: "never", checkedRevision: null, validatedAt: "", summary: {} },
};
const SAVED_SESSION = {
  id: 184, mode: "draft_from_template", status: "draft_review", matter: MATTER, template: null,
  selectedFactIds: [], selectedCuratedFacts: [], selectedSourceResults: [], selectedBlockKeys: [],
  authorProfile: {}, templateData: {}, goal: "Answer the complaint", instructions: "Answer the complaint",
  draftPlan: { documents: [{ title: "Answer to complaint" }] }, missingInformation: [], selectedTemplateIds: [],
  workflowOptions: {}, revision: 2, updatedAt: "2026-09-25T12:00:00Z",
};
const SAVED_ROW = {
  id: 184, mode: "draft_from_template", status: "draft_review", matterId: 1, caseNumber: "26-0001", routeCaseKey: "26-0001",
  goal: "Answer the complaint", templateTitle: "", plannedDocuments: ["Answer to complaint"], draftCount: 1,
  createdAt: "2026-09-25T12:00:00Z", updatedAt: "2026-09-25T12:00:00Z",
};

function draftingBody(url) {
  const path = url.pathname.replace(/^\/api/, "");
  if (path === "/drafting-sessions/" && url.searchParams.get("caseKey")) {
    return { json: { sessions: [SAVED_ROW], total: 1, hasMore: false } };
  }
  if (path === "/drafting-sessions/184/") {
    const caseKey = url.searchParams.get("caseKey");
    if (caseKey && !ROUTE_KEYS.has(caseKey)) return { status: 404, json: { error: "Drafting session not found" } };
    return { json: { session: SAVED_SESSION, resume: { recommendedView: "draft", activeJobId: null, draftIds: [391], lastDraftId: 391, hasPlan: true } } };
  }
  if (path === "/drafting-sessions/184/drafts/") {
    if (url.searchParams.get("job")) return { json: { job: { id: 7, sessionId: 184, status: "complete", draftIds: [391] }, drafts: [SAVED_DRAFT] } };
    return { json: { drafts: [SAVED_DRAFT] } };
  }
  return null;
}

// The case a URL names: by its readable number or its id, and nothing else.
const ROUTE_KEYS = new Set([MATTER.routeCaseKey, String(MATTER.id)]);

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const drafting = route.request().method() === "GET" ? draftingBody(url) : null;
    if (drafting) return route.fulfill(drafting);
    if (url.pathname.endsWith("/cases/by-route-key/")) {
      return ROUTE_KEYS.has(url.searchParams.get("key"))
        ? route.fulfill({ json: { case: MATTER } })
        : route.fulfill({ status: 404, json: { error: "Case not found or not available to this user" } });
    }
    await route.fulfill({ json: bodyFor(route.request().url()) });
  });
});

// Collected per test rather than asserted inline: an exception thrown while
// rendering must fail the test that opened the screen, not the next one.
// `allow` names console errors a test provokes on purpose, such as the 404 the
// browser logs for a case that does not exist.
function watchForErrors(page, { allow = [] } = {}) {
  const errors = [];
  page.on("pageerror", (error) => errors.push(`uncaught: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    if (allow.some((pattern) => pattern.test(message.text()))) return;
    errors.push(`console: ${message.text()}`);
  });
  return errors;
}

// Waits for the screen, but gives up the moment the page throws -- a component
// that blew up on render will never produce its marker, and the exception is
// the finding worth reporting, not a timeout on an element that cannot appear.
async function expectScreenRenders(errors, marker) {
  await expect
    .poll(async () => errors[0] ?? ((await marker.isVisible()) ? "rendered" : "not yet"))
    .toBe("rendered");
}

test("every screen in the sidebar opens and renders", async ({ page }) => {
  const errors = watchForErrors(page);
  await page.goto("/");

  // The sidebar itself is the precondition: without it the app never signed in
  // and the per-screen failures below would all be the same one failure.
  await expect(page.locator("nav.mode-list")).toBeVisible();

  // No case is active until the advocate chooses one; the first row is never
  // chosen for them. Then choose the stub case, as an advocate would.
  await expect(page.locator(".topbar-case")).toHaveCount(0);
  await page.getByRole("button", { name: "Make active" }).first().click();
  await expect(page.locator(".topbar-case")).toContainText(MATTER.client);

  for (const screen of SCREENS) {
    await test.step(screen.name, async () => {
      await page.locator("nav.mode-list button", { hasText: screen.name }).click();
      await expectScreenRenders(errors, page.getByRole(screen.marker, { name: screen.text }));
    });
  }
});

test("the draft workflow steps each render", async ({ page }) => {
  const errors = watchForErrors(page);
  await page.goto("/");
  // With no case, Draft lists saved work and asks for a case; setup needs one.
  await page.getByRole("button", { name: "Make active" }).first().click();
  await page.locator("nav.mode-list button", { hasText: "Draft" }).click();

  const steps = page.locator(".stepper button.step");
  // Changing screen is a navigation now, and it renders a moment after the
  // click; counting at once counted an empty sidebar.
  await expect(steps.first()).toBeVisible();
  const count = await steps.count();
  expect(count, "the draft stepper listed no steps").toBeGreaterThan(0);

  for (let index = 0; index < count; index += 1) {
    const label = (await steps.nth(index).innerText()).trim();
    await test.step(label, async () => {
      await steps.nth(index).click();
      await expectScreenRenders(errors, page.locator("main.workspace"));
    });
  }
});


test("the address bar names the screen and the case, and survives a reload", async ({ page }) => {
  const errors = watchForErrors(page);
  await page.goto("/");
  await expect(page).toHaveURL(/\/cases$/);
  await page.getByRole("button", { name: "Make active" }).first().click();
  await expect(page).toHaveURL(/\/cases\/26-0001$/);

  await page.locator("nav.mode-list button", { hasText: "Draft" }).click();
  await expect(page).toHaveURL(/\/drafting\/26-0001\/new$/);
  await page.reload();
  await expect(page.locator(".topbar-case")).toContainText(MATTER.client);
  await expectScreenRenders(errors, page.getByRole("heading", { name: "What do you want to file or accomplish?" }));

  await page.goBack();
  await expect(page).toHaveURL(/\/cases\/26-0001$/);
  await expect(page.getByRole("heading", { name: "Cases" })).toBeVisible();
});

test("a pasted link opens its own case, even with another one remembered", async ({ page }) => {
  const errors = watchForErrors(page);
  await page.addInitScript(() => localStorage.setItem("drafting.activeCase:smoke", "SOMEONE-ELSE"));
  await page.goto("/triage/26-0001");
  await expect(page.locator(".topbar-case")).toContainText(MATTER.client);
  await expectScreenRenders(errors, page.getByRole("heading", { name: "Triage case" }));
  await expect(page).toHaveURL(/\/triage\/26-0001$/);
});

test("a link by external id is rewritten to the readable case number", async ({ page }) => {
  await page.goto("/chat/1");
  await expect(page).toHaveURL(/\/chat\/26-0001$/);
  await expect(page.locator(".topbar-case")).toContainText(MATTER.client);
});

test("a case that does not open shows nothing from any other case", async ({ page }) => {
  const errors = watchForErrors(page, { allow: [/status of 404/] });
  await page.goto("/cases/26-0001");
  await expect(page.locator(".topbar-case")).toContainText(MATTER.client);
  await page.goto("/drafting/26-9999/new");
  await expectScreenRenders(errors, page.getByRole("heading", { name: "Case 26-9999 is not available" }));
  await expect(page.locator(".topbar-case")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "What do you want to file or accomplish?" })).toHaveCount(0);
  await expect(page).toHaveURL(/\/drafting\/26-9999\/new$/);

  // The bad link left the case being worked on alone.
  await page.getByRole("button", { name: "Choose a case" }).click();
  await expect(page).toHaveURL(/\/cases\/26-0001$/);
});

test("an account without LegalServer is told to connect it, and the case then opens", async ({ page }) => {
  let connected = false;
  await page.route((url) => url.pathname.endsWith("/api/cases/by-route-key/"), (route) => (
    connected
      ? route.fulfill({ json: { case: MATTER } })
      : route.fulfill({ status: 404, json: { error: "Case not found or not available to this user", reason: "legalserver_not_connected" } })
  ));
  await page.route("**/api/legalserver/account/", (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    connected = true;
    return route.fulfill({ json: { legalserver: { configured: true, connected: true, identifier: "smoke@example.org" } } });
  });
  const errors = watchForErrors(page, { allow: [/status of 404/] });
  await page.goto("/cases/26-0001");
  await expectScreenRenders(errors, page.getByRole("heading", { name: "Connect LegalServer to open case 26-0001" }));
  await expect(page.getByText("assigned to someone else")).toHaveCount(0);
  await page.getByRole("button", { name: "Connect LegalServer" }).first().click();
  const dialog = page.getByRole("dialog", { name: "LegalServer connection settings" });
  await dialog.getByLabel("LegalServer identifier").fill("smoke@example.org");
  await dialog.getByRole("button", { name: "Connect LegalServer" }).click();
  await expect(page.locator(".topbar-case")).toContainText(MATTER.client);
  await expect(page).toHaveURL(/\/cases\/26-0001$/);
});

test("a link this version cannot open says so rather than opening something else", async ({ page }) => {
  const errors = watchForErrors(page);
  await page.goto("/drafting/26-0001/sessions/184/drafts/391/export");
  await expectScreenRenders(errors, page.getByRole("heading", { name: "This page does not exist" }));
  await expect(page).toHaveURL(/\/drafting\/26-0001\/sessions\/184\/drafts\/391\/export$/);
});

// Opening saved work is reading it. Any write while following links is a bug.
function watchForWrites(page) {
  const writes = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/") && request.method() !== "GET") writes.push(`${request.method()} ${request.url()}`);
  });
  return writes;
}

test("a case's saved drafting work is listed and each row reopens it", async ({ page }) => {
  const errors = watchForErrors(page);
  const writes = watchForWrites(page);
  await page.goto("/drafting/26-0001");
  await expectScreenRenders(errors, page.getByRole("heading", { name: "Drafting" }));
  await page.getByRole("link", { name: /Answer to complaint/ }).click();
  // The session resolves to the document it last saved, replacing itself.
  await expect(page).toHaveURL(/\/drafting\/26-0001\/sessions\/184\/drafts\/391$/);
  await expect(page.locator(".draft-switcher, .editor-panel").first()).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/drafting\/26-0001$/);
  expect(writes).toEqual([]);
});

test("a saved document survives a reload without anything being regenerated", async ({ page }) => {
  const errors = watchForErrors(page);
  const writes = watchForWrites(page);
  await page.goto("/drafting/26-0001/sessions/184/drafts/391");
  await expectScreenRenders(errors, page.locator(".editor-panel"));
  await page.reload();
  await expectScreenRenders(errors, page.locator(".editor-panel"));
  await page.goto("/drafting/26-0001/sessions/184/plan");
  await expectScreenRenders(errors, page.locator("main.workspace .panel").first());
  await expect(page).toHaveURL(/\/sessions\/184\/plan$/);
  expect(writes).toEqual([]);
});

test("a session opened under the wrong case does not open", async ({ page }) => {
  const errors = watchForErrors(page, { allow: [/status of 404/] });
  await page.goto("/drafting/1/sessions/184/plan");
  // "1" is the stub case's id, so it canonicalizes; an unknown case never opens.
  await page.goto("/drafting/26-9999/sessions/184/plan");
  await expectScreenRenders(errors, page.getByRole("heading", { name: "Case 26-9999 is not available" }));
});

test("a document the session does not have says so", async ({ page }) => {
  const errors = watchForErrors(page);
  await page.goto("/drafting/26-0001/sessions/184/drafts/999");
  await expectScreenRenders(errors, page.getByRole("heading", { name: "This document is not part of this session" }));
});

test("a generation link reconnects to its job and lands on the document", async ({ page }) => {
  const writes = watchForWrites(page);
  await page.goto("/drafting/26-0001/sessions/184/jobs/7");
  await expect(page).toHaveURL(/\/sessions\/184\/drafts\/391$/);
  expect(writes).toEqual([]);
});

test("making a plan gives the new session its own URL, replacing setup", async ({ page }) => {
  const created = { ...SAVED_SESSION, id: 185, draftPlan: {} };
  const planned = { ...created, draftPlan: { documents: [{ title: "Answer to complaint" }] }, selectedFactIds: [1] };
  await page.route("**/api/drafting-sessions/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST" && path.endsWith("/drafting-sessions/")) return route.fulfill({ status: 201, json: { session: created } });
    if (request.method() === "POST" && path.endsWith("/185/plan/")) return route.fulfill({ json: { session: planned, plan: planned.draftPlan } });
    if (request.method() === "POST" && path.endsWith("/185/recommend-facts/")) return route.fulfill({ json: { session: planned, factIds: [1] } });
    if (request.method() === "PATCH" && path.endsWith("/185/")) return route.fulfill({ json: { session: { ...planned, revision: (planned.revision || 0) + 1 } } });
    return route.fallback();
  });
  const errors = watchForErrors(page);
  await page.goto("/cases/26-0001");
  await page.locator("nav.mode-list button", { hasText: "Draft" }).click();
  await expect(page).toHaveURL(/\/drafting\/26-0001\/new$/);
  await page.getByRole("textbox").first().fill("Answer the complaint");
  await page.getByRole("button", { name: "Make plan" }).click();
  await expect(page).toHaveURL(/\/drafting\/26-0001\/sessions\/185\/plan$/);
  await expectScreenRenders(errors, page.locator(".stepper"));
  // Setup was replaced: Back leaves drafting rather than offering setup again.
  await page.goBack();
  await expect(page).toHaveURL(/\/cases\/26-0001$/);
});

async function typeIntoDocument(page, text) {
  const editable = page.locator(".editor-panel [contenteditable='true']").first();
  await editable.click();
  await page.keyboard.press("End");
  await page.keyboard.type(text);
}

test("leaving a document with unsaved edits asks first, and Stay keeps them", async ({ page }) => {
  const errors = watchForErrors(page);
  await page.goto("/drafting/26-0001/sessions/184/drafts/391");
  await expectScreenRenders(errors, page.locator(".editor-panel"));
  await typeIntoDocument(page, " More.");
  await expect(page.getByText("Unsaved changes", { exact: true })).toBeVisible();

  await page.locator("nav.mode-list button", { hasText: "Triage" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Leave with unsaved changes?" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Stay" }).click();
  await expect(dialog).toBeHidden();
  await expect(page).toHaveURL(/\/drafts\/391$/);
  await expect(page.getByText("Unsaved changes", { exact: true })).toBeVisible();

  await page.locator("nav.mode-list button", { hasText: "Triage" }).click();
  await dialog.getByRole("button", { name: "Discard changes" }).click();
  await expect(page).toHaveURL(/\/triage\/26-0001$/);
});

test("a document saved in another window is a conflict, never an overwrite", async ({ page }) => {
  const theirs = { ...SAVED_DRAFT, revision: 5, plainText: "Their version.", sections: [{ key: "intro", label: "Introduction", body: "Their version." }] };
  let patches = 0;
  await page.route("**/api/drafts/391/", async (route) => {
    if (route.request().method() !== "PATCH") return route.fallback();
    patches += 1;
    const body = route.request().postDataJSON();
    if (body.revision !== 5) {
      return route.fulfill({ status: 409, json: { error: "This was changed in another window since you opened it.", conflict: "draft", currentRevision: 5, draft: theirs } });
    }
    return route.fulfill({ json: { draft: { ...SAVED_DRAFT, ...body, revision: 6 } } });
  });
  const errors = watchForErrors(page, { allow: [/status of 409/] });
  await page.goto("/drafting/26-0001/sessions/184/drafts/391");
  await expectScreenRenders(errors, page.locator(".editor-panel"));
  await typeIntoDocument(page, " Mine.");
  await page.getByRole("button", { name: "Save", exact: true }).click();

  const conflict = page.getByRole("alert").filter({ hasText: "changed in another window" });
  await expect(conflict).toBeVisible();
  await expect(page.locator(".editor-panel")).toContainText("Mine.");
  // Keeping mine is a deliberate overwrite, sent against their revision.
  await conflict.getByRole("button", { name: "Keep mine and save over it" }).click();
  await expect(page.getByText("All changes saved")).toBeVisible();
  expect(patches).toBe(2);
});

test("a session edited in another window is a conflict too", async ({ page }) => {
  await page.route("**/api/drafting-sessions/184/", async (route) => {
    if (route.request().method() !== "PATCH") return route.fallback();
    return route.fulfill({
      status: 409,
      json: { error: "This was changed in another window since you opened it.", conflict: "session", currentRevision: 9, session: { ...SAVED_SESSION, revision: 9, goal: "Their goal" } },
    });
  });
  const errors = watchForErrors(page, { allow: [/status of 409/] });
  await page.goto("/drafting/26-0001/sessions/184/goal");
  await expectScreenRenders(errors, page.getByText("All changes saved"));
  await page.getByRole("textbox").first().fill("My goal");
  await page.getByRole("status").getByRole("button", { name: "Save" }).click();
  const conflict = page.getByRole("alert").filter({ hasText: "changed in another window" });
  await expect(conflict).toBeVisible();
  await conflict.getByRole("button", { name: "Load the saved version (discard mine)" }).click();
  await expect(page.getByRole("textbox").first()).toHaveValue("Their goal");
});

const ASSESSMENTS = [
  { id: 52, priority: true, priorityLabel: "Priority", confidence: "high", summary: "Newest summary.", reasoning: "", matchedCriteria: [], missingInformation: [], evidence: [], rubric: { name: "Eviction" }, createdAt: "2026-09-25T12:00:00Z" },
  { id: 51, priority: false, priorityLabel: "Needs review", confidence: "low", summary: "Older summary.", reasoning: "", matchedCriteria: [], missingInformation: [], evidence: [], rubric: { name: "Eviction" }, createdAt: "2026-09-20T12:00:00Z" },
];

test("a saved triage assessment opens by its URL and never reruns", async ({ page }) => {
  await page.route("**/api/cases/1/triage/", (route) => (
    route.request().method() === "GET" ? route.fulfill({ json: { assessments: ASSESSMENTS } }) : route.fallback()
  ));
  const errors = watchForErrors(page);
  const writes = watchForWrites(page);
  await page.goto("/triage/26-0001/assessments/51");
  await expectScreenRenders(errors, page.getByText("Older summary."));
  await page.getByRole("navigation", { name: "Saved assessments" }).getByRole("link", { name: /Priority/ }).click();
  await expect(page).toHaveURL(/\/triage\/26-0001\/assessments\/52$/);
  await expect(page.getByText("Newest summary.")).toBeVisible();
  await page.goto("/triage/26-0001/assessments/999");
  await expectScreenRenders(errors, page.getByRole("heading", { name: "This triage assessment is not available" }));
  await expect(page.getByText("Newest summary.")).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("a chat thread opens by its URL, an archived one is read-only, and a missing one is never replaced", async ({ page }) => {
  await page.route("**/api/cases/1/chat/**", (route) => {
    const threadId = new URL(route.request().url()).searchParams.get("threadId");
    const threads = [{ id: 7, active: true, preview: "Current" }, { id: 3, active: false, preview: "Earlier question" }];
    if (threadId === "999") return route.fulfill({ status: 404, json: { error: "Chat thread not found" } });
    const messages = threadId === "3" ? [{ role: "user", content: "An earlier question" }] : [{ role: "user", content: "A current question" }];
    return route.fulfill({ json: { messages, threads, threadId: Number(threadId || 7), currentThreadId: 7 } });
  });
  const errors = watchForErrors(page, { allow: [/status of 404/] });
  const writes = watchForWrites(page);
  await page.goto("/chat/26-0001/threads/3");
  await expectScreenRenders(errors, page.getByText("An earlier question"));
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();
  await page.getByRole("combobox", { name: "Case chat threads" }).selectOption("");
  await expect(page).toHaveURL(/\/chat\/26-0001$/);
  await expect(page.getByText("A current question")).toBeVisible();
  await page.goto("/chat/26-0001/threads/999");
  await expectScreenRenders(errors, page.getByText("This conversation is not available"));
  await expect(page.getByText("A current question")).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("fill template upload, optional answers, save and DOCX download", async ({ page }) => {
  const errors = watchForErrors(page);
  let uploaded = false;
  const session = { id: 81, title: "Uploaded motion", revision: 0, fields: [
    { key: "client", path: "client", label: "Client", kind: "text", value: "Sample Client", source: "LegalServer: client_full_name", state: "mapped" },
    { key: "hearing", path: "hearing", label: "Hearing date", kind: "text", value: null, state: "unanswered", context: [{ text: "The hearing is set for " }, { fields: ["hearing"] }, { text: "." }] },
    { key: "reason", path: "reason", label: "Reason", kind: "multiline", value: null, state: "unanswered" },
  ] };
  const finished = { id: 91, sessionId: 81, kind: "export", status: "complete", result: { filename: "filled.docx", delivery: null } };
  await page.route("**/api/template-fill/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/start/")) {
      expect(request.headers()["content-type"]).toContain("multipart/form-data");
      uploaded = true;
      return route.fulfill({ json: { job: { id: 90, sessionId: 81, kind: "prepare", status: "complete" } } });
    }
    if (path.endsWith("/preview/")) {
      return route.fulfill({ json: { preview: { header: [], footer: [], truncated: false, assumedOff: [], body: [
        { kind: "p", segments: [{ text: "Client: " }, { filled: "Sample Client", key: "client", label: "Client" }] },
        { kind: "p", segments: [{ text: "The hearing is set for " }, { prompt: "Hearing date", key: "hearing" }, { text: "." }] },
      ] } } });
    }
    if (path.endsWith("/sessions/81/")) {
      if (request.method() !== "GET") {
        const payload = request.postDataJSON();
        expect(payload.answers).toEqual({ hearing: "May 1", reason: "Please continue the hearing." });
        session.fields[2].value = payload.answers.reason;
        session.revision += 1;
        if (request.method() === "POST") return route.fulfill({ json: { job: finished, session } });
      }
      return route.fulfill({ json: { session, jobs: [] } });
    }
    if (path.endsWith("/file/")) return route.fulfill({ contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers: { "Content-Disposition": 'attachment; filename="filled.docx"' }, body: "synthetic DOCX download" });
    return route.fulfill({ json: { templates: [], sessions: uploaded ? [{ id: 81, title: session.title, updatedAt: "2026-09-25T12:00:00Z" }] : [] } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Make active" }).first().click();
  await page.locator("nav.mode-list button", { hasText: "Fill template" }).click();
  await page.getByLabel("Or upload a DOCX template (up to 15 MB)").setInputFiles({ name: "motion.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: Buffer.from("synthetic upload") });
  await expect(page.getByRole("textbox", { name: "Client", exact: true })).toHaveValue("Sample Client");
  await expect(page.locator(".fill-inline-sentence").getByRole("textbox", { name: "Hearing date", exact: true })).toHaveValue("");
  await page.getByLabel("Type short blanks inside their sentence").uncheck();
  await expect(page.locator(".fill-inline-sentence")).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Hearing date", exact: true })).toHaveValue("");
  await page.getByRole("tab", { name: "Preview" }).click();
  await expect(page.getByRole("article", { name: "Document preview" })).toContainText("The hearing is set for");
  await page.getByRole("button", { name: "[Enter Hearing date]" }).click();
  const dialog = page.getByRole("dialog", { name: "Hearing date" });
  await dialog.getByRole("textbox").fill("May 1");
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("All changes saved.")).toBeVisible();
  await page.getByRole("button", { name: "[Enter Hearing date]" }).click();
  await dialog.getByRole("textbox").fill("May 1");
  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(page.getByText("1 unsaved change")).toBeVisible();
  await page.getByRole("tab", { name: "Fill in blanks" }).click();
  await expect(page.getByRole("textbox", { name: "Hearing date", exact: true })).toHaveValue("May 1");
  await page.getByRole("textbox", { name: "Reason", exact: true }).fill("Please continue the hearing.");
  // Leaving the screen unmounts the panel; coming back reopens the session with
  // the unsaved typing restored, rather than an empty template picker.
  await page.locator("nav.mode-list button", { hasText: "Chat" }).click();
  await page.locator("nav.mode-list button", { hasText: "Fill template" }).click();
  await expect(page.getByText(/Restored 2 unsaved changes/)).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Reason", exact: true })).toHaveValue("Please continue the hearing.");
  await page.getByRole("button", { name: "Prepare DOCX", exact: true }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download prepared DOCX" }).click();
  expect((await downloadPromise).suggestedFilename()).toBe("filled.docx");
  expect(errors).toEqual([]);
});

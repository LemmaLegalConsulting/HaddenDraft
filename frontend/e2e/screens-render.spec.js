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
  if (path.startsWith("/research")) return { messages: [], threads: [] };
  return {};
}

// The screens reachable from the sidebar, and one thing on each that only that
// screen renders -- so a screen that silently renders nothing still fails.
const SCREENS = [
  { name: "Case", marker: "heading", text: "Cases" },
  { name: "Triage", marker: "heading", text: "Triage case" },
  { name: "Chat", marker: "combobox", text: "Case chat threads" },
  { name: "Research", marker: "tab", text: "Ask a question" },
  { name: "Advice letter", marker: "heading", text: "Client advice letter" },
  { name: "Draft", marker: "heading", text: "What do you want to file or accomplish?" },
  { name: "Argument gym", marker: "button", text: "Open session" },
];

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ json: bodyFor(route.request().url()) });
  });
});

// Collected per test rather than asserted inline: an exception thrown while
// rendering must fail the test that opened the screen, not the next one.
function watchForErrors(page) {
  const errors = [];
  page.on("pageerror", (error) => errors.push(`uncaught: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
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
  await page.locator("nav.mode-list button", { hasText: "Draft" }).click();

  const steps = page.locator(".stepper button.step");
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

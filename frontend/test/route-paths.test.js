import assert from "node:assert/strict";
import test from "node:test";

import {
  canonicalPath,
  caseRouteAction,
  matterMatchesKey,
  parseLocation,
  buildPath,
  pathForMode,
  resumePath,
  routeCaseState,
  paths,
  signInReturnPath,
  TASK_ROOTS,
} from "../src/routes/paths.js";

test("builds task-first case URLs", () => {
  assert.equal(paths.case("26-0222"), "/cases/26-0222");
  assert.equal(paths.drafting("26-0222"), "/drafting/26-0222");
  assert.equal(paths.draftingNew("26-0222"), "/drafting/26-0222/new");
  assert.equal(pathForMode("triage", "26-0222"), "/triage/26-0222");
  assert.equal(pathForMode("case_chat", "26-0222"), "/chat/26-0222");
  assert.equal(pathForMode("template_fill", "26-0222"), "/template-fill/26-0222");
  assert.equal(pathForMode("advice_letter", "26-0222"), "/advice-letters/26-0222");
  assert.equal(pathForMode("draft", "26-0222", { view: "new" }), "/drafting/26-0222/new");
});

test("a case-scoped task with no case goes to the task's own screen", () => {
  assert.equal(pathForMode("draft", null), "/drafting");
  assert.equal(pathForMode("case", null), "/cases");
});

test("research and the argument gym never carry a case", () => {
  assert.equal(pathForMode("research", "26-0222"), "/research/search");
  assert.equal(pathForMode("argument_gym", "26-0222"), "/argument-gym");
});

test("a case key is encoded, so a stray character cannot add a path segment", () => {
  assert.equal(paths.drafting("A/B C"), "/drafting/A%2FB%20C");
  assert.deepEqual(parseLocation("/drafting/A%2FB%20C").caseKey, "A/B C");
});

const pick = ({ mode, caseKey, view, found }) => ({ mode, caseKey, view, found });

test("reads every route this version can open", () => {
  assert.deepEqual(pick(parseLocation("/drafting/26-0222")), { mode: "draft", caseKey: "26-0222", view: null, found: true });
  assert.deepEqual(pick(parseLocation("/drafting/26-0222/new")), { mode: "draft", caseKey: "26-0222", view: "new", found: true });
  assert.deepEqual(pick(parseLocation("/cases")), { mode: "case", caseKey: null, view: null, found: true });
  assert.equal(parseLocation("/cases/26-0222/").caseKey, "26-0222");
  assert.equal(parseLocation("/research/search").mode, "research");
  assert.equal(parseLocation("/research").mode, "research");
  assert.equal(parseLocation("/argument-gym").mode, "argument_gym");
  assert.equal(parseLocation("/").root, true);
});

test("every mode round-trips through its path", () => {
  for (const mode of Object.keys(TASK_ROOTS)) {
    assert.equal(parseLocation(pathForMode(mode, "26-0222")).mode, mode, mode);
  }
});

test("a link this version cannot open is not found, never trimmed to its case", () => {
  for (const path of [
    "/drafting/26-0222/sessions/0",
    "/drafting/26-0222/sessions/abc",
    "/drafting/26-0222/sessions/184/drafts",
    "/drafting/26-0222/sessions/184/drafts/9/export",
    "/drafting/26-0222/sessions/184/generate",
    "/drafting/26-0222/plan",
    "/cases/26-0222/documents",
    "/triage/26-0222/new",
    "/research/chats/4",
    "/argument-gym/workspaces/2",
    "/api/cases/",
    "/admin/",
    "/nonsense",
    "/drafting/%E0%A4%A",
    "/drafting/%20",
  ]) {
    assert.equal(parseLocation(path).found, false, path);
  }
});

test("canonical path swaps in the current key and keeps the screen", () => {
  assert.equal(canonicalPath(parseLocation("/drafting/OLD-1/new"), "26-0999"), "/drafting/26-0999/new");
  assert.equal(canonicalPath(parseLocation("/triage/MID-1"), "26-0222"), "/triage/26-0222");
  assert.equal(canonicalPath(parseLocation("/research/search"), "26-0222"), null);
});

test("the URL's case wins over the remembered one", () => {
  assert.deepEqual(
    caseRouteAction(parseLocation("/drafting/26-0222"), { activeCaseKey: "26-0111" }),
    { type: "load", caseKey: "26-0222" },
  );
});

test("a task URL with no case fills in the active case", () => {
  assert.deepEqual(
    caseRouteAction(parseLocation("/drafting"), { activeCaseKey: "26-0111" }),
    { type: "redirect", to: "/drafting/26-0111" },
  );
  assert.deepEqual(caseRouteAction(parseLocation("/"), { activeCaseKey: "26-0111" }), { type: "redirect", to: "/cases/26-0111" });
  assert.deepEqual(caseRouteAction(parseLocation("/"), {}), { type: "redirect", to: "/cases" });
});

test("with no case anywhere, nothing is opened -- never a guess", () => {
  assert.deepEqual(caseRouteAction(parseLocation("/drafting"), {}), { type: "none" });
  assert.deepEqual(caseRouteAction(parseLocation("/research/search"), {}), { type: "none" });
});

test("a standalone task keeps the active case as context without putting it in the URL", () => {
  assert.deepEqual(
    caseRouteAction(parseLocation("/research/search"), { activeCaseKey: "26-0111" }),
    { type: "load", caseKey: "26-0111" },
  );
});

test("only an openable page is offered as a sign-in return target", () => {
  assert.equal(signInReturnPath("/drafting/26-0222/new"), "/drafting/26-0222/new");
  assert.equal(signInReturnPath("/"), "");
  assert.equal(signInReturnPath("/admin/"), "");
});

test("a loaded matter matches its route key or its external id", () => {
  const matter = { id: "MID-1", routeCaseKey: "26-0222" };
  assert.equal(matterMatchesKey(matter, "26-0222"), true);
  assert.equal(matterMatchesKey(matter, "MID-1"), true);
  assert.equal(matterMatchesKey(matter, "26-0333"), false);
  assert.equal(matterMatchesKey(null, "26-0222"), false);
});

test("a case screen waits for the case its URL names", () => {
  const route = parseLocation("/drafting/26-0222");
  assert.equal(routeCaseState(route, {}), "loading");
  assert.equal(routeCaseState(route, { matter: { id: "MID-1", routeCaseKey: "26-0222" } }), "ready");
  assert.equal(routeCaseState(parseLocation("/drafting"), {}), "none");
});

test("another case still in memory never counts as the URL's case", () => {
  const route = parseLocation("/drafting/26-0222");
  const other = { id: "MID-2", routeCaseKey: "26-0333" };
  assert.equal(routeCaseState(route, { matter: other }), "loading");
  assert.equal(routeCaseState(route, { matter: other, lookup: { key: "26-0222", status: "unavailable" } }), "unavailable");
});

test("an old case number stays ready while the URL is rewritten to the new one", () => {
  const route = parseLocation("/drafting/26-0111");
  const matter = { id: "MID-1", routeCaseKey: "26-0999" };
  assert.equal(routeCaseState(route, { matter, lookup: { key: "26-0111", status: "ready" } }), "ready");
});

test("drafting session, job, and draft routes carry their ids", () => {
  const draft = parseLocation("/drafting/26-0222/sessions/184/drafts/391/history");
  assert.equal(draft.view, "history");
  assert.equal(draft.sessionId, 184);
  assert.equal(draft.draftId, 391);
  const job = parseLocation("/drafting/26-0222/sessions/184/jobs/7");
  assert.deepEqual([job.view, job.sessionId, job.jobId], ["job", 184, 7]);
  assert.equal(parseLocation("/drafting/26-0222/sessions/184").view, "session");
  for (const view of ["goal", "plan", "questions", "package"]) {
    assert.equal(parseLocation(`/drafting/26-0222/sessions/184/${view}`).view, view);
  }
});

test("every drafting route builds back to the path it was read from", () => {
  for (const path of [
    "/drafting/26-0222",
    "/drafting/26-0222/new",
    "/drafting/26-0222/sessions/184",
    "/drafting/26-0222/sessions/184/plan",
    "/drafting/26-0222/sessions/184/jobs/7",
    "/drafting/26-0222/sessions/184/drafts/391",
    "/drafting/26-0222/sessions/184/drafts/391/validation",
  ]) {
    assert.equal(buildPath(parseLocation(path)), path);
  }
});

test("renumbering a case keeps the session and draft in the rewritten URL", () => {
  const route = parseLocation("/drafting/26-0111/sessions/184/drafts/391");
  assert.equal(canonicalPath(route, "26-0999"), "/drafting/26-0999/sessions/184/drafts/391");
});

test("a saved session reopens where its saved work is", () => {
  assert.equal(resumePath("26-0222", 184, { recommendedView: "goal" }), "/drafting/26-0222/sessions/184/goal");
  assert.equal(resumePath("26-0222", 184, { recommendedView: "plan" }), "/drafting/26-0222/sessions/184/plan");
  assert.equal(
    resumePath("26-0222", 184, { recommendedView: "draft", lastDraftId: 392, draftIds: [391, 392] }),
    "/drafting/26-0222/sessions/184/drafts/392",
  );
  assert.equal(resumePath("26-0222", 184, { recommendedView: "job", activeJobId: 7 }), "/drafting/26-0222/sessions/184/jobs/7");
  // Advice with nothing to back it falls back to a screen that only reads.
  assert.equal(resumePath("26-0222", 184, { recommendedView: "draft", draftIds: [] }), "/drafting/26-0222/sessions/184/goal");
});

test("triage assessments and chat threads have their own URLs", () => {
  assert.equal(paths.triageAssessment("26-0222", 52), "/triage/26-0222/assessments/52");
  assert.equal(paths.chatThread("26-0222", 42), "/chat/26-0222/threads/42");
  const thread = parseLocation("/chat/26-0222/threads/42");
  assert.deepEqual([thread.mode, thread.view, thread.threadId], ["case_chat", "thread", 42]);
  const assessment = parseLocation("/triage/26-0222/assessments/52");
  assert.deepEqual([assessment.mode, assessment.view, assessment.assessmentId], ["triage", "assessment", 52]);
});

test("a switched-off route family links to its collection and cannot be opened", async () => {
  const { setDisabledRouteFamilies } = await import("../src/routes/paths.js");
  setDisabledRouteFamilies(["chat-threads"]);
  try {
    assert.equal(paths.chatThread("26-0222", 42), "/chat/26-0222");
    assert.equal(parseLocation("/chat/26-0222/threads/42").found, false);
    assert.equal(paths.triageAssessment("26-0222", 52), "/triage/26-0222/assessments/52");
  } finally {
    setDisabledRouteFamilies([]);
  }
});

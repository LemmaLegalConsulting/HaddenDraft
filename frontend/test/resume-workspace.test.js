import assert from "node:assert/strict";
import test from "node:test";

import {
  blockDefaultsApply,
  draftScreenFor,
  hydrateNewWorkspace,
  hydrateSavedSession,
  stepForView,
} from "../src/state/resumeWorkspace.js";

const SAVED = {
  id: 184,
  mode: "draft_from_template",
  goal: "Answer and counterclaims",
  instructions: "Raise habitability.",
  template: { id: 12 },
  selectedTemplateIds: [12],
  selectedFactIds: [3, 5],
  selectedCuratedFacts: [{ text: "Tenant withheld rent." }],
  selectedBlockKeys: ["habitability"],
  selectedSourceResults: [{ id: "r1" }],
  templateData: { hearing_date: "May 1" },
  authorProfile: { displayName: "Ada Advocate" },
  draftPlan: { documents: [{ title: "Answer" }, { title: "Counterclaim" }] },
};

test("a saved session's choices win over every default", () => {
  const snapshot = hydrateSavedSession(SAVED, { defaultTemplateId: 99 });
  assert.equal(snapshot.selectedTemplateId, 12);
  assert.deepEqual(snapshot.selectedFactIds, [3, 5]);
  assert.deepEqual(snapshot.selectedBlockKeys, ["habitability"]);
  assert.deepEqual(snapshot.templateData, { hearing_date: "May 1" });
  assert.equal(snapshot.draftGoal, "Answer and counterclaims");
  assert.equal(snapshot.instructions, "Raise habitability.");
  assert.equal(snapshot.planningMode, "known");
  assert.equal(snapshot.allowMultipleDocuments, true);
  assert.equal(snapshot.templateChosen, true);
  assert.deepEqual(snapshot.authorProfile, { displayName: "Ada Advocate" });
});

test("an empty saved selection stays empty rather than becoming the defaults", () => {
  const snapshot = hydrateSavedSession({ ...SAVED, selectedFactIds: [], selectedBlockKeys: [] });
  assert.deepEqual(snapshot.selectedFactIds, []);
  assert.deepEqual(snapshot.selectedBlockKeys, []);
});

test("restoring copies, so editing the workspace never edits the loaded session", () => {
  const snapshot = hydrateSavedSession(SAVED);
  snapshot.selectedFactIds.push(9);
  snapshot.templateData.extra = "x";
  assert.deepEqual(SAVED.selectedFactIds, [3, 5]);
  assert.equal(SAVED.templateData.extra, undefined);
});

test("a session with no plan and no template falls back only where nothing was saved", () => {
  const snapshot = hydrateSavedSession({ id: 1, mode: "draft_from_scratch", draftPlan: {}, authorProfile: {} }, { defaultTemplateId: 99 });
  assert.equal(snapshot.draftPlan, null);
  assert.equal(snapshot.selectedTemplateId, 99);
  assert.equal(snapshot.templateChosen, false);
  assert.equal(snapshot.draftMode, "draft_from_scratch");
  assert.equal(snapshot.authorProfile, null);
  assert.equal(snapshot.planningMode, "suggest");
});

test("a new workspace starts from defaults and names no session", () => {
  const snapshot = hydrateNewWorkspace({ defaultTemplateId: 99, defaultFactIds: [1, 2] });
  assert.equal(snapshot.sessionId, null);
  assert.equal(snapshot.selectedTemplateId, 99);
  assert.deepEqual(snapshot.selectedFactIds, [1, 2]);
  assert.equal(snapshot.draftPlan, null);
});

test("restored block keys are kept until the advocate changes what they depend on", () => {
  const factIds = [3, 5];
  const restored = { matterId: "MID-1", selectedFactIds: factIds, templateId: 12 };
  assert.equal(blockDefaultsApply(restored, { matterId: "MID-1", selectedFactIds: factIds, templateId: 12 }), false);
  assert.equal(blockDefaultsApply(restored, { matterId: "MID-1", selectedFactIds: [3, 5, 7], templateId: 12 }), true);
  assert.equal(blockDefaultsApply(restored, { matterId: "MID-1", selectedFactIds: factIds, templateId: 13 }), true);
  assert.equal(blockDefaultsApply(null, { matterId: "MID-1", selectedFactIds: factIds, templateId: 12 }), true);
});

test("each drafting view shows its workflow step", () => {
  assert.equal(stepForView("plan"), "plan");
  assert.equal(stepForView("history"), "editor");
  assert.equal(stepForView("job"), "editor");
  assert.equal(stepForView("new"), null);
});

test("each drafting URL maps to one screen", () => {
  const at = (view, extra = {}) => ({ mode: "draft", view, caseKey: "26-0222", sessionId: 184, draftId: null, ...extra });
  assert.equal(draftScreenFor(at(null)), "list");
  assert.equal(draftScreenFor(at("new"), { localStep: "goal" }), "goal");
  assert.equal(draftScreenFor(at("session")), "resolving");
  assert.equal(draftScreenFor(at("plan"), { sessionReady: true }), "plan");
  assert.equal(draftScreenFor(at("job"), { sessionReady: true }), "job");
  assert.equal(draftScreenFor(at("history", { draftId: 391 }), { sessionReady: true, draftPresent: true }), "editor");
});

test("a saved screen waits for its own session, and a missing document says so", () => {
  const at = (view, extra = {}) => ({ mode: "draft", view, caseKey: "26-0222", sessionId: 184, draftId: null, ...extra });
  assert.equal(draftScreenFor(at("plan"), { sessionReady: false }), "session_pending");
  assert.equal(draftScreenFor(at("draft", { draftId: 999 }), { sessionReady: true, draftPresent: false }), "draft_missing");
  assert.equal(draftScreenFor({ mode: "triage", view: null }), null);
});

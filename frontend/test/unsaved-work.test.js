import assert from "node:assert/strict";
import test from "node:test";

import { checkpointFromWorkspace, planChanged, sessionChanges } from "../src/state/sessionCheckpoint.js";
import { hydrateSavedSession } from "../src/state/resumeWorkspace.js";
import { leavesSavedWork, saveStatus } from "../src/state/unsavedGuard.js";

const SESSION = {
  id: 184,
  mode: "draft_from_template",
  goal: "Answer",
  selectedFactIds: [3],
  selectedTemplateIds: [],
  templateData: {},
  draftPlan: { documents: [{ title: "Answer" }] },
  workflowOptions: {},
};

test("a freshly restored session has nothing unsaved", () => {
  const ws = hydrateSavedSession(SESSION);
  assert.deepEqual(sessionChanges(SESSION, ws), []);
  assert.equal(planChanged(SESSION, ws.draftPlan), false);
});

test("an edited goal or fact selection is unsaved", () => {
  const ws = { ...hydrateSavedSession(SESSION), draftGoal: "Answer and counterclaims", selectedFactIds: [3, 4] };
  assert.deepEqual(sessionChanges(SESSION, ws), ["goal", "selectedFactIds"]);
});

test("an edited plan is unsaved; an empty plan equals no plan", () => {
  assert.equal(planChanged(SESSION, { documents: [{ title: "Motion" }] }), true);
  assert.equal(planChanged({ ...SESSION, draftPlan: {} }, null), false);
});

test("a checkpoint names only the workspace's choices", () => {
  const payload = checkpointFromWorkspace({ ...hydrateSavedSession(SESSION), planningMode: "known", selectedTemplateId: "12" });
  assert.deepEqual(payload.selectedTemplateIds, [12]);
  assert.deepEqual(Object.keys(payload).sort(), [
    "goal", "instructions", "selectedBlockKeys", "selectedCuratedFacts", "selectedFactIds",
    "selectedSourceResults", "selectedTemplateIds", "templateData", "workflowOptions",
  ]);
});

test("saved workflow options come back as they were saved", () => {
  const ws = hydrateSavedSession({ ...SESSION, workflowOptions: { planningMode: "known", clarifyMissingFactsBeforeDraft: false } });
  assert.equal(ws.planningMode, "known");
  assert.equal(ws.clarifyMissingFactsBeforeDraft, false);
});

test("moving within one saved session is not leaving it", () => {
  assert.equal(leavesSavedWork("/drafting/26-0222/sessions/184/plan", "/drafting/26-0222/sessions/184/questions"), false);
  assert.equal(leavesSavedWork("/drafting/26-0222/sessions/184/drafts/1", "/drafting/26-0222/sessions/184/drafts/2"), false);
});

test("another session, case, or task is leaving it", () => {
  assert.equal(leavesSavedWork("/drafting/26-0222/sessions/184/plan", "/drafting/26-0222/sessions/185/plan"), true);
  assert.equal(leavesSavedWork("/drafting/26-0222/sessions/184/plan", "/drafting/26-0222"), true);
  assert.equal(leavesSavedWork("/drafting/26-0222/sessions/184/plan", "/triage/26-0222"), true);
});

test("the save status shows the most pressing state", () => {
  assert.equal(saveStatus({ dirty: true, conflict: true }), "conflict");
  assert.equal(saveStatus({ dirty: true, saving: true }), "saving");
  assert.equal(saveStatus({ dirty: true, failed: true }), "failed");
  assert.equal(saveStatus({ dirty: true }), "dirty");
  assert.equal(saveStatus({}), "saved");
});

test("an advice letter is its own piece of saved work", () => {
  assert.equal(leavesSavedWork("/advice-letters/26-0222/drafts/118", "/advice-letters/26-0222/drafts/118/history"), false);
  assert.equal(leavesSavedWork("/advice-letters/26-0222/drafts/118", "/advice-letters/26-0222/drafts/119"), true);
  assert.equal(leavesSavedWork("/advice-letters/26-0222/drafts/118", "/drafting/26-0222"), true);
});

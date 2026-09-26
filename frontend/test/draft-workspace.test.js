import assert from "node:assert/strict";
import test from "node:test";

import {
  activeDraft,
  draftWorkspaceReducer,
  initialDraftWorkspace,
} from "../src/state/draftWorkspace.js";

const motion = { id: 1, title: "Motion", sections: [], plainText: "Motion text." };
const order = { id: 2, title: "Proposed Order", sections: [], plainText: "Order text." };

function generated(drafts = [motion, order]) {
  return draftWorkspaceReducer(initialDraftWorkspace, { type: "documentsGenerated", drafts });
}

test("generating documents opens the first one and clears prior validation state", () => {
  const dirty = { ...initialDraftWorkspace, validationSummary: { remainingErrorCount: 2 }, dirtySinceValidation: true };

  const state = draftWorkspaceReducer(dirty, { type: "documentsGenerated", drafts: [motion, order] });

  assert.equal(activeDraft(state).id, motion.id);
  assert.equal(state.validationSummary, null);
  assert.equal(state.dirtySinceValidation, false);
});

test("editing the active document keeps the document list in step", () => {
  const state = draftWorkspaceReducer(generated(), {
    type: "documentPatched",
    patch: { plainText: "Edited motion." },
  });

  assert.equal(activeDraft(state).plainText, "Edited motion.");
  assert.equal(state.drafts.find((item) => item.id === motion.id).plainText, "Edited motion.");
  assert.equal(state.drafts.find((item) => item.id === order.id).plainText, "Order text.");
});

test("a server response for another document does not steal the editor", () => {
  const state = draftWorkspaceReducer(generated(), {
    type: "documentUpdated",
    draft: { ...order, plainText: "Regenerated order." },
  });

  assert.equal(state.activeDraftId, motion.id);
  assert.equal(state.drafts.find((item) => item.id === order.id).plainText, "Regenerated order.");
});

test("switching documents drops validation state that belongs to the previous one", () => {
  const validated = draftWorkspaceReducer(generated(), {
    type: "documentValidated",
    draft: { ...motion, validationFlags: [{ findingId: "W800-1" }] },
    validation: { remainingErrorCount: 0 },
  });

  const switched = draftWorkspaceReducer(validated, { type: "documentSelected", draftId: order.id });

  assert.equal(switched.activeDraftId, order.id);
  assert.equal(switched.validationSummary, null);
  assert.equal(switched.revisionPlan, null);
  assert.deepEqual(
    switched.drafts.find((item) => item.id === motion.id).validationFlags,
    [{ findingId: "W800-1" }],
    "the validated document keeps its findings",
  );
});

test("selecting an unknown or already active document changes nothing", () => {
  const state = generated();

  assert.equal(draftWorkspaceReducer(state, { type: "documentSelected", draftId: 99 }), state);
  assert.equal(draftWorkspaceReducer(state, { type: "documentSelected", draftId: motion.id }), state);
});

test("validation clears the unsaved-changes hint and editing sets it again", () => {
  const edited = draftWorkspaceReducer(generated(), { type: "documentEdited", draft: motion });
  assert.equal(edited.dirtySinceValidation, true);

  const validated = draftWorkspaceReducer(edited, {
    type: "documentValidated",
    draft: motion,
    validation: { remainingErrorCount: 0 },
  });

  assert.equal(validated.dirtySinceValidation, false);
  assert.deepEqual(validated.validationSummary, { remainingErrorCount: 0 });
});

test("reloading a session's documents keeps the one being edited open", () => {
  const state = draftWorkspaceReducer(generated(), { type: "documentSelected", draftId: order.id });

  const reloaded = draftWorkspaceReducer(state, { type: "documentsLoaded", drafts: [motion, order] });

  assert.equal(reloaded.activeDraftId, order.id);
});

test("revision plan items are edited in place and cleared once applied", () => {
  const loaded = draftWorkspaceReducer(generated(), {
    type: "revisionPlanLoaded",
    plan: { plan: [{ blockKey: "facts", include: true }, { blockKey: "argument", include: true }] },
  });

  const excluded = draftWorkspaceReducer(loaded, {
    type: "revisionPlanItemUpdated",
    blockKey: "argument",
    patch: { include: false },
  });
  assert.deepEqual(
    excluded.revisionPlan.plan.map((item) => item.include),
    [true, false],
  );

  const applied = draftWorkspaceReducer(excluded, {
    type: "revisionPlanApplied",
    draft: { ...motion, plainText: "Revised." },
    validation: { remainingErrorCount: 0 },
  });
  assert.equal(applied.revisionPlan, null);
  assert.equal(activeDraft(applied).plainText, "Revised.");
});

test("typing marks a document unsaved until the server acknowledges it", async () => {
  const { draftWorkspaceReducer, hasUnsavedDocuments, initialDraftWorkspace } = await import("../src/state/draftWorkspace.js");
  let state = draftWorkspaceReducer(initialDraftWorkspace, {
    type: "documentsLoaded",
    drafts: [{ id: 1, revision: 3, plainText: "a" }],
  });
  state = draftWorkspaceReducer(state, { type: "documentPatched", patch: { plainText: "ab" } });
  assert.equal(hasUnsavedDocuments(state), true);
  state = draftWorkspaceReducer(state, { type: "documentEdited", draft: { id: 1, revision: 4, plainText: "ab" } });
  assert.equal(hasUnsavedDocuments(state), false);
});

test("a refused save keeps the advocate's text and holds the server's beside it", async () => {
  const { draftWorkspaceReducer, initialDraftWorkspace } = await import("../src/state/draftWorkspace.js");
  let state = draftWorkspaceReducer(initialDraftWorkspace, { type: "documentsLoaded", drafts: [{ id: 1, revision: 3, plainText: "a" }] });
  state = draftWorkspaceReducer(state, { type: "documentPatched", patch: { plainText: "mine" } });
  state = draftWorkspaceReducer(state, { type: "documentConflict", draft: { id: 1, revision: 5, plainText: "theirs" } });
  assert.equal(state.drafts[0].plainText, "mine");
  assert.equal(state.conflict.server.plainText, "theirs");

  const theirs = draftWorkspaceReducer(state, { type: "conflictResolved", keep: "theirs" });
  assert.equal(theirs.drafts[0].plainText, "theirs");
  assert.deepEqual(theirs.unsavedDraftIds, []);

  const mine = draftWorkspaceReducer(state, { type: "conflictResolved", keep: "mine" });
  assert.equal(mine.drafts[0].plainText, "mine");
  assert.equal(mine.drafts[0].revision, 5);
  assert.deepEqual(mine.unsavedDraftIds, [1]);
  assert.equal(mine.conflict, null);
});

test("validation counts only when the server says it checked the text on screen", async () => {
  const { draftWorkspaceReducer, initialDraftWorkspace } = await import("../src/state/draftWorkspace.js");
  let state = draftWorkspaceReducer(initialDraftWorkspace, {
    type: "documentsLoaded",
    drafts: [{ id: 1, validation: { state: "current" } }, { id: 2, validation: { state: "stale" } }],
  });
  assert.deepEqual(state.validatedDraftIds, [1]);
  state = draftWorkspaceReducer(state, { type: "documentEdited", draft: { id: 1, validation: { state: "stale" } } });
  assert.deepEqual(state.validatedDraftIds, []);
});

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

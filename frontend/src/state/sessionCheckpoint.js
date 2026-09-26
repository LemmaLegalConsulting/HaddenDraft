// What of a saved drafting session is unsaved on screen, and what to send.
//
// The comparison is between two workspace snapshots built the same way -- one
// from the session as the server last returned it, one from what is on screen
// -- so a field the server never recorded cannot look "changed" just because
// the two sides spell its absence differently.

import { hydrateSavedSession } from "./resumeWorkspace.js";

// The workspace fields a checkpoint saves, as the server's API names them.
export function checkpointFromWorkspace(ws) {
  return {
    goal: ws.draftGoal || "",
    instructions: ws.instructions || ws.draftGoal || "",
    selectedFactIds: [...(ws.selectedFactIds || [])],
    selectedCuratedFacts: [...(ws.selectedCuratedFacts || [])],
    selectedSourceResults: [...(ws.sourceResults || [])],
    selectedBlockKeys: [...(ws.selectedBlockKeys || [])],
    selectedTemplateIds: ws.planningMode === "known" && ws.selectedTemplateId ? [Number(ws.selectedTemplateId)] : [],
    templateData: { ...(ws.templateData || {}) },
    workflowOptions: {
      planningMode: ws.planningMode || "suggest",
      allowMultipleDocuments: Boolean(ws.allowMultipleDocuments),
      clarifyMissingFactsBeforeDraft: ws.clarifyMissingFactsBeforeDraft !== false,
    },
  };
}

// Fields the advocate edits directly on a saved session's screens. Others --
// instructions rebuilt from the goal, block keys recomputed from facts -- are
// saved with a checkpoint but do not by themselves make a session "unsaved".
const TRACKED = ["goal", "selectedFactIds", "selectedCuratedFacts", "selectedSourceResults", "selectedTemplateIds", "templateData", "workflowOptions"];

const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

export function sessionChanges(session, ws, { defaultTemplateId = null } = {}) {
  if (!session) return [];
  const saved = checkpointFromWorkspace(hydrateSavedSession(session, { defaultTemplateId }));
  const current = checkpointFromWorkspace(ws);
  return TRACKED.filter((field) => !same(saved[field], current[field]));
}

function normalizedPlan(plan) {
  return plan && Object.keys(plan).length ? plan : null;
}

export function planChanged(session, draftPlan) {
  if (!session) return false;
  return !same(normalizedPlan(session.draftPlan), normalizedPlan(draftPlan));
}

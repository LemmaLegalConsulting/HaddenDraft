/**
 * State for the documents a drafting session produced.
 *
 * A plan can produce several documents, one of which is on screen. The list and
 * the active document have to move together or an edit is lost when the user
 * switches documents, and validation state belongs to the document that
 * produced it. Keeping those rules in one reducer makes them testable instead
 * of spread across the workspace component.
 */

export const initialDraftWorkspace = {
  drafts: [],
  activeDraftId: null,
  validationSummary: null,
  dirtySinceValidation: false,
  revisionPlan: null,
  // Documents whose stored findings describe their current text. An empty
  // findings list means "clean" only for these; for the rest it means "never
  // checked" or "checked an older version".
  validatedDraftIds: [],
  // Documents with edits on screen the server has not acknowledged yet.
  unsavedDraftIds: [],
  // A save refused because the document changed elsewhere:
  // { draftId, server } -- the local edits stay until the advocate chooses.
  conflict: null,
};

// Validation the server recorded against the revision now on screen.
function currentlyValidated(drafts) {
  return drafts.filter((item) => item.validation?.state === "current").map((item) => item.id);
}

function without(ids, id) {
  return ids.filter((item) => item !== id);
}

export function hasUnsavedDocuments(state) {
  return state.unsavedDraftIds.length > 0;
}

export function activeDraft(state) {
  return state.drafts.find((item) => item.id === state.activeDraftId) || null;
}

function replaceDraft(drafts, nextDraft) {
  return drafts.map((item) => (item.id === nextDraft.id ? nextDraft : item));
}

function withValidated(state, draft) {
  if (!draft || state.validatedDraftIds.includes(draft.id)) return state.validatedDraftIds;
  return [...state.validatedDraftIds, draft.id];
}

export function draftWorkspaceReducer(state, action) {
  switch (action.type) {
    case "documentsGenerated": {
      const drafts = action.drafts || [];
      return {
        ...initialDraftWorkspace,
        drafts,
        activeDraftId: drafts[0]?.id ?? null,
        validatedDraftIds: currentlyValidated(drafts),
      };
    }
    case "documentsLoaded": {
      // Recovering a session's documents must not discard the one being edited.
      const drafts = action.drafts || [];
      const stillPresent = drafts.some((item) => item.id === state.activeDraftId);
      return {
        ...state,
        drafts,
        activeDraftId: stillPresent ? state.activeDraftId : drafts[0]?.id ?? null,
        validatedDraftIds: currentlyValidated(drafts),
        unsavedDraftIds: [],
        conflict: null,
      };
    }
    case "documentUpdated": {
      if (!action.draft) return state;
      return { ...state, drafts: replaceDraft(state.drafts, action.draft) };
    }
    case "documentPatched": {
      const current = activeDraft(state);
      if (!current) return state;
      const next = { ...current, ...action.patch };
      return {
        ...state,
        drafts: replaceDraft(state.drafts, next),
        unsavedDraftIds: state.unsavedDraftIds.includes(current.id) ? state.unsavedDraftIds : [...state.unsavedDraftIds, current.id],
      };
    }
    case "documentSelected": {
      if (!state.drafts.some((item) => item.id === action.draftId)) return state;
      if (action.draftId === state.activeDraftId) return state;
      // Validation and revision state describe the document that produced them.
      return {
        ...state,
        activeDraftId: action.draftId,
        validationSummary: null,
        dirtySinceValidation: false,
        revisionPlan: null,
      };
    }
    case "documentValidated": {
      return {
        ...state,
        drafts: action.draft ? replaceDraft(state.drafts, action.draft) : state.drafts,
        unsavedDraftIds: action.draft ? without(state.unsavedDraftIds, action.draft.id) : state.unsavedDraftIds,
        validationSummary: action.validation || null,
        dirtySinceValidation: false,
        validatedDraftIds: withValidated(state, action.draft),
      };
    }
    case "documentEdited": {
      // The server's copy after a save: the edits it carries are acknowledged.
      if (!action.draft) return { ...state, dirtySinceValidation: true };
      const saved = action.draft;
      const stillValid = saved.validation ? saved.validation.state === "current" : state.validatedDraftIds.includes(saved.id);
      return {
        ...state,
        drafts: replaceDraft(state.drafts, saved),
        dirtySinceValidation: true,
        unsavedDraftIds: without(state.unsavedDraftIds, saved.id),
        validatedDraftIds: stillValid ? state.validatedDraftIds : without(state.validatedDraftIds, saved.id),
        conflict: state.conflict?.draftId === saved.id ? null : state.conflict,
      };
    }
    case "documentConflict": {
      // Keep what the advocate typed; hold the server's version beside it.
      if (!action.draft) return state;
      return { ...state, conflict: { draftId: action.draft.id, server: action.draft } };
    }
    case "conflictResolved": {
      const conflict = state.conflict;
      if (!conflict) return state;
      if (action.keep === "theirs") {
        return {
          ...state,
          drafts: replaceDraft(state.drafts, conflict.server),
          unsavedDraftIds: without(state.unsavedDraftIds, conflict.draftId),
          conflict: null,
        };
      }
      // Keep mine: the local text now answers the server's latest revision,
      // so the next save deliberately replaces it -- a choice, not an accident.
      const local = state.drafts.find((item) => item.id === conflict.draftId);
      if (!local) return { ...state, conflict: null };
      return {
        ...state,
        drafts: replaceDraft(state.drafts, { ...local, revision: conflict.server.revision }),
        conflict: null,
      };
    }
    case "revisionPlanLoaded":
      return { ...state, revisionPlan: action.plan || null };
    case "revisionPlanItemUpdated": {
      if (!state.revisionPlan) return state;
      return {
        ...state,
        revisionPlan: {
          ...state.revisionPlan,
          plan: state.revisionPlan.plan.map((item) => (
            item.blockKey === action.blockKey ? { ...item, ...action.patch } : item
          )),
        },
      };
    }
    case "revisionPlanApplied":
      return {
        ...state,
        drafts: action.draft ? replaceDraft(state.drafts, action.draft) : state.drafts,
        validationSummary: action.validation || null,
        dirtySinceValidation: false,
        revisionPlan: null,
        validatedDraftIds: withValidated(state, action.draft),
      };
    case "reset":
      return initialDraftWorkspace;
    default:
      return state;
  }
}

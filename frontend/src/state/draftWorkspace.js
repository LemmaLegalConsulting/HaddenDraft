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
  // Documents validated at least once. An empty findings list means "clean"
  // only for these; for the rest it means "never checked".
  validatedDraftIds: [],
};

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
      return { ...state, drafts: replaceDraft(state.drafts, next) };
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
        validationSummary: action.validation || null,
        dirtySinceValidation: false,
        validatedDraftIds: withValidated(state, action.draft),
      };
    }
    case "documentEdited": {
      const drafts = action.draft ? replaceDraft(state.drafts, action.draft) : state.drafts;
      return { ...state, drafts, dirtySinceValidation: true };
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

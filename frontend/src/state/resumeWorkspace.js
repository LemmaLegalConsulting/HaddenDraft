// Turning a saved drafting session back into the drafting workspace.
//
// The workspace starts from defaults -- the case's default facts, the default
// template, an empty goal -- and a new session is built from there. A saved
// session is the opposite case: what the advocate chose was persisted, and
// every default must yield to it. Keeping the two starts as separate functions
// makes that difference explicit and testable, instead of an accident of which
// effect happened to run last.

// Which workflow step a drafting URL's view shows.
export const STEP_FOR_VIEW = {
  goal: "goal",
  plan: "plan",
  questions: "questions",
  job: "editor",
  draft: "editor",
  history: "editor",
  validation: "editor",
  package: "editor",
};

export function stepForView(view) {
  return STEP_FOR_VIEW[view] || null;
}

// The workspace for `/drafting/<case>/new`: nothing saved, defaults apply.
export function hydrateNewWorkspace({ defaultTemplateId = null, defaultFactIds = [] } = {}) {
  return {
    sessionId: null,
    draftMode: "draft_from_template",
    draftGoal: "",
    instructions: "",
    planningMode: "suggest",
    allowMultipleDocuments: false,
    clarifyMissingFactsBeforeDraft: true,
    selectedTemplateId: defaultTemplateId,
    templateChosen: false,
    selectedFactIds: [...defaultFactIds],
    selectedCuratedFacts: [],
    selectedBlockKeys: [],
    templateData: {},
    sourceResults: [],
    draftPlan: null,
    authorProfile: null,
  };
}

function hasContent(value) {
  if (!value) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return true;
}

// The workspace a saved session describes. Every field comes from the
// session; a default is used only where the session saved nothing at all.
export function hydrateSavedSession(session, { defaultTemplateId = null } = {}) {
  const plan = hasContent(session.draftPlan) ? session.draftPlan : null;
  const selectedTemplateIds = session.selectedTemplateIds || [];
  const templateId = session.template?.id ?? selectedTemplateIds[0] ?? null;
  const plannedDocuments = plan?.documents || [];
  // Saved options win; a session saved before they were recorded gets them
  // inferred from what it did save.
  const options = session.workflowOptions || {};
  return {
    sessionId: session.id,
    draftMode: session.mode === "draft_from_scratch" ? "draft_from_scratch" : "draft_from_template",
    draftGoal: session.goal || "",
    instructions: session.instructions || session.goal || "",
    // A session saved with a chosen template was planned around it.
    planningMode: options.planningMode ?? (selectedTemplateIds.length ? "known" : "suggest"),
    allowMultipleDocuments: options.allowMultipleDocuments ?? plannedDocuments.length > 1,
    clarifyMissingFactsBeforeDraft: options.clarifyMissingFactsBeforeDraft ?? true,
    selectedTemplateId: templateId ?? defaultTemplateId,
    templateChosen: templateId != null,
    selectedFactIds: [...(session.selectedFactIds || [])],
    selectedCuratedFacts: [...(session.selectedCuratedFacts || [])],
    selectedBlockKeys: [...(session.selectedBlockKeys || [])],
    templateData: { ...(session.templateData || {}) },
    sourceResults: [...(session.selectedSourceResults || [])],
    draftPlan: plan,
    // Null keeps the signed-in author's profile; a saved one replaces it.
    authorProfile: hasContent(session.authorProfile) ? session.authorProfile : null,
  };
}

// Whether the template's default block selection may be recomputed. It may
// not while the workspace still shows exactly what a saved session restored:
// the saved block keys are the advocate's choice, and recomputing them from
// facts and template would silently replace it.
export function blockDefaultsApply(restored, { matterId, selectedFactIds, templateId }) {
  if (!restored) return true;
  return !(
    restored.matterId === matterId &&
    restored.selectedFactIds === selectedFactIds &&
    restored.templateId === templateId
  );
}

// What the drafting area shows for a URL:
//   "list"            the case's saved sessions (/drafting/<case>)
//   "goal" | "plan" | "questions" | "editor"   a workflow step
//   "resolving"       /sessions/<id>, waiting to be sent to its checkpoint
//   "session_pending" the named session is still loading, or did not open
//   "job"             reconnecting to a generation already running
//   "draft_missing"   the session opened but has no such document
//
// A saved-session screen is drawn only once that session is the one in
// memory, so one session's plan is never shown under another's URL.
export function draftScreenFor(route, { localStep = "goal", sessionReady = false, draftPresent = false } = {}) {
  if (!route || route.mode !== "draft") return null;
  if (route.view === null) return "list";
  if (route.view === "new") return localStep;
  if (route.view === "session") return "resolving";
  if (!sessionReady) return "session_pending";
  if (route.view === "job") return "job";
  if (route.draftId != null && !draftPresent) return "draft_missing";
  return stepForView(route.view);
}

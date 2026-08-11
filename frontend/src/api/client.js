const API_BASE = import.meta.env.VITE_API_BASE || "/api";

function getCookie(name) {
  const match = document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : "";
}

async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const unsafe = !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method);
  const csrfToken = unsafe ? getCookie("csrftoken") : "";

  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    try {
      const payload = JSON.parse(text);
      throw new Error(payload.error || `Request failed: ${response.status}`);
    } catch (err) {
      if (err instanceof SyntaxError) {
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("text/html") || /^\s*</.test(text)) {
          throw new Error(`Request failed: ${response.status}`);
        }
        throw new Error(text || `Request failed: ${response.status}`);
      }
      throw err;
    }
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return response;
  }
  return response.json();
}

export const api = {
  bootstrap: () => request("/bootstrap/"),
  me: () => request("/auth/me/"),
  authorProfile: () => request("/author-profile/"),
  updateAuthorProfile: (payload) => request("/author-profile/", { method: "PATCH", body: JSON.stringify(payload) }),
  login: (payload) => request("/auth/login/", { method: "POST", body: JSON.stringify(payload) }),
  logout: () => request("/auth/logout/", { method: "POST" }),
  startOffice365Login: () => request("/auth/office365/start/"),
  cases: ({ query = "", status = "", assigned = "", problem = "", sort = "", limit = 0, offset = 0 } = {}) => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (status) params.set("status", status);
    if (assigned) params.set("assigned", assigned);
    if (problem) params.set("problem", problem);
    if (sort) params.set("sort", sort);
    if (limit) params.set("limit", String(limit));
    if (offset) params.set("offset", String(offset));
    const search = params.toString();
    return request(`/cases/${search ? `?${search}` : ""}`);
  },
  createManualCase: (formData) => request("/cases/", { method: "POST", body: formData }),
  updateManualCase: (matterId, payload) =>
    request(`/cases/${matterId}/`, { method: "PATCH", body: JSON.stringify(payload) }),
  legalserverDraftIntakePreview: (matterId) =>
    request(`/cases/${matterId}/`, { method: "POST", body: JSON.stringify({ action: "legalserver_draft_intake" }) }),
  triageRubrics: () => request("/triage/rubrics/"),
  caseTriage: (matterId) => request(`/cases/${matterId}/triage/`),
  runCaseTriage: (matterId, payload) =>
    request(`/cases/${matterId}/triage/`, { method: "POST", body: JSON.stringify(payload) }),
  connectLegalServer: (payload) => request("/legalserver/account/", { method: "POST", body: JSON.stringify(payload) }),
  disconnectLegalServer: () => request("/legalserver/account/", { method: "DELETE" }),
  caseDetail: (matterId) => request(`/cases/${matterId}/`),
  caseChatHistory: (matterId, threadId) => request(`/cases/${matterId}/chat/${threadId ? `?threadId=${threadId}` : ""}`),
  newCaseChat: (matterId) => request(`/cases/${matterId}/chat/`, { method: "POST", body: JSON.stringify({ action: "new_thread" }) }),
  clearCaseChatHistory: (matterId) => request(`/cases/${matterId}/chat/`, { method: "DELETE" }),
  caseChat: (matterId, payload) => request(`/cases/${matterId}/chat/`, { method: "POST", body: JSON.stringify(payload) }),
  caseLegalServer: (matterId) => request(`/cases/${matterId}/legalserver/`),
  saveCaseNoteToLegalServer: (matterId, payload) =>
    request(`/cases/${matterId}/legalserver/casenote/`, { method: "POST", body: JSON.stringify(payload) }),
  saveDocumentToLegalServer: (matterId, formData) =>
    request(`/cases/${matterId}/legalserver/document/`, { method: "POST", body: formData }),
  caseDocuments: (matterId) => request(`/cases/${matterId}/documents/`),
  caseMaterials: (matterId) => request(`/cases/${matterId}/materials/`),
  customFields: (matterId) => request(`/cases/${matterId}/custom-fields/`),
  fetchCustomFields: (matterId, payload) =>
    request(`/cases/${matterId}/custom-fields/fetch/`, { method: "POST", body: JSON.stringify(payload) }),
  caseFacts: (matterId) => request(`/cases/${matterId}/facts/`),
  recommendCaseFacts: (matterId) => request(`/cases/${matterId}/facts/recommend/`, { method: "POST" }),
  createCaseFact: (matterId, payload) =>
    request(`/cases/${matterId}/facts/`, { method: "POST", body: JSON.stringify(payload) }),
  uploadCaseFactDocument: (matterId, formData) =>
    request(`/cases/${matterId}/facts/`, { method: "POST", body: formData }),
  caseDocumentContext: (matterId, documentId, payload) =>
    request(`/cases/${matterId}/documents/${documentId}/context/`, { method: "POST", body: JSON.stringify(payload) }),
  caseDocumentFileUrl: (matterId, documentId) =>
    `${API_BASE}/cases/${encodeURIComponent(matterId)}/documents/${encodeURIComponent(documentId)}/file/`,
  candidateIssues: (matterId) => request(`/cases/${matterId}/candidate-issues/`),
  runIssueSelection: (matterId, payload) =>
    request(`/cases/${matterId}/run-issue-selection/`, { method: "POST", body: JSON.stringify(payload) }),
  reviewCandidateIssue: (issueId, payload) =>
    request(`/candidate-issues/${issueId}/review/`, { method: "POST", body: JSON.stringify(payload) }),
  modes: () => request("/modes/"),
  templates: () => request("/templates/"),
  userResources: () => request("/user-resources/"),
  createUserResource: (formData) => request("/user-resources/", { method: "POST", body: formData }),
  caselawDecision: (decisionId) => request(`/caselaw/decisions/${decisionId}/`),
  caselawDecisionPdfUrl: (decisionId) => `${API_BASE}/caselaw/decisions/${decisionId}/pdf/`,
  caselawBrowse: (params = {}) => request(`/caselaw/browse/${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== ""))}` : ""}`),
  // Facet narrowing repeats a parameter name per selected value, so the catalog
  // takes pairs rather than an object.
  caselawCatalog: (params = []) => request(`/caselaw/catalog/${params.length ? `?${new URLSearchParams(params)}` : ""}`),
  library: () => request("/library/"),
  libraryDocument: (documentSlug, query = "") =>
    request(`/library/${encodeURIComponent(documentSlug)}/${query ? `?${new URLSearchParams({ q: query })}` : ""}`),
  contentSource: (documentSlug, chunkId) => request(`/sources/content/${encodeURIComponent(documentSlug)}/${encodeURIComponent(chunkId)}/`),
  contentSourcePdfUrl: (documentSlug, chunkId, page) =>
    `${API_BASE}/sources/content/${encodeURIComponent(documentSlug)}/${encodeURIComponent(chunkId)}/pdf/${page ? `#page=${page}` : ""}`,
  researchHistory: (threadId) => request(`/research/${threadId ? `?threadId=${threadId}` : ""}`),
  newResearchChat: () => request("/research/", { method: "POST", body: JSON.stringify({ action: "new_thread" }) }),
  clearResearchHistory: () => request("/research/", { method: "DELETE" }),
  research: (payload) => request("/research/", { method: "POST", body: JSON.stringify(payload) }),
  createTemplateFromExample: (payload) =>
    request("/templates/from-example/", { method: "POST", body: JSON.stringify(payload) }),
  createSession: (payload) => request("/drafting-sessions/", { method: "POST", body: JSON.stringify(payload) }),
  advanceSession: (sessionId, payload) =>
    request(`/drafting-sessions/${sessionId}/advance/`, { method: "POST", body: JSON.stringify(payload) }),
  recommendSessionFacts: (sessionId, payload = { apply: true }) =>
    request(`/drafting-sessions/${sessionId}/recommend-facts/`, { method: "POST", body: JSON.stringify(payload) }),
  recommendSessionGoals: (sessionId, payload = { limit: 5 }) =>
    request(`/drafting-sessions/${sessionId}/recommend-goals/`, { method: "POST", body: JSON.stringify(payload) }),
  recommendSessionSupport: (sessionId, payload = { apply: true }) =>
    request(`/drafting-sessions/${sessionId}/recommend-support/`, { method: "POST", body: JSON.stringify(payload) }),
  sessionOutline: (sessionId) => request(`/drafting-sessions/${sessionId}/outline/`),
  approveSessionOutline: (sessionId, payload = {}) =>
    request(`/drafting-sessions/${sessionId}/outline/`, { method: "POST", body: JSON.stringify(payload) }),
  generateDraftPlan: (sessionId, payload = {}) =>
    request(`/drafting-sessions/${sessionId}/plan/`, { method: "POST", body: JSON.stringify(payload) }),
  updateDraftPlan: (sessionId, payload = {}) =>
    request(`/drafting-sessions/${sessionId}/plan/`, { method: "PATCH", body: JSON.stringify(payload) }),
  updateSessionTemplateData: (sessionId, templateData) =>
    request(`/drafting-sessions/${sessionId}/template-data/`, { method: "POST", body: JSON.stringify({ templateData }) }),
  sessionDrafts: (sessionId) => request(`/drafting-sessions/${sessionId}/drafts/`),
  sessionPackage: (sessionId) => request(`/drafting-sessions/${sessionId}/package/`),
  generatePlanDrafts: (sessionId, payload = {}) =>
    request(`/drafting-sessions/${sessionId}/drafts/`, { method: "POST", body: JSON.stringify(payload) }),
  generateDraft: (sessionId) => request(`/drafting-sessions/${sessionId}/draft/`, { method: "POST" }),
  updateDraft: (draftId, payload) => request(`/drafts/${draftId}/`, { method: "PATCH", body: JSON.stringify(payload) }),
  draftComponents: (draftId) => request(`/drafts/${draftId}/components/`),
  draftOperations: (draftId) => request(`/drafts/${draftId}/operations/`),
  proposeDraftOperation: (draftId, payload) =>
    request(`/drafts/${draftId}/operations/`, { method: "POST", body: JSON.stringify(payload) }),
  decideDraftOperation: (draftId, operationId, payload) =>
    request(`/drafts/${draftId}/operations/${operationId}/decision/`, { method: "POST", body: JSON.stringify(payload) }),
  regenerateDraftBlock: (draftId, blockKey, payload) =>
    request(`/drafts/${draftId}/blocks/${blockKey}/regenerate/`, { method: "POST", body: JSON.stringify(payload) }),
  validateDraft: (draftId) => request(`/drafts/${draftId}/validate/`, { method: "POST" }),
  draftRevisionPlan: (draftId) => request(`/drafts/${draftId}/revision-plan/`, { method: "POST" }),
  applyDraftRevision: (draftId, plan) =>
    request(`/drafts/${draftId}/revision/`, { method: "POST", body: JSON.stringify({ plan }) }),
  // The export is a download, so the LegalServer opt-out rides along as a query
  // parameter and the outcome comes back in response headers.
  exportDraftUrl: (draftId, { saveToLegalServer = true } = {}) =>
    `${API_BASE}/drafts/${draftId}/export/${saveToLegalServer ? "" : "?saveToLegalServer=0"}`,
  exportDraft: (draftId, options = {}) => request(api.exportDraftUrl(draftId, options).replace(API_BASE, "")),

  adviceLetterSections: ({ region = "", letterType = "brief_advice", reviewedOnly = false } = {}) =>
    request(`/advice-letters/sections/?${new URLSearchParams({ region, letterType, reviewedOnly: reviewedOnly ? "1" : "" })}`),
  adviceLetterAddressing: (matterId) =>
    request(`/advice-letters/addressing/?${new URLSearchParams({ matterId })}`),
  adviceLetterRecommendations: (payload) =>
    request("/advice-letters/recommend/", { method: "POST", body: JSON.stringify(payload) }),
  adviceLetterPreview: (payload) =>
    request("/advice-letters/preview/", { method: "POST", body: JSON.stringify(payload) }),
  adviceLetterExport: (payload) =>
    request("/advice-letters/export/", { method: "POST", body: JSON.stringify(payload) }),
  adviceLetterDraft: (payload) =>
    request("/advice-letters/drafts/", { method: "POST", body: JSON.stringify(payload) }),
  adviceLetterDraftExport: (draftId, payload = {}) =>
    request(`/advice-letters/drafts/${draftId}/export/`, { method: "POST", body: JSON.stringify(payload) }),
  adminUrl: () => "/admin/",
};

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
  cases: (query = "") => request(`/cases/${query ? `?${new URLSearchParams({ q: query })}` : ""}`),
  createManualCase: (formData) => request("/cases/", { method: "POST", body: formData }),
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
  caseDocuments: (matterId) => request(`/cases/${matterId}/documents/`),
  caseFacts: (matterId) => request(`/cases/${matterId}/facts/`),
  recommendCaseFacts: (matterId) => request(`/cases/${matterId}/facts/recommend/`, { method: "POST" }),
  createCaseFact: (matterId, payload) =>
    request(`/cases/${matterId}/facts/`, { method: "POST", body: JSON.stringify(payload) }),
  uploadCaseFactDocument: (matterId, formData) =>
    request(`/cases/${matterId}/facts/`, { method: "POST", body: formData }),
  caseDocumentContext: (matterId, documentId, payload) =>
    request(`/cases/${matterId}/documents/${documentId}/context/`, { method: "POST", body: JSON.stringify(payload) }),
  candidateIssues: (matterId) => request(`/cases/${matterId}/candidate-issues/`),
  runIssueSelection: (matterId, payload) =>
    request(`/cases/${matterId}/run-issue-selection/`, { method: "POST", body: JSON.stringify(payload) }),
  reviewCandidateIssue: (issueId, payload) =>
    request(`/candidate-issues/${issueId}/review/`, { method: "POST", body: JSON.stringify(payload) }),
  modes: () => request("/modes/"),
  templates: () => request("/templates/"),
  userResources: () => request("/user-resources/"),
  createUserResource: (formData) => request("/user-resources/", { method: "POST", body: formData }),
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
  recommendSessionSupport: (sessionId, payload = { apply: true }) =>
    request(`/drafting-sessions/${sessionId}/recommend-support/`, { method: "POST", body: JSON.stringify(payload) }),
  sessionOutline: (sessionId) => request(`/drafting-sessions/${sessionId}/outline/`),
  approveSessionOutline: (sessionId, payload = {}) =>
    request(`/drafting-sessions/${sessionId}/outline/`, { method: "POST", body: JSON.stringify(payload) }),
  generateDraft: (sessionId) => request(`/drafting-sessions/${sessionId}/draft/`, { method: "POST" }),
  updateDraft: (draftId, payload) => request(`/drafts/${draftId}/`, { method: "PATCH", body: JSON.stringify(payload) }),
  regenerateDraftBlock: (draftId, blockKey, payload) =>
    request(`/drafts/${draftId}/blocks/${blockKey}/regenerate/`, { method: "POST", body: JSON.stringify(payload) }),
  validateDraft: (draftId) => request(`/drafts/${draftId}/validate/`, { method: "POST" }),
  exportDraftUrl: (draftId) => `${API_BASE}/drafts/${draftId}/export/`,
  adminUrl: () => "/admin/",
};

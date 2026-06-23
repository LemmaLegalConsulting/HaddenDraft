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
      "Content-Type": "application/json",
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
  login: (payload) => request("/auth/login/", { method: "POST", body: JSON.stringify(payload) }),
  logout: () => request("/auth/logout/", { method: "POST" }),
  startOffice365Login: () => request("/auth/office365/start/"),
  cases: (query = "") => request(`/cases/${query ? `?${new URLSearchParams({ q: query })}` : ""}`),
  connectLegalServer: (payload) => request("/legalserver/account/", { method: "POST", body: JSON.stringify(payload) }),
  disconnectLegalServer: () => request("/legalserver/account/", { method: "DELETE" }),
  caseDetail: (matterId) => request(`/cases/${matterId}/`),
  caseChat: (matterId, payload) => request(`/cases/${matterId}/chat/`, { method: "POST", body: JSON.stringify(payload) }),
  modes: () => request("/modes/"),
  templates: () => request("/templates/"),
  research: (payload) => request("/research/", { method: "POST", body: JSON.stringify(payload) }),
  createTemplateFromExample: (payload) =>
    request("/templates/from-example/", { method: "POST", body: JSON.stringify(payload) }),
  createSession: (payload) => request("/drafting-sessions/", { method: "POST", body: JSON.stringify(payload) }),
  advanceSession: (sessionId, payload) =>
    request(`/drafting-sessions/${sessionId}/advance/`, { method: "POST", body: JSON.stringify(payload) }),
  generateDraft: (sessionId) => request(`/drafting-sessions/${sessionId}/draft/`, { method: "POST" }),
  updateDraft: (draftId, payload) => request(`/drafts/${draftId}/`, { method: "PATCH", body: JSON.stringify(payload) }),
  validateDraft: (draftId) => request(`/drafts/${draftId}/validate/`, { method: "POST" }),
  exportDraftUrl: (draftId) => `${API_BASE}/drafts/${draftId}/export/`,
  adminUrl: () => "/admin/",
};

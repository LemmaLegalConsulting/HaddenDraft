// Application URLs: the only place they are built or read.
//
// Routes are task first, case second: `/drafting/26-0222`, not
// `/cases/26-0222/drafting`. The case segment is the matter's `routeCaseKey`,
// a readable lookup alias the server resolves and access-checks; it is never
// the matter's identity, and nothing here decides whether a case exists.
//
// Nothing outside this module interpolates a path. A component that needs a
// link asks for one here, so a URL shape changes in one place and a case number
// is always encoded the same way.

// Sidebar mode id -> first path segment. The server's sign-in return check
// (backend/apps/core/return_paths.py) lists the same roots.
export const TASK_ROOTS = {
  case: "cases",
  triage: "triage",
  case_chat: "chat",
  research: "research",
  advice_letter: "advice-letters",
  draft: "drafting",
  template_fill: "template-fill",
  argument_gym: "argument-gym",
};

const MODE_BY_ROOT = Object.fromEntries(Object.entries(TASK_ROOTS).map(([mode, root]) => [root, mode]));

// Tasks that act on one case and carry it in the URL. Research and the
// argument gym stand on their own; a case, when they use one, is context.
export const CASE_SCOPED_MODES = new Set(["case", "triage", "case_chat", "advice_letter", "draft", "template_fill"]);

const encodeKey = (caseKey) => encodeURIComponent(String(caseKey));

// Every screen this version can open, as { mode, view, pattern }. A pattern is
// the path after the task root: ":caseKey" is a case's route key, ":…Id" a
// positive integer, anything else literal. One table drives both reading and
// building URLs, so the two can never disagree about a shape.
export const ROUTES = [
  { mode: "case", view: null, pattern: [] },
  { mode: "case", view: null, pattern: [":caseKey"] },
  { mode: "draft", view: null, pattern: [] },
  { mode: "draft", view: null, pattern: [":caseKey"] },
  { mode: "draft", view: "new", pattern: [":caseKey", "new"] },
  { mode: "draft", view: "session", pattern: [":caseKey", "sessions", ":sessionId"] },
  { mode: "draft", view: "goal", pattern: [":caseKey", "sessions", ":sessionId", "goal"] },
  { mode: "draft", view: "plan", pattern: [":caseKey", "sessions", ":sessionId", "plan"] },
  { mode: "draft", view: "questions", pattern: [":caseKey", "sessions", ":sessionId", "questions"] },
  { mode: "draft", view: "package", pattern: [":caseKey", "sessions", ":sessionId", "package"] },
  { mode: "draft", view: "job", pattern: [":caseKey", "sessions", ":sessionId", "jobs", ":jobId"] },
  { mode: "draft", view: "draft", pattern: [":caseKey", "sessions", ":sessionId", "drafts", ":draftId"] },
  { mode: "draft", view: "history", pattern: [":caseKey", "sessions", ":sessionId", "drafts", ":draftId", "history"] },
  { mode: "draft", view: "validation", pattern: [":caseKey", "sessions", ":sessionId", "drafts", ":draftId", "validation"] },
  { mode: "triage", view: null, pattern: [] },
  { mode: "triage", view: null, pattern: [":caseKey"] },
  { mode: "case_chat", view: null, pattern: [] },
  { mode: "case_chat", view: null, pattern: [":caseKey"] },
  { mode: "template_fill", view: null, pattern: [] },
  { mode: "template_fill", view: null, pattern: [":caseKey"] },
  { mode: "advice_letter", view: null, pattern: [] },
  { mode: "advice_letter", view: null, pattern: [":caseKey"] },
  { mode: "research", view: null, pattern: [] },
  { mode: "research", view: "search", pattern: ["search"] },
  { mode: "argument_gym", view: null, pattern: [] },
];

const ID_PARAMS = ["sessionId", "jobId", "draftId", "threadId", "assessmentId", "workspaceId", "runId"];

function decodeSegment(segment) {
  try {
    return decodeURIComponent(segment);
  } catch {
    return null;
  }
}

function matchPattern(pattern, segments) {
  if (pattern.length !== segments.length) return null;
  const params = {};
  for (let index = 0; index < pattern.length; index += 1) {
    const token = pattern[index];
    const segment = segments[index];
    if (!token.startsWith(":")) {
      if (token !== segment) return null;
      continue;
    }
    const name = token.slice(1);
    if (name === "caseKey") {
      const value = decodeSegment(segment);
      if (!value || !value.trim()) return null;
      params.caseKey = value;
    } else {
      if (!/^[1-9][0-9]{0,15}$/.test(segment)) return null;
      params[name] = Number(segment);
    }
  }
  return params;
}

function emptyRoute(mode, view) {
  const route = { mode, caseKey: null, view, found: true };
  for (const name of ID_PARAMS) route[name] = null;
  return route;
}

const NOT_FOUND = Object.freeze({ ...emptyRoute(null, null), found: false });

// What a pathname asks for: { mode, view, caseKey, sessionId, draftId, ... , found }.
//
// Only shapes in ROUTES are `found`. A longer link -- from a later release,
// say -- is reported as not found rather than trimmed to its case: quietly
// showing something other than what a link named reads as though it had opened.
export function parseLocation(pathname = "/") {
  const segments = String(pathname).split("/").filter(Boolean);
  if (segments.length === 0) return { ...emptyRoute("case", null), root: true };
  const mode = MODE_BY_ROOT[segments[0]];
  if (!mode) return NOT_FOUND;
  const rest = segments.slice(1);
  for (const entry of ROUTES) {
    if (entry.mode !== mode) continue;
    const params = matchPattern(entry.pattern, rest);
    if (params) return { ...emptyRoute(mode, entry.view), ...params };
  }
  return NOT_FOUND;
}

// The URL for a route object, or null if no screen has that shape.
export function buildPath(route) {
  if (!route?.mode) return null;
  const entry = ROUTES.find(
    (item) =>
      item.mode === route.mode &&
      item.view === (route.view ?? null) &&
      item.pattern.every((token) => !token.startsWith(":") || route[token.slice(1)] != null) &&
      (item.pattern.includes(":caseKey") === Boolean(route.caseKey)),
  );
  if (!entry) return null;
  const parts = entry.pattern.map((token) => {
    if (!token.startsWith(":")) return token;
    const name = token.slice(1);
    return name === "caseKey" ? encodeKey(route.caseKey) : String(route[name]);
  });
  return `/${[TASK_ROOTS[route.mode], ...parts].join("/")}`;
}

const at = (mode, view, params = {}) => buildPath({ mode, view, ...params });

export const paths = {
  cases: () => "/cases",
  case: (caseKey) => at("case", null, { caseKey }),
  draftingHome: () => "/drafting",
  drafting: (caseKey) => at("draft", null, { caseKey }),
  draftingNew: (caseKey) => at("draft", "new", { caseKey }),
  draftingSession: (caseKey, sessionId) => at("draft", "session", { caseKey, sessionId }),
  draftingSessionView: (caseKey, sessionId, view) => at("draft", view, { caseKey, sessionId }),
  draftingJob: (caseKey, sessionId, jobId) => at("draft", "job", { caseKey, sessionId, jobId }),
  draft: (caseKey, sessionId, draftId) => at("draft", "draft", { caseKey, sessionId, draftId }),
  draftView: (caseKey, sessionId, draftId, view) => at("draft", view, { caseKey, sessionId, draftId }),
  research: () => "/research/search",
  argumentGym: () => "/argument-gym",
};

// Where a mode's sidebar entry goes. `view` is "new" for drafting setup.
export function pathForMode(mode, caseKey = null, { view = null } = {}) {
  if (!TASK_ROOTS[mode]) return paths.cases();
  if (mode === "research") return paths.research();
  if (mode === "argument_gym") return paths.argumentGym();
  if (!caseKey) return `/${TASK_ROOTS[mode]}`;
  return buildPath({ mode, view: mode === "draft" && view === "new" ? "new" : null, caseKey });
}

// The same screen, addressed by the case's current route key. Used to replace
// an old case number or a bare external id with the link the server now gives.
export function canonicalPath(route, routeCaseKey) {
  if (!route?.found || !route.mode || !route.caseKey) return null;
  if (!CASE_SCOPED_MODES.has(route.mode)) return null;
  return buildPath({ ...route, caseKey: routeCaseKey });
}

// Where a saved drafting session reopens, from the server's advisory `resume`
// block. Only screens that show saved state: nothing here is an action.
export function resumePath(caseKey, sessionId, resume) {
  const view = resume?.recommendedView;
  if (view === "job" && resume.activeJobId) return paths.draftingJob(caseKey, sessionId, resume.activeJobId);
  if (view === "draft") {
    const draftId = resume.lastDraftId ?? resume.draftIds?.[0];
    if (draftId) return paths.draft(caseKey, sessionId, draftId);
  }
  if (view === "plan") return paths.draftingSessionView(caseKey, sessionId, "plan");
  return paths.draftingSessionView(caseKey, sessionId, "goal");
}

// What a case-scoped screen should do about which case it shows.
//
//   { type: "load", caseKey }      resolve this key (the URL's, or a remembered one)
//   { type: "redirect", to }       the URL names no case but one is active: say so
//   { type: "none" }               nothing to open; the screen asks for a case
//
// The URL always wins. A remembered case only fills a URL that names none, so
// a pasted link never opens whichever case this browser happened to have last.
export function caseRouteAction(route, { activeCaseKey = null } = {}) {
  if (!route?.found) return { type: "none" };
  if (route.root) return { type: "redirect", to: pathForMode("case", activeCaseKey) };
  if (route.caseKey) return { type: "load", caseKey: route.caseKey };
  if (!CASE_SCOPED_MODES.has(route.mode)) {
    return activeCaseKey ? { type: "load", caseKey: activeCaseKey } : { type: "none" };
  }
  if (activeCaseKey) return { type: "redirect", to: pathForMode(route.mode, activeCaseKey) };
  return { type: "none" };
}

// The page to come back to after an external sign-in, or "" for the home
// screen. The server validates it again; this only avoids asking for a path
// that cannot be honoured.
export function signInReturnPath(pathname) {
  const route = parseLocation(pathname);
  if (!route.found || route.root) return "";
  return pathname;
}

// Whether a matter is the one a route key names, before asking the server.
export function matterMatchesKey(matter, caseKey) {
  if (!matter || !caseKey) return false;
  return String(matter.routeCaseKey ?? "") === String(caseKey) || String(matter.id) === String(caseKey);
}

// Whether the case a URL names is ready to show:
//   "none"         the URL names no case
//   "loading"      it is being looked up
//   "ready"        the loaded matter is the one the URL names
//   "unavailable"  no such case, or not one this account may open (the same answer)
//   "error"        the lookup failed for some other reason
//
// A case-scoped screen shows its work only when "ready" or "none"; anything
// else would draw one case's screen under another case's URL.
export function routeCaseState(route, { matter = null, lookup = null } = {}) {
  if (!route?.caseKey) return "none";
  if (matterMatchesKey(matter, route.caseKey)) return "ready";
  if (lookup?.key === route.caseKey && lookup.status !== "idle") return lookup.status;
  return "loading";
}

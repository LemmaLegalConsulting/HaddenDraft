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

export const paths = {
  cases: () => "/cases",
  case: (caseKey) => `/cases/${encodeKey(caseKey)}`,
  draftingHome: () => "/drafting",
  drafting: (caseKey) => `/drafting/${encodeKey(caseKey)}`,
  draftingNew: (caseKey) => `/drafting/${encodeKey(caseKey)}/new`,
  research: () => "/research/search",
  argumentGym: () => "/argument-gym",
};

// Where a mode's sidebar entry goes. `view` is "new" for drafting setup.
export function pathForMode(mode, caseKey = null, { view = null } = {}) {
  const root = TASK_ROOTS[mode];
  if (!root) return paths.cases();
  if (mode === "research") return paths.research();
  if (mode === "argument_gym") return paths.argumentGym();
  if (!caseKey) return `/${root}`;
  const base = `/${root}/${encodeKey(caseKey)}`;
  return mode === "draft" && view === "new" ? `${base}/new` : base;
}

function decodeSegment(segment) {
  try {
    return decodeURIComponent(segment);
  } catch {
    return null;
  }
}

const NOT_FOUND = Object.freeze({ mode: null, caseKey: null, view: null, found: false });

// What a pathname asks for: { mode, caseKey, view, found }.
//
// Only shapes this version can actually open are `found`. A longer link --
// `/drafting/26-0222/sessions/184`, say, from a later release -- is reported
// as not found rather than trimmed to its case: quietly showing something
// other than what a link named reads as though it had opened.
export function parseLocation(pathname = "/") {
  const segments = String(pathname).split("/").filter(Boolean);
  if (segments.length === 0) return { mode: "case", caseKey: null, view: null, found: true, root: true };
  const mode = MODE_BY_ROOT[segments[0]];
  if (!mode) return NOT_FOUND;

  if (mode === "research") {
    if (segments.length === 1 || (segments.length === 2 && segments[1] === "search")) {
      return { mode, caseKey: null, view: null, found: true };
    }
    return NOT_FOUND;
  }
  if (mode === "argument_gym") {
    return segments.length === 1 ? { mode, caseKey: null, view: null, found: true } : NOT_FOUND;
  }

  if (segments.length === 1) return { mode, caseKey: null, view: null, found: true };
  const caseKey = decodeSegment(segments[1]);
  if (!caseKey || !caseKey.trim()) return NOT_FOUND;
  if (segments.length === 2) return { mode, caseKey, view: null, found: true };
  if (mode === "draft" && segments.length === 3 && segments[2] === "new") {
    return { mode, caseKey, view: "new", found: true };
  }
  return NOT_FOUND;
}

// The same screen, addressed by the case's current route key. Used to replace
// an old case number or a bare external id with the link the server now gives.
export function canonicalPath(route, routeCaseKey) {
  if (!route?.found || !route.mode) return null;
  if (!CASE_SCOPED_MODES.has(route.mode)) return null;
  return pathForMode(route.mode, routeCaseKey, { view: route.view });
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

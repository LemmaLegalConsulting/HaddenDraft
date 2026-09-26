// When leaving a screen could lose work nobody has saved.
//
// Moving between the steps and documents of one saved session keeps all of it
// in memory, so that is never interrupted. Leaving the session -- another
// session, another case, another task, or closing the tab -- is.

import { parseLocation } from "../routes/paths.js";

// The piece of saved work a URL is on, or null. A session or letter belongs to
// one case, so its id alone says whether two URLs are the same work --
// rewriting an old case number in the URL is not leaving it.
export function savedWorkKey(route) {
  if (route?.mode === "draft" && route.sessionId) return `drafting:${route.sessionId}`;
  if (route?.mode === "advice_letter" && route.draftId) return `advice:${route.draftId}`;
  return null;
}

export function leavesSavedWork(currentPathname, nextPathname) {
  if (currentPathname === nextPathname) return false;
  const current = savedWorkKey(parseLocation(currentPathname));
  if (!current) return true;
  return current !== savedWorkKey(parseLocation(nextPathname));
}

// The single save status a screen shows. "conflict" outranks everything: the
// advocate has a decision to make before any save can succeed.
export function saveStatus({ dirty = false, saving = false, failed = false, conflict = false } = {}) {
  if (conflict) return "conflict";
  if (saving) return "saving";
  if (failed) return "failed";
  return dirty ? "dirty" : "saved";
}

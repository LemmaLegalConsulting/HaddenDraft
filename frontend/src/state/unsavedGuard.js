// When leaving a screen could lose work nobody has saved.
//
// Moving between the steps and documents of one saved session keeps all of it
// in memory, so that is never interrupted. Leaving the session -- another
// session, another case, another task, or closing the tab -- is.

import { parseLocation } from "../routes/paths.js";

export function leavesSavedWork(currentPathname, nextPathname) {
  if (currentPathname === nextPathname) return false;
  const current = parseLocation(currentPathname);
  const next = parseLocation(nextPathname);
  if (current.mode !== "draft" || !current.sessionId) return true;
  // A session belongs to one case, so its id alone says whether this is the
  // same work -- rewriting an old case number in the URL is not leaving it.
  return !(next.mode === "draft" && next.sessionId === current.sessionId);
}

// The single save status a screen shows. "conflict" outranks everything: the
// advocate has a decision to make before any save can succeed.
export function saveStatus({ dirty = false, saving = false, failed = false, conflict = false } = {}) {
  if (conflict) return "conflict";
  if (saving) return "saving";
  if (failed) return "failed";
  return dirty ? "dirty" : "saved";
}

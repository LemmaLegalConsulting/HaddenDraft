// Which fill-template session was open for a case, and what had been typed
// into it but not saved, remembered in this browser.
//
// The panel lives only while its screen is showing. Switching to another
// screen, a reload, a deploy, or a dev-server hot reload unmounted it and took
// the open session and every unsaved answer with it, so the advocate came back
// to an empty template picker. Now the session reopens and the typing returns.
//
// A draft is tied to the revision it was typed against. If the session has been
// saved since -- in another window, say -- the draft is dropped rather than
// laid over newer answers, and the caller says so.
//
// Browser storage can be missing or throw; every access is guarded, and the
// fallback is the old behaviour, never an error.

const OPEN = "drafting.templateFill.open:";
const DRAFT = "drafting.templateFill.draft:";

function storage(store) {
  if (store !== undefined) return store;
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function read(key, store) {
  try {
    return storage(store)?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function write(key, value, store) {
  try {
    const target = storage(store);
    if (!target) return;
    if (value === null) target.removeItem(key);
    else target.setItem(key, value);
  } catch {
    // A convenience only; losing it costs reopening the session by hand.
  }
}

export function rememberOpenSession(matterId, sessionId, store) {
  if (matterId) write(`${OPEN}${matterId}`, sessionId ? String(sessionId) : null, store);
}

export function openSessionFor(matterId, store) {
  return matterId ? read(`${OPEN}${matterId}`, store) : null;
}

export function saveDraft(sessionId, revision, edits, store) {
  if (!sessionId) return;
  const empty = !edits || Object.keys(edits).length === 0;
  write(`${DRAFT}${sessionId}`, empty ? null : JSON.stringify({ revision, edits }), store);
}

export function clearDraft(sessionId, store) {
  if (sessionId) write(`${DRAFT}${sessionId}`, null, store);
}

// { edits } to restore, { stale: true } when the session moved on, or null.
export function restoreDraft(sessionId, revision, store) {
  const raw = read(`${DRAFT}${sessionId}`, store);
  if (!raw) return null;
  try {
    const draft = JSON.parse(raw);
    if (!draft || typeof draft.edits !== "object" || !Object.keys(draft.edits).length) return null;
    if (draft.revision !== revision) {
      clearDraft(sessionId, store);
      return { stale: true };
    }
    return { edits: draft.edits };
  } catch {
    clearDraft(sessionId, store);
    return null;
  }
}

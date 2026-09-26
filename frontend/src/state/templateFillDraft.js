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
// Both are kept per signed-in account. Answers typed about a client are the
// client's information; the next person to sign in on this browser must never
// have them restored into their screen. With no account there is nothing to
// key on, so nothing is stored or restored at all.
//
// Browser storage can be missing or throw; every access is guarded, and the
// fallback is the old behaviour, never an error.

const OPEN = "drafting.templateFill.v2.open:";
const DRAFT = "drafting.templateFill.v2.draft:";
// Written before entries were kept per account. Nothing reads them; they are
// removed so an unscoped copy of someone's answers does not linger.
const LEGACY_PREFIXES = ["drafting.templateFill.open:", "drafting.templateFill.draft:"];

const scoped = (prefix, account, id) => `${prefix}${encodeURIComponent(account)}:${id}`;

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

// A hint only: a URL that names a session always wins over it.
export function rememberOpenSession(account, matterId, sessionId, store) {
  if (account && matterId) write(scoped(OPEN, account, matterId), sessionId ? String(sessionId) : null, store);
}

export function openSessionFor(account, matterId, store) {
  return account && matterId ? read(scoped(OPEN, account, matterId), store) : null;
}

export function saveDraft(account, sessionId, revision, edits, store) {
  if (!account || !sessionId) return;
  const empty = !edits || Object.keys(edits).length === 0;
  write(scoped(DRAFT, account, sessionId), empty ? null : JSON.stringify({ revision, edits }), store);
}

export function clearDraft(account, sessionId, store) {
  if (account && sessionId) write(scoped(DRAFT, account, sessionId), null, store);
}

// { edits } to restore, { stale: true } when the session moved on, or null.
export function restoreDraft(account, sessionId, revision, store) {
  if (!account) return null;
  const raw = read(scoped(DRAFT, account, sessionId), store);
  if (!raw) return null;
  try {
    const draft = JSON.parse(raw);
    if (!draft || typeof draft.edits !== "object" || !Object.keys(draft.edits).length) return null;
    if (draft.revision !== revision) {
      clearDraft(account, sessionId, store);
      return { stale: true };
    }
    return { edits: draft.edits };
  } catch {
    clearDraft(account, sessionId, store);
    return null;
  }
}

// Remove entries written before recovery was kept per account.
export function purgeUnscopedEntries(store) {
  try {
    const target = storage(store);
    if (!target || typeof target.length !== "number") return;
    const doomed = [];
    for (let index = 0; index < target.length; index += 1) {
      const key = target.key(index);
      if (key && LEGACY_PREFIXES.some((prefix) => key.startsWith(prefix))) doomed.push(key);
    }
    doomed.forEach((key) => target.removeItem(key));
  } catch {
    // Nothing reads them either way.
  }
}

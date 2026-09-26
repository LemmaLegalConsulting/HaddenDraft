// Which case an advocate was working on, remembered across reloads.
//
// The active case used to be React state only, and on load the app activated
// whichever case sorted first. A reload therefore switched every screen to a
// different client -- one the advocate never chose -- with only the name in the
// header to show for it. Now the choice is remembered per user in this browser,
// and when there is nothing to restore, nothing is activated: the Case screen
// asks rather than guessing.
//
// Browser storage can be missing or throw (private windows, blocked site data);
// every access is guarded, and the fallback is "no case", never "some case".

const PREFIX = "drafting.activeCase:";

function storage(store) {
  if (store !== undefined) return store;
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

export function rememberedCase(username, store) {
  if (!username) return null;
  try {
    return storage(store)?.getItem(`${PREFIX}${username}`) || null;
  } catch {
    return null;
  }
}

export function rememberCase(username, matterId, store) {
  if (!username) return;
  try {
    const target = storage(store);
    if (!target) return;
    if (matterId) target.setItem(`${PREFIX}${username}`, String(matterId));
    else target.removeItem(`${PREFIX}${username}`);
  } catch {
    // A convenience only; losing it costs one click on the Case screen.
  }
}

// The case to activate once the case list has loaded: the one already active,
// else the one this user last chose, else none.
export function initialActiveCase({ current = null, username = "", store } = {}) {
  return current ?? rememberedCase(username, store) ?? null;
}

// What a failed case lookup means for the screen, from the server's answer.
//
// A 404 with an account reason says this account cannot reach LegalServer
// cases at all: the fix is the connection, and the case stays remembered
// because nothing is wrong with it. A plain 404 means this case does not open
// for this account; anything else is a failure worth reporting.
export const ACCOUNT_LOOKUP_STATUSES = {
  legalserver_not_connected: "not_connected",
  legalserver_identity_mismatch: "identity_mismatch",
};

export function caseLookupStatus(error) {
  if (error?.status !== 404) return "error";
  return ACCOUNT_LOOKUP_STATUSES[error?.data?.reason] || "unavailable";
}

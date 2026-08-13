/**
 * Saying that the server is waking up, rather than that nothing is happening.
 *
 * The app is hosted so that it sleeps when nobody is using it, and the request
 * that wakes it waits on the container starting rather than on any work it
 * asked for. That wait lands on whoever comes back to a tab they left open, and
 * with no name on it a ten second pause reads as a hang.
 *
 * Elapsed time alone cannot tell the two apart: drafting and chat calls take
 * far longer than a cold start and are working the whole time. What separates
 * them is that a sleeping container answers *nothing* -- so when a request has
 * been out for a while, this asks nginx for /healthz, which a running container
 * returns in milliseconds without involving Django. A reply that does not come
 * back promptly means nothing is serving yet, and only then is the wait a
 * wake-up worth reporting.
 */

/** How long a request may be in flight before its slowness is worth diagnosing. */
export const WAKE_CHECK_AFTER_MS = 1200;
/** How long /healthz may take before we conclude nothing is serving yet. */
export const WARM_REPLY_MS = 800;

const listeners = new Set();
let inFlight = 0;
let checkTimer = null;
let waking = false;

function publish(next) {
  if (next === waking) return;
  waking = next;
  for (const listener of listeners) listener(waking);
}

/** Subscribe to whether the server is currently being woken up. */
export function subscribeToWake(listener) {
  listeners.add(listener);
  listener(waking);
  return () => listeners.delete(listener);
}

function checkWhetherServing(fetchImpl, healthPath) {
  let answered = false;
  const verdict = setTimeout(() => {
    // No answer to a request that costs the server nothing: it is still coming
    // up. Requests that are merely slow leave this path untouched.
    if (!answered && inFlight > 0) publish(true);
  }, WARM_REPLY_MS);

  const settle = () => {
    answered = true;
    clearTimeout(verdict);
  };
  try {
    fetchImpl(healthPath, { cache: "no-store" }).then(settle, settle);
  } catch {
    settle();
  }
}

/**
 * Record that a request is in flight. Returns the function to call when it
 * settles, however it settles.
 */
export function trackRequest({ fetchImpl = fetch, healthPath = "/healthz" } = {}) {
  inFlight += 1;
  if (checkTimer === null) {
    checkTimer = setTimeout(() => checkWhetherServing(fetchImpl, healthPath), WAKE_CHECK_AFTER_MS);
  }
  let done = false;
  return () => {
    if (done) return;
    done = true;
    inFlight -= 1;
    if (inFlight > 0) return;
    // Nothing is outstanding, so whatever the server was doing it is doing it
    // now. The next request starts the clock again from scratch.
    clearTimeout(checkTimer);
    checkTimer = null;
    publish(false);
  };
}

/** Test seam: forget everything this module is holding between requests. */
export function resetWakeNotice() {
  clearTimeout(checkTimer);
  checkTimer = null;
  inFlight = 0;
  waking = false;
  listeners.clear();
}

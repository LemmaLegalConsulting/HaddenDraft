/**
 * Telling "you are signed out" apart from "the server did not answer".
 *
 * The API host sleeps when nobody is using it, and a replica that has just
 * woken answers some of its first requests with a 500 for about thirty seconds
 * before it settles. The app treated any failure of /api/auth/me/ as proof the
 * session was gone and put the login form up -- so an advocate who stepped away
 * for five minutes came back to a login screen, typed their credentials, and
 * often had the login itself fail the same way. Their session was never in
 * question: it lasts a fortnight.
 *
 * A 401 or a 403 is the server telling us something about the viewer. A 500, or
 * no response at all, is the server telling us nothing -- and nothing is not a
 * reason to throw someone out of a session they still have. So those are worth
 * asking again about, and the ones that carry an answer are not.
 */

export class ApiError extends Error {
  constructor(message, { status = 0 } = {}) {
    super(message);
    this.name = "ApiError";
    /** The HTTP status, or 0 when the request never got a response at all. */
    this.status = status;
  }
}

/** Did the server fail to give us an answer, rather than an unwelcome one? */
export function isServerUnreachable(error) {
  const status = error?.status;
  if (typeof status !== "number") return false;
  return status === 0 || status >= 500;
}

/**
 * How long to wait before each retry.
 *
 * Growing, and summing to about twenty seconds across the seven attempts, which
 * covers the window a waking replica spends failing without leaving someone
 * staring at a spinner if the server is genuinely broken.
 */
export const UNREACHABLE_RETRY_DELAYS_MS = [500, 1000, 2000, 4000, 6000, 8000];

const sleepFor = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Run `attempt`, asking again while the failure is the server not answering.
 *
 * Anything the server did answer -- a 403, a validation error -- is raised
 * immediately, because repeating the request cannot change it.
 */
export async function retryWhileUnreachable(attempt, { delays = UNREACHABLE_RETRY_DELAYS_MS, sleep = sleepFor } = {}) {
  for (let index = 0; ; index += 1) {
    try {
      return await attempt();
    } catch (error) {
      if (index >= delays.length || !isServerUnreachable(error)) throw error;
      await sleep(delays[index]);
    }
  }
}

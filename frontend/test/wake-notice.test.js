import assert from "node:assert/strict";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";

import {
  WAKE_CHECK_AFTER_MS,
  WARM_REPLY_MS,
  resetWakeNotice,
  subscribeToWake,
  trackRequest,
} from "../src/api/wakeNotice.js";

/** Records every value the notice publishes, in order. */
function recorder() {
  const seen = [];
  const stop = subscribeToWake((waking) => seen.push(waking));
  return { seen, stop };
}

/** A health endpoint that answers after `ms`, standing in for the container. */
function healthAnsweringIn(ms) {
  return () => delay(ms);
}

test("a request that returns promptly says nothing", async () => {
  resetWakeNotice();
  const { seen } = recorder();

  trackRequest({ fetchImpl: healthAnsweringIn(0) })();
  await delay(WAKE_CHECK_AFTER_MS + WARM_REPLY_MS + 60);

  assert.deepEqual(seen, [false]);
});

test("a slow request whose server still answers /healthz is only slow, not asleep", async () => {
  resetWakeNotice();
  const { seen } = recorder();

  // The sort of long call the app makes on purpose: minutes of drafting work
  // against a server that is up the whole time.
  const settled = trackRequest({ fetchImpl: healthAnsweringIn(5) });
  await delay(WAKE_CHECK_AFTER_MS + WARM_REPLY_MS + 60);
  settled();

  assert.deepEqual(seen, [false], "a working server must not be reported as waking up");
});

test("a slow request whose server answers nothing is reported as waking up", async () => {
  resetWakeNotice();
  const { seen } = recorder();

  // Nothing is serving, so even the endpoint that costs the server nothing
  // stays unanswered.
  const settled = trackRequest({ fetchImpl: healthAnsweringIn(60_000) });
  await delay(WAKE_CHECK_AFTER_MS + WARM_REPLY_MS + 60);

  assert.deepEqual(seen, [false, true]);

  settled();
  assert.deepEqual(seen, [false, true, false], "the notice clears once the request lands");
});

test("the notice is not raised for a request that has already finished", async () => {
  resetWakeNotice();
  const { seen } = recorder();

  const settled = trackRequest({ fetchImpl: healthAnsweringIn(60_000) });
  await delay(WAKE_CHECK_AFTER_MS + 20);
  settled();
  await delay(WARM_REPLY_MS + 60);

  assert.deepEqual(seen, [false]);
});

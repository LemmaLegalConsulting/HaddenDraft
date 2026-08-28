import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, isServerUnreachable, retryWhileUnreachable } from "../src/api/errors.js";

const noWait = { delays: [1, 1, 1], sleep: async () => {} };

test("a 500 is the server not answering, not a signed-out viewer", () => {
  assert.equal(isServerUnreachable(new ApiError("boom", { status: 500 })), true);
  assert.equal(isServerUnreachable(new ApiError("unreachable", { status: 0 })), true);
});

test("a 401 or 403 is an answer, and asking again cannot change it", () => {
  assert.equal(isServerUnreachable(new ApiError("no", { status: 401 })), false);
  assert.equal(isServerUnreachable(new ApiError("no", { status: 403 })), false);
  assert.equal(isServerUnreachable(new ApiError("bad input", { status: 400 })), false);
});

test("an error carrying no status is not retried", () => {
  // A bug in our own code must surface, not be asked again six times.
  assert.equal(isServerUnreachable(new TypeError("undefined is not a function")), false);
});

test("a waking replica's 500s are ridden out rather than shown as a logout", async () => {
  let calls = 0;
  const result = await retryWhileUnreachable(async () => {
    calls += 1;
    if (calls < 3) throw new ApiError("Request failed: 500", { status: 500 });
    return { user: { isAuthenticated: true } };
  }, noWait);

  assert.equal(calls, 3);
  assert.equal(result.user.isAuthenticated, true);
});

test("a genuine rejection is raised at once, without retrying", async () => {
  let calls = 0;
  await assert.rejects(
    () => retryWhileUnreachable(async () => {
      calls += 1;
      throw new ApiError("Sign-in failed", { status: 400 });
    }, noWait),
    /Sign-in failed/,
  );

  assert.equal(calls, 1);
});

test("a server that never answers gives up rather than spinning forever", async () => {
  let calls = 0;
  await assert.rejects(
    () => retryWhileUnreachable(async () => {
      calls += 1;
      throw new ApiError("Request failed: 500", { status: 500 });
    }, noWait),
    /Request failed: 500/,
  );

  assert.equal(calls, noWait.delays.length + 1);
});

import assert from "node:assert/strict";
import test from "node:test";

import { waitForDrafts } from "../src/state/draftJobs.js";

const noSleep = async () => {};

test("an immediate answer with drafts needs no polling", async () => {
  const drafts = await waitForDrafts({ drafts: [{ id: 1 }] }, () => assert.fail("polled"), { sleep: noSleep });
  assert.deepEqual(drafts, [{ id: 1 }]);
});

test("a background job is polled until it completes", async () => {
  const answers = [
    { job: { id: 7, status: "running" } },
    { job: { id: 7, status: "complete" }, drafts: [{ id: 3 }] },
  ];
  const polled = [];
  const drafts = await waitForDrafts({ job: { id: 7, status: "pending" } }, async (id) => {
    polled.push(id);
    return answers.shift();
  }, { sleep: noSleep });
  assert.deepEqual(drafts, [{ id: 3 }]);
  assert.deepEqual(polled, [7, 7]);
});

test("a failed job surfaces its own error", async () => {
  await assert.rejects(
    waitForDrafts({ job: { id: 7, status: "pending" } }, async () => ({ job: { id: 7, status: "failed", error: "Model unavailable." } }), { sleep: noSleep }),
    /Model unavailable/,
  );
});

test("an answer with neither drafts nor a job is an error, not an empty draft", async () => {
  await assert.rejects(waitForDrafts({}, async () => ({}), { sleep: noSleep }), /did not start/);
});

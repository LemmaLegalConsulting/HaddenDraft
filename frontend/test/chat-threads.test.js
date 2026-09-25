import assert from "node:assert/strict";
import test from "node:test";

import { chatThreadView } from "../src/state/chatThreads.js";

test("the current chat is writable and names its thread", () => {
  assert.deepEqual(chatThreadView({ currentThreadId: 7 }), { viewing: 7, readOnly: false, writeThreadId: 7 });
});

test("a chat with no thread yet names none; the first message starts one", () => {
  assert.deepEqual(chatThreadView({}), { viewing: null, readOnly: false, writeThreadId: null });
});

test("a thread opened by URL that is still current can be continued", () => {
  assert.equal(chatThreadView({ routeThreadId: 7, currentThreadId: 7 }).readOnly, false);
});

test("an archived thread opened by URL is history, never written to", () => {
  assert.deepEqual(chatThreadView({ routeThreadId: 3, currentThreadId: 7 }), { viewing: 3, readOnly: true, writeThreadId: null });
});

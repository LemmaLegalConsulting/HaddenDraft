import assert from "node:assert/strict";
import test from "node:test";

import {
  chatScopeKey,
  chatTranscriptBody,
  chatTranscriptNote,
  chatTranscriptTitle,
} from "../src/components/chatTranscript.js";

const THREAD = [
  { role: "user", content: "Can the tenant raise conditions as a defense?" },
  { role: "assistant", content: "Yes, under R.C. 5321.07 with rent deposited." },
];

test("the note is titled with the question that opened the thread", () => {
  assert.equal(chatTranscriptTitle(THREAD), "Case chat: Can the tenant raise conditions as a defense?");
});

test("a thread with no question still gets a usable title", () => {
  assert.equal(chatTranscriptTitle([]), "Case chat");
  assert.equal(chatTranscriptTitle([{ role: "assistant", content: "hello" }]), "Case chat");
});

test("a long opening question is truncated rather than sent whole", () => {
  const title = chatTranscriptTitle([{ role: "user", content: "x".repeat(400) }]);
  assert.ok(title.length < 140);
  assert.ok(title.endsWith("…"));
});

test("both sides of the exchange are attributed in the note", () => {
  const body = chatTranscriptBody(THREAD);
  assert.match(body, /Advocate: Can the tenant/);
  assert.match(body, /AI: Yes, under R\.C\. 5321\.07/);
});

test("the note says it has not been reviewed by an attorney", () => {
  assert.match(chatTranscriptBody(THREAD), /has not been reviewed by an attorney/);
});

test("empty messages are left out rather than filed as blank lines", () => {
  const body = chatTranscriptBody([...THREAD, { role: "user", content: "   " }]);
  assert.equal(body.split("\n\n").length, 3);
});

test("the scope key names the thread, so re-saving replaces one note", () => {
  assert.equal(chatScopeKey({ matterId: "26-0000009", threadId: "7" }), "case-chat:26-0000009:7");
  assert.equal(chatScopeKey({ matterId: "26-0000009" }), "case-chat:26-0000009:current");
});

test("two threads on one case do not share a note", () => {
  assert.notEqual(
    chatScopeKey({ matterId: "26-0000009", threadId: "7" }),
    chatScopeKey({ matterId: "26-0000009", threadId: "8" }),
  );
});

test("the note payload carries title, body, and scope together", () => {
  const note = chatTranscriptNote(THREAD, { matterId: "26-0000009", threadId: "7" });
  assert.deepEqual(Object.keys(note).sort(), ["body", "scopeKey", "title"]);
});

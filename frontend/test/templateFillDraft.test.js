import test from "node:test";
import assert from "node:assert/strict";
import { clearDraft, openSessionFor, rememberOpenSession, restoreDraft, saveDraft } from "../src/state/templateFillDraft.js";

function memoryStore() {
  const data = new Map();
  return { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => data.set(key, String(value)), removeItem: (key) => data.delete(key), data };
}

test("the open session is remembered per case", () => {
  const store = memoryStore();
  rememberOpenSession("case-1", 81, store);
  rememberOpenSession("case-2", 90, store);
  assert.equal(openSessionFor("case-1", store), "81");
  assert.equal(openSessionFor("case-2", store), "90");
  rememberOpenSession("case-1", null, store);
  assert.equal(openSessionFor("case-1", store), null);
});

test("a draft comes back only against the revision it was typed on", () => {
  const store = memoryStore();
  saveDraft(81, 3, { hearing: "May 1" }, store);
  assert.deepEqual(restoreDraft(81, 3, store), { edits: { hearing: "May 1" } });
  // Saved elsewhere since: dropped, and the caller is told.
  assert.deepEqual(restoreDraft(81, 4, store), { stale: true });
  assert.equal(restoreDraft(81, 3, store), null, "a stale draft is gone, not kept for later");
});

test("saving no edits removes the draft; unreadable storage is not an error", () => {
  const store = memoryStore();
  saveDraft(81, 1, { hearing: "May 1" }, store);
  saveDraft(81, 1, {}, store);
  assert.equal(store.data.size, 0);
  store.setItem("drafting.templateFill.draft:82", "{not json");
  assert.equal(restoreDraft(82, 1, store), null);
  clearDraft(82, store);
  const broken = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); } };
  assert.doesNotThrow(() => saveDraft(81, 1, { a: "b" }, broken));
  assert.equal(restoreDraft(81, 1, broken), null);
  assert.equal(openSessionFor("case-1", broken), null);
  assert.equal(openSessionFor("case-1", null), null);
});

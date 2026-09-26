import test from "node:test";
import assert from "node:assert/strict";
import { clearDraft, openSessionFor, purgeUnscopedEntries, rememberOpenSession, restoreDraft, saveDraft } from "../src/state/templateFillDraft.js";

function memoryStore() {
  const data = new Map();
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
    key: (index) => [...data.keys()][index] ?? null,
    get length() { return data.size; },
    data,
  };
}

test("the open session is remembered per account and case", () => {
  const store = memoryStore();
  rememberOpenSession("ada", "case-1", 81, store);
  rememberOpenSession("ada", "case-2", 90, store);
  assert.equal(openSessionFor("ada", "case-1", store), "81");
  assert.equal(openSessionFor("ada", "case-2", store), "90");
  rememberOpenSession("ada", "case-1", null, store);
  assert.equal(openSessionFor("ada", "case-1", store), null);
});

test("a draft comes back only against the revision it was typed on", () => {
  const store = memoryStore();
  saveDraft("ada", 81, 3, { hearing: "May 1" }, store);
  assert.deepEqual(restoreDraft("ada", 81, 3, store), { edits: { hearing: "May 1" } });
  // Saved elsewhere since: dropped, and the caller is told.
  assert.deepEqual(restoreDraft("ada", 81, 4, store), { stale: true });
  assert.equal(restoreDraft("ada", 81, 3, store), null, "a stale draft is gone, not kept for later");
});

test("one account's unsaved answers are never restored for another", () => {
  const store = memoryStore();
  saveDraft("ada", 81, 3, { client: "Maria Alvarez" }, store);
  rememberOpenSession("ada", "case-1", 81, store);
  assert.equal(restoreDraft("bob", 81, 3, store), null);
  assert.equal(openSessionFor("bob", "case-1", store), null);
});

test("with no account, nothing is stored or restored", () => {
  const store = memoryStore();
  saveDraft("", 81, 3, { client: "Maria Alvarez" }, store);
  rememberOpenSession(null, "case-1", 81, store);
  assert.equal(store.data.size, 0);
  assert.equal(restoreDraft("", 81, 3, store), null);
});

test("entries written before accounts were recorded are removed", () => {
  const store = memoryStore();
  store.setItem("drafting.templateFill.draft:81", JSON.stringify({ revision: 3, edits: { client: "Maria" } }));
  store.setItem("drafting.templateFill.open:case-1", "81");
  store.setItem("drafting.activeCase:ada", "case-1");
  purgeUnscopedEntries(store);
  assert.deepEqual([...store.data.keys()], ["drafting.activeCase:ada"]);
});

test("saving no edits removes the draft; unreadable storage is not an error", () => {
  const store = memoryStore();
  saveDraft("ada", 81, 1, { hearing: "May 1" }, store);
  saveDraft("ada", 81, 1, {}, store);
  assert.equal(store.data.size, 0);
  store.setItem("drafting.templateFill.v2.draft:ada:82", "{not json");
  assert.equal(restoreDraft("ada", 82, 1, store), null);
  clearDraft("ada", 82, store);
  const broken = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); } };
  assert.doesNotThrow(() => saveDraft("ada", 81, 1, { a: "b" }, broken));
  assert.equal(restoreDraft("ada", 81, 1, broken), null);
  assert.equal(openSessionFor("ada", "case-1", broken), null);
  assert.equal(openSessionFor("ada", "case-1", null), null);
  assert.doesNotThrow(() => purgeUnscopedEntries(broken));
});

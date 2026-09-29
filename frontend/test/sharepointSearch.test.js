import test from "node:test";
import assert from "node:assert/strict";
import { createPrecedentSearch, sourceLink, resultDetails } from "../src/components/sharepointSearch.js";

const payload = { results: [{ id: "sp:item", title: "Lease" }], aiSummary: "No AI was used.", coverage: "Up to 25 matches." };

test("search trims the query and preserves API order and coverage", async () => {
  let called;
  const model = createPrecedentSearch(async (query) => { called = query; return payload; });
  model.setQuery(" lease ");
  await model.submit();
  assert.equal(called, "lease");
  assert.deepEqual(model.getSnapshot().results, payload.results);
  assert.equal(model.getSnapshot().aiSummary, payload.aiSummary);
  assert.equal(model.getSnapshot().coverage, payload.coverage);
  assert.equal(model.getSnapshot().busy, false);
});

test("empty, failed, unconfigured, and throttled searches stay distinct", async () => {
  const model = createPrecedentSearch(async () => ({ ...payload, results: [] }));
  assert.equal(model.getSnapshot().results, null);
  await model.submit();
  assert.match(model.getSnapshot().error, /Enter a search/);
  model.setQuery("lease");
  await model.submit();
  assert.deepEqual(model.getSnapshot().results, []);
  for (const error of [{ message: "Access denied" }, { message: "Not configured" }, { message: "Busy", data: { retryAfter: 30 } }]) {
    const failing = createPrecedentSearch(async () => { throw error; });
    failing.setQuery("lease");
    await failing.submit();
    assert.equal(failing.getSnapshot().results, null);
    assert.match(failing.getSnapshot().error, new RegExp(error.message));
    if (error.data) assert.match(failing.getSnapshot().error, /30 seconds/);
  }
});

test("editing the query invalidates an outstanding response", async () => {
  let resolve, signal;
  const model = createPrecedentSearch((_query, options) => {
    signal = options.signal;
    return new Promise((done) => { resolve = done; });
  });
  model.setQuery("lease");
  const pending = model.submit();
  assert.equal(model.getSnapshot().busy, true);
  model.setQuery("notice");
  assert.equal(signal.aborted, true);
  resolve(payload);
  await pending;
  assert.equal(model.getSnapshot().results, null);
  assert.equal(model.getSnapshot().query, "notice");
});

test("disposing suppresses a late failure", async () => {
  let reject;
  const model = createPrecedentSearch(() => new Promise((_resolve, fail) => { reject = fail; }));
  model.setQuery("lease");
  const pending = model.submit();
  model.dispose();
  reject(new Error("late failure"));
  await pending;
  assert.equal(model.getSnapshot().error, "");
});

test("source links accept HTTPS and metadata has readable labels", () => {
  assert.equal(sourceLink("https://tenant.sharepoint.com/lease"), "https://tenant.sharepoint.com/lease");
  for (const url of ["javascript:alert(1)", "/relative", "http://example.org", "https://user:secret@example.org"]) assert.equal(sourceLink(url), "");
  assert.match(resultDetails({ metadata: { modifiedAt: "2026-09-01", path: "/Library" } }), /Modified 2026-09-01 · \/Library/);
});

import assert from "node:assert/strict";
import test from "node:test";

import { mergeSessionPages, sessionRowLabels } from "../src/state/savedSessions.js";

test("a drafted session says how many documents it has", () => {
  const labels = sessionRowLabels({ templateTitle: "Answer", goal: "Answer the complaint", draftCount: 2 });
  assert.deepEqual(labels, { title: "Answer", goal: "Answer the complaint", progress: "2 documents drafted" });
});

test("a planned session names its planned documents", () => {
  const labels = sessionRowLabels({ plannedDocuments: ["Answer", "Motion"], draftCount: 0 });
  assert.equal(labels.title, "Answer, Motion");
  assert.equal(labels.progress, "Planned, not drafted");
});

test("an unplanned session still reads as something", () => {
  assert.equal(sessionRowLabels({}).progress, "Not planned yet");
});

test("pages merge without repeating a row", () => {
  assert.deepEqual(mergeSessionPages([{ id: 1 }, { id: 2 }], [{ id: 2 }, { id: 3 }]).map((row) => row.id), [1, 2, 3]);
});

import assert from "node:assert/strict";
import test from "node:test";

import {
  changeLogEntries,
  componentHistoryEntries,
  pendingOperations,
  restoreVersionRequest,
  supportSummary,
} from "../src/components/documentHistory.js";

const components = [
  {
    id: 1,
    stableKey: "notice-defense",
    label: "Notice defense",
    removed: false,
    currentVersionSequence: 2,
    versions: [
      {
        sequence: 1,
        origin: "template",
        instruction: "",
        body: "Template text.",
        createdAt: "2026-08-01T10:00:00",
        sourceBindings: [],
      },
      {
        sequence: 2,
        origin: "ai",
        instruction: "Add the service date.",
        body: "Regenerated text.",
        createdAt: "2026-08-01T11:00:00",
        sourceBindings: [
          { sourceKey: "rc-1923", role: "legal_authority", label: "R.C. 1923.04", citation: "R.C. 1923.04", verified: false },
          { sourceKey: "prior-answer", role: "example_language", label: "Prior answer", citation: "", verified: false },
        ],
      },
    ],
  },
];

test("history shows the newest version first and marks the current one", () => {
  const [entry] = componentHistoryEntries(components);

  assert.equal(entry.label, "Notice defense");
  assert.equal(entry.versionCount, 2);
  assert.deepEqual(entry.versions.map((version) => version.sequence), [2, 1]);
  assert.deepEqual(entry.versions.map((version) => version.isCurrent), [true, false]);
  assert.equal(entry.versions[0].originLabel, "AI generated");
  assert.equal(entry.versions[1].originLabel, "From template");
});

test("support is grouped by what each source is allowed to carry", () => {
  const [entry] = componentHistoryEntries(components);

  assert.deepEqual(
    entry.support.groups.map((group) => group.label),
    ["Legal authority", "Example language only"],
  );
  assert.equal(entry.support.hasAuthority, true);
  assert.equal(entry.support.styleOnlyOnly, false);
});

test("a section resting only on example language is identifiable", () => {
  const summary = supportSummary([{ sourceKey: "prior-answer", role: "example_language", label: "Prior answer" }]);

  assert.equal(summary.hasAuthority, false);
  assert.equal(summary.styleOnlyOnly, true);
});

test("a section with no bound sources claims neither authority nor style support", () => {
  const summary = supportSummary([]);

  assert.equal(summary.total, 0);
  assert.equal(summary.hasAuthority, false);
  assert.equal(summary.styleOnlyOnly, false);
});

test("the change log reads as what happened, and pending proposals are separable", () => {
  const operations = [
    {
      id: 9,
      operationType: "replace_component",
      targetComponentKey: "notice-defense",
      status: "applied",
      origin: "ai",
      rationale: "Add the service date.",
      requestedBy: "reviewer",
      createdAt: "2026-08-01T11:00:00",
      resolvedAt: "2026-08-01T11:00:01",
    },
    {
      id: 10,
      operationType: "delete_component",
      targetComponentKey: "certificate",
      status: "proposed",
      origin: "human",
      rationale: "Not needed in this court.",
      createdAt: "2026-08-01T12:00:00",
      resolvedAt: null,
    },
  ];

  const entries = changeLogEntries(operations);

  assert.deepEqual(entries.map((entry) => entry.label), ["Replaced section", "Removed section"]);
  assert.equal(entries[0].origin, "AI generated");
  assert.equal(entries[0].pending, false);
  assert.deepEqual(pendingOperations(operations).map((entry) => entry.id), [10]);
});

test("restoring a version asks for a revert operation that applies immediately", () => {
  assert.deepEqual(restoreVersionRequest("notice-defense", 1), {
    operationType: "revert_component",
    payload: { stableKey: "notice-defense", sequence: 1 },
    rationale: "Reviewer restored version 1 of notice-defense.",
    apply: true,
  });
});

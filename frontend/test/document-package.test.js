import assert from "node:assert/strict";
import test from "node:test";

import {
  packageFindings,
  packageView,
  unvalidatedDocuments,
} from "../src/components/documentPackage.js";
import { draftWorkspaceReducer, initialDraftWorkspace } from "../src/state/draftWorkspace.js";

const packageData = {
  documents: [
    { id: 1, title: "Motion to Continue", role: "motion", templateId: 5 },
    { id: 2, title: "Proposed Order", role: "proposed_order", templateId: 6 },
  ],
  relationships: [
    { sourceDocumentId: 2, targetDocumentId: 1, relationshipType: "implements_relief", metadata: { derived: true } },
  ],
};

test("the package graph reads as sentences about named documents", () => {
  const view = packageView(packageData);

  assert.deepEqual(view.documents.map((item) => item.roleLabel), ["Motion", "Proposed order"]);
  assert.equal(
    view.relationships[0].description,
    "Proposed Order implements the relief requested by Motion to Continue.",
  );
  assert.equal(view.isPackage, true);
});

test("relationships pointing outside the package are dropped", () => {
  const view = packageView({
    ...packageData,
    relationships: [
      ...packageData.relationships,
      { sourceDocumentId: 99, targetDocumentId: 1, relationshipType: "depends_on" },
    ],
  });

  assert.equal(view.relationships.length, 1);
});

test("a single document is not presented as a package", () => {
  assert.equal(packageView({ documents: [packageData.documents[0]], relationships: [] }).isPackage, false);
  assert.equal(packageView(null).isPackage, false);
});

test("cross-document findings are collected from every document and keep their source", () => {
  const drafts = [
    {
      id: 1,
      title: "Motion to Continue",
      validationFlags: [
        { findingId: "W800-a", category: "package_consistency", message: "Case numbers disagree." },
        { findingId: "W430-b", category: "citations", message: "No citations detected." },
      ],
    },
    {
      id: 2,
      title: "Proposed Order",
      validationFlags: [
        { findingId: "W810-c", category: "package_consistency", message: "Exhibit A is not identified." },
      ],
    },
  ];

  const findings = packageFindings(drafts);

  assert.deepEqual(findings.map((finding) => finding.findingId), ["W800-a", "W810-c"]);
  assert.deepEqual(findings.map((finding) => finding.documentTitle), ["Motion to Continue", "Proposed Order"]);
});

test("documents nobody has validated are named, so an empty result is not read as clean", () => {
  const drafts = [{ id: 1, title: "Motion to Continue" }, { id: 2, title: "Proposed Order" }];
  const generated = draftWorkspaceReducer(initialDraftWorkspace, { type: "documentsGenerated", drafts });

  assert.deepEqual(unvalidatedDocuments(drafts, generated.validatedDraftIds), [
    "Motion to Continue",
    "Proposed Order",
  ]);

  const validated = draftWorkspaceReducer(generated, {
    type: "documentValidated",
    draft: { ...drafts[0], validationFlags: [] },
    validation: { remainingErrorCount: 0 },
  });

  assert.deepEqual(validated.validatedDraftIds, [1]);
  assert.deepEqual(unvalidatedDocuments(validated.drafts, validated.validatedDraftIds), ["Proposed Order"]);
});

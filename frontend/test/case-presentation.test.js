import assert from "node:assert/strict";
import test from "node:test";

import {
  caseNumberFor,
  caseDocumentPreviewKind,
  caseTitleFor,
  isLegalServerCase,
  isQuickCase,
  lastActivityLabel,
} from "../src/components/casePresentation.js";

test("case title and number prefer explicit LegalServer display fields", () => {
  const matter = {
    id: "fallback-id",
    title: "Tenant v. Landlord",
    client: "Jordan Tenant",
    caseNumber: "26-000123",
  };

  assert.equal(caseTitleFor(matter), "Tenant v. Landlord");
  assert.equal(caseNumberFor(matter), "26-000123");
});

test("case presentation has safe fallbacks for quick and LegalServer cases", () => {
  assert.equal(caseTitleFor({}), "Unnamed case");
  assert.equal(caseNumberFor({ id: "LS-1" }), "LS-1");
  assert.equal(isLegalServerCase({ sourceSystem: "LegalServer" }), true);
  assert.equal(isQuickCase({ sourceSystem: "Manual" }), true);
});

test("last activity is rendered as a useful relative label", () => {
  const now = Date.parse("2026-08-03T12:00:00Z");

  assert.equal(lastActivityLabel({ sourceSystem: "LegalServer", lastActivityAt: "2026-08-02T12:00:00Z" }, now), "1 day inactive");
  assert.equal(lastActivityLabel({ sourceSystem: "Manual", lastActivityAt: "2026-08-02T12:00:00Z" }, now), "");
});

test("viewable case documents are identified from MIME type or filename", () => {
  assert.equal(caseDocumentPreviewKind({ mimeType: "application/pdf", filename: "download" }), "pdf");
  assert.equal(caseDocumentPreviewKind({ filename: "inspection-photo.JPG" }), "image");
  assert.equal(caseDocumentPreviewKind({ filename: "notes.docx" }), "");
});

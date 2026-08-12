import assert from "node:assert/strict";
import test from "node:test";

import {
  deliveryFromHeaders,
  deliveryMessage,
  deliveryTone,
  previewedFieldRows,
  saveAvailability,
  saveDefault,
  triageDeliveryLines,
} from "../src/components/legalServerSave.js";
import { saveButtonLabel, saveButtonTitle } from "../src/components/legalServerSave.js";
import { filenameFromDisposition } from "../src/components/downloadFile.js";

function headers(entries) {
  return { get: (name) => entries[name] ?? null };
}

test("a generated document defaults to being filed, working notes do not", () => {
  const boot = { configured: true, defaults: { documents: true, research: false, triage: false } };

  assert.equal(saveDefault(boot, "documents"), true);
  assert.equal(saveDefault(boot, "research"), false);
  assert.equal(saveDefault(boot, "triage"), false);
});

test("the defaults survive a bootstrap that does not mention them", () => {
  assert.equal(saveDefault(null, "documents"), true);
  assert.equal(saveDefault({}, "research"), false);
});

test("a server default overrides the built-in one", () => {
  assert.equal(saveDefault({ defaults: { documents: false } }, "documents"), false);
  assert.equal(saveDefault({ defaults: { triage: true } }, "triage"), true);
});

test("an unconfigured site explains itself instead of offering the checkbox", () => {
  const { available, hint } = saveAvailability({ bootstrapSave: { configured: false } });

  assert.equal(available, false);
  assert.match(hint, /not connected/);
});

test("a case that does not exist in LegalServer says so in its own words", () => {
  const { available, hint } = saveAvailability({
    bootstrapSave: { configured: true },
    caseStatus: { canSave: false, message: "This case does not exist in LegalServer." },
  });

  assert.equal(available, false);
  assert.equal(hint, "This case does not exist in LegalServer.");
});

test("a download reports its upload result through response headers", () => {
  const response = {
    headers: headers({
      "X-LegalServer-Delivery": "saved",
      "X-LegalServer-Delivery-Message": "Saved the document to LegalServer.",
    }),
  };

  assert.deepEqual(deliveryFromHeaders(response), {
    status: "saved",
    message: "Saved the document to LegalServer.",
  });
});

test("a download with no delivery headers reports nothing rather than a false success", () => {
  assert.equal(deliveryFromHeaders({ headers: headers({}) }), null);
  assert.equal(deliveryFromHeaders(null), null);
});

test("a failed upload reads as an error, a dry run does not", () => {
  assert.equal(deliveryTone({ status: "failed" }), "error");
  assert.equal(deliveryTone({ status: "saved" }), "success");
  assert.equal(deliveryTone({ status: "dry_run" }), "info");
});

test("a delivery with no message of its own still says what happened", () => {
  assert.match(deliveryMessage({ status: "failed" }), /Could not save/);
  assert.equal(deliveryMessage({ status: "saved", message: "Saved the case note." }), "Saved the case note.");
});

test("triage reports the note and the case update as separate lines", () => {
  const lines = triageDeliveryLines({
    casenote: { kind: "casenote", status: "saved", message: "Saved the case note to LegalServer." },
    caseUpdate: { kind: "case_update", status: "dry_run", message: "Previewed only.", fields: {} },
  });

  assert.deepEqual(lines.map((line) => line.key), ["casenote", "case_update"]);
  assert.deepEqual(lines.map((line) => line.tone), ["success", "info"]);
});

test("a triage run that produced no delivery shows no lines", () => {
  assert.deepEqual(triageDeliveryLines(null), []);
  assert.deepEqual(triageDeliveryLines({ casenote: null, caseUpdate: null }), []);
});

test("previewed case properties flatten custom fields alongside ordinary ones", () => {
  const rows = previewedFieldRows({
    fields: { case_status: "Screened", custom_fields: { ai_triage_outcome: "Full rep" } },
  });

  assert.deepEqual(rows, [
    { name: "case_status", value: "Screened" },
    { name: "ai_triage_outcome", value: "Full rep" },
  ]);
});

test("the download filename comes from the server, not the guess", () => {
  assert.equal(
    filenameFromDisposition('attachment; filename="2026-08-11-garcia-advice-letter.docx"', "fallback.docx"),
    "2026-08-11-garcia-advice-letter.docx",
  );
  assert.equal(filenameFromDisposition("", "fallback.docx"), "fallback.docx");
});

test("the save button says update once this session already filed one", () => {
  assert.equal(saveButtonLabel({}), "Save to LegalServer");
  assert.equal(saveButtonLabel({ delivery: { status: "saved" } }), "Update in LegalServer");
  assert.equal(saveButtonLabel({ busy: true }), "Saving\u2026");
});

test("a failed save still offers to save, not to update", () => {
  assert.equal(saveButtonLabel({ delivery: { status: "failed" } }), "Save to LegalServer");
});

test("the button explains that a second save replaces rather than duplicates", () => {
  assert.match(saveButtonTitle({ delivery: { status: "saved" } }), /Replaces/);
  assert.match(saveButtonTitle({}), /Files this/);
  assert.equal(saveButtonTitle({ available: false, hint: "no case" }), "no case");
});

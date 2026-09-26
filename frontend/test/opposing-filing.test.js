import assert from "node:assert/strict";
import test from "node:test";

import {
  blocksGeneration,
  caseFileOptionLabel,
  filedOnError,
  filingKindLabel,
  filingStatus,
  respondsToRequirement,
  sourceSummary,
} from "../src/components/opposingFiling.js";

const MOTION = { id: 1, title: "Motion for Continuance", metadata: {} };
const DISMISS = {
  id: 2,
  title: "Motion to Dismiss",
  metadata: { respondsTo: { required: false, recommended: true, expects: ["complaint"], question: "Which complaint?" } },
};
const REPLY = {
  id: 3,
  title: "Reply in Support of Motion to Dismiss",
  metadata: {
    respondsTo: { required: true, expects: ["brief_in_opposition"], question: "Which brief in opposition is this reply answering?" },
  },
};

test("templates that answer nothing need no panel", () => {
  assert.equal(respondsToRequirement([MOTION]), null);
  assert.equal(respondsToRequirement([]), null);
  assert.equal(filingStatus(null, null), "not_needed");
});

test("a required template leads the combined requirement", () => {
  const requirement = respondsToRequirement([DISMISS, REPLY]);
  assert.equal(requirement.required, true);
  assert.equal(requirement.recommended, true);
  assert.equal(requirement.question, "Which brief in opposition is this reply answering?");
  assert.deepEqual(requirement.expects, ["complaint", "brief_in_opposition"]);
  assert.deepEqual(requirement.templateTitles, ["Reply in Support of Motion to Dismiss"]);
});

test("only a required filing holds back generation", () => {
  const optional = respondsToRequirement([DISMISS]);
  const required = respondsToRequirement([REPLY]);
  assert.equal(filingStatus(optional, null), "missing_optional");
  assert.equal(blocksGeneration(optional, null), false);
  assert.equal(filingStatus(required, null), "missing_required");
  assert.equal(blocksGeneration(required, null), true);
  assert.equal(blocksGeneration(required, { id: 9 }), false);
});

test("filing dates are ISO or empty", () => {
  assert.equal(filedOnError(""), "");
  assert.equal(filedOnError("2026-09-12"), "");
  assert.equal(filedOnError("9/12/2026"), "Give the filing date as YYYY-MM-DD.");
});

test("labels read as words", () => {
  assert.equal(filingKindLabel("brief_in_opposition"), "Brief in opposition");
  assert.equal(filingKindLabel("notice_of_appeal"), "notice of appeal");
  assert.equal(caseFileOptionLabel({ title: "Opposition.pdf", date: "2026-09-12T10:00:00Z" }), "Opposition.pdf (2026-09-12)");
  assert.equal(caseFileOptionLabel({ title: "Lease.pdf", date: "" }), "Lease.pdf");
});

test("the source summary says where the text comes from", () => {
  assert.match(sourceSummary({ sourceType: "matter_document" }), /read from LegalServer/);
  assert.equal(
    sourceSummary({ sourceType: "upload", originalFilename: "opp.pdf", pageCount: 12, exhibits: [{}, {}] }),
    "Uploaded opp.pdf · 12 pages · 2 attached exhibits set aside.",
  );
});

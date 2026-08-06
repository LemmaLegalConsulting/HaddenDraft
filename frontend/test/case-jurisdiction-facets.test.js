import assert from "node:assert/strict";
import test from "node:test";

import {
  caseCount,
  jurisdictionFacets,
  jurisdictionOf,
  narrowResults,
  selectionAfterNarrowing,
} from "../src/components/caseJurisdictionFacets.js";

const caseResult = (id, county, extra = {}) => ({
  id,
  sourceKind: "local_cases",
  metadata: { county, ...extra },
});
const treatise = (id) => ({ id, sourceKind: "rag", metadata: {} });

const RESULTS = [
  caseResult("c1", "Cuyahoga County"),
  treatise("t1"),
  caseResult("c2", "Franklin County"),
  caseResult("c3", "Cuyahoga"), // the corpus spells the same county both ways
  treatise("t2"),
  caseResult("c4", "Hamilton County"),
];

test("chips count the counties present, commonest first", () => {
  assert.deepEqual(jurisdictionFacets(RESULTS), [
    { value: "cuyahoga county", label: "Cuyahoga County", count: 2 },
    { value: "franklin county", label: "Franklin County", count: 1 },
    { value: "hamilton county", label: "Hamilton County", count: 1 },
  ]);
});

test("one county spelled two ways is one chip, not two half-empty ones", () => {
  const facets = jurisdictionFacets([caseResult("a", "Summit"), caseResult("b", "Summit County")]);
  assert.deepEqual(facets, []); // one bucket, so nothing to choose between
  assert.equal(jurisdictionOf(caseResult("a", "Summit")).key, jurisdictionOf(caseResult("b", "Summit County")).key);
});

test("a single county offers nothing to choose between, so no chips", () => {
  assert.deepEqual(jurisdictionFacets([caseResult("c1", "Cuyahoga County"), treatise("t1")]), []);
  assert.deepEqual(jurisdictionFacets([treatise("t1")]), []);
  assert.deepEqual(jurisdictionFacets([]), []);
});

test("a case with no county is counted, not dropped", () => {
  const facets = jurisdictionFacets([caseResult("c1", "Cuyahoga County"), caseResult("c2", "")]);
  assert.deepEqual(facets.map((facet) => facet.label), ["Cuyahoga County", "Unattributed"]);
  assert.equal(facets.reduce((total, facet) => total + facet.count, 0), 2);
});

test("court then jurisdiction stand in when no county is recorded", () => {
  assert.deepEqual(jurisdictionOf(caseResult("c", "", { court: "Cleveland Municipal Court" })), {
    key: "cleveland municipal court",
    label: "Cleveland Municipal Court",
  });
  assert.deepEqual(jurisdictionOf(caseResult("c", "", { court: "", jurisdiction: "Ohio" })), {
    key: "ohio",
    label: "Ohio",
  });
  assert.deepEqual(jurisdictionOf({ sourceKind: "local_cases" }), { key: "", label: "Unattributed" });
});

test("narrowing keeps non-case results whatever chip is active", () => {
  const narrowed = narrowResults(RESULTS, "cuyahoga county");
  assert.deepEqual(narrowed.map((result) => result.id), ["c1", "t1", "c3", "t2"]);
});

test("no chip means everywhere", () => {
  assert.equal(narrowResults(RESULTS, "").length, RESULTS.length);
  assert.equal(caseCount(RESULTS), 4);
});

test("a chip left over from an earlier search does not blank the list", () => {
  assert.deepEqual(narrowResults(RESULTS, "county that is not here"), RESULTS);
});

test("narrowing deselects the cases it hides and keeps the rest", () => {
  const selected = RESULTS.map((result) => result.id);
  assert.deepEqual(selectionAfterNarrowing(RESULTS, "cuyahoga county", selected), ["c1", "t1", "c3", "t2"]);
});

test("deselecting on narrow does not resurrect a case the reader unticked", () => {
  assert.deepEqual(selectionAfterNarrowing(RESULTS, "cuyahoga county", ["c1", "t1"]), ["c1", "t1"]);
});

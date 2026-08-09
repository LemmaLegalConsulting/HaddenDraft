import assert from "node:assert/strict";
import test from "node:test";

import { DEFAULT_CASE_FILTERS, activeFilterCount, describeFilters } from "../src/components/caseFilters.js";

test("the default view counts as unfiltered", () => {
  assert.equal(activeFilterCount(DEFAULT_CASE_FILTERS), 0);
  assert.equal(activeFilterCount({}), 0);
});

test("each departure from the default view is counted", () => {
  assert.equal(activeFilterCount({ ...DEFAULT_CASE_FILTERS, status: "closed" }), 1);
  assert.equal(activeFilterCount({ status: "all", assigned: "mine", problem: "51 Medicaid", sort: "opened" }), 4);
});

test("the summary says what is being shown and how it is sorted", () => {
  const summary = describeFilters(DEFAULT_CASE_FILTERS, { total: 26, shown: 20 });

  assert.equal(summary, "20 of 26 open cases, sorted by last activity");
});

test("the summary names the narrowing filters", () => {
  const summary = describeFilters(
    { status: "closed", assigned: "mine", problem: "51 Medicaid", sort: "opened" },
    { total: 3, shown: 3 },
  );

  assert.equal(summary, "3 closed cases, cases I handle, 51 Medicaid, sorted by date opened");
});

test("a complete list does not claim to be a partial one", () => {
  assert.equal(describeFilters(DEFAULT_CASE_FILTERS, { total: 4, shown: 4 }), "4 open cases, sorted by last activity");
});

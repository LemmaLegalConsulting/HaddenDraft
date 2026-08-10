import assert from "node:assert/strict";
import test from "node:test";

import {
  activeFilters,
  catalogParams,
  filterCount,
  hasMore,
  orderedFacets,
  pageSummary,
  removeFacetValue,
  toggleFacetValue,
} from "../src/components/caseCatalog.js";

test("picking a second value in one facet widens rather than replaces", () => {
  const one = toggleFacetValue({}, "county", "Cuyahoga County");
  const two = toggleFacetValue(one, "county", "Franklin County");

  assert.deepEqual(two, { county: ["Cuyahoga County", "Franklin County"] });
});

test("unpicking the last value in a facet drops the facet entirely", () => {
  const filters = toggleFacetValue({ court: ["Cleveland Municipal Court"] }, "county", "Cuyahoga County");
  const dropped = toggleFacetValue(filters, "county", "Cuyahoga County");

  assert.deepEqual(dropped, { court: ["Cleveland Municipal Court"] });
  assert.equal(filterCount(filters), 2);
});

test("removing a value that was never picked leaves the narrowing untouched", () => {
  const filters = { county: ["Cuyahoga County"] };

  assert.equal(removeFacetValue(filters, "county", "Summit County"), filters);
  assert.deepEqual(removeFacetValue(filters, "county", "Cuyahoga County"), {});
});

test("each selected value becomes its own undo chip, in reading order", () => {
  const chips = activeFilters(
    { statute: ["Ohio Rev. Code § 1923.04"], county: ["Cuyahoga County", "Summit County"] },
    { county: "County", statute: "Statute cited" },
  );

  assert.deepEqual(chips.map((chip) => `${chip.label}: ${chip.value}`), [
    "County: Cuyahoga County",
    "County: Summit County",
    "Statute cited: Ohio Rev. Code § 1923.04",
  ]);
});

test("a facet repeats its name once per value so the server reads them as alternatives", () => {
  const params = catalogParams({
    query: "  habitability  ",
    filters: { county: ["Cuyahoga County", "Summit County"], decisionYear: ["2016"] },
    sort: "oldest",
    offset: 25,
  });

  assert.deepEqual(params, [
    ["q", "habitability"],
    ["county", "Cuyahoga County"],
    ["county", "Summit County"],
    ["decisionYear", "2016"],
    ["sort", "oldest"],
    ["offset", "25"],
  ]);
});

test("an unnarrowed first page asks for nothing but the default view", () => {
  assert.deepEqual(catalogParams(), []);
  assert.deepEqual(catalogParams({ query: "   ", sort: "newest", offset: 0 }), []);
});

test("facets a corpus never fills in are not offered as ways to narrow", () => {
  const groups = orderedFacets(
    { subsidyProgram: [], county: [{ value: "Cuyahoga County", count: 3 }], judge: [{ value: "Pianka", count: 1 }] },
    { county: "County", judge: "Judge" },
  );

  assert.deepEqual(groups.map((group) => group.facet), ["county", "judge"]);
  assert.equal(groups[0].label, "County");
});

test("the count says how much of the corpus is in view and how much was set aside", () => {
  assert.equal(pageSummary({ total: 532, offset: 0, shown: 25, corpusTotal: 532 }), "1–25 of 532");
  assert.equal(pageSummary({ total: 40, offset: 0, shown: 25, corpusTotal: 532 }), "1–25 of 40 (of 532 imported)");
  assert.equal(pageSummary({ total: 0, corpusTotal: 532 }), "No cases match. 532 in the corpus.");
  assert.equal(pageSummary({ total: 0, corpusTotal: 0 }), "No cases imported yet.");
});

test("more cases are offered only while some remain unshown", () => {
  assert.equal(hasMore({ total: 40, shown: 25 }), true);
  assert.equal(hasMore({ total: 25, shown: 25 }), false);
});

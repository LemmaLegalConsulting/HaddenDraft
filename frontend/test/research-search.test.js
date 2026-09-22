import assert from "node:assert/strict";
import test from "node:test";

import {
  EMPTY_SEARCH,
  activeFilterChips,
  aiStatus,
  buildSearchRequest,
  clearFilters,
  expansionStatus,
  indexStatusLine,
  pageOffsets,
  resultMetaLine,
  resultWarnings,
  snippetSegments,
  toggleFilterValue,
} from "../src/components/researchSearch.js";

const FACETS = [
  { field: "county", label: "County", values: [{ value: "Cuyahoga", count: 4 }] },
  { field: "sourceType", label: "Source type", values: [{ value: "cases", count: 9 }] },
];

test("a search request carries only what was chosen", () => {
  const request = buildSearchRequest({ ...EMPTY_SEARCH, query: "  habitability  " });
  assert.equal(request.query, "habitability");
  assert.deepEqual(request.filters, {});
  assert.equal(request.aiRerank, false);
  assert.equal(request.aiSynthesis, false);
  assert.equal(request.expansion, "thesaurus");
});

test("a case is attached to the search only when one is open", () => {
  assert.equal(buildSearchRequest(EMPTY_SEARCH).matterId, undefined);
  assert.equal(buildSearchRequest(EMPTY_SEARCH, { matterId: 7 }).matterId, 7);
});

test("an emptied facet is removed rather than left as an empty list", () => {
  const withFilter = toggleFilterValue(EMPTY_SEARCH, "county", "Cuyahoga");
  assert.deepEqual(withFilter.filters, { county: ["Cuyahoga"] });
  const without = toggleFilterValue(withFilter, "county", "Cuyahoga");
  assert.deepEqual(without.filters, {});
});

test("narrowing returns to the first page, so results do not start mid-list", () => {
  const state = { ...EMPTY_SEARCH, offset: 40 };
  assert.equal(toggleFilterValue(state, "county", "Cuyahoga").offset, 0);
  assert.equal(clearFilters(state).offset, 0);
});

test("every narrowing in force is offered back as a removable chip", () => {
  const state = toggleFilterValue(toggleFilterValue(EMPTY_SEARCH, "county", "Cuyahoga"), "sourceType", "cases");
  assert.deepEqual(activeFilterChips(state, FACETS), [
    { field: "county", value: "Cuyahoga", label: "County: Cuyahoga", removable: true },
    { field: "sourceType", value: "cases", label: "Source type: cases", removable: true },
  ]);
});

test("a filter typed into the query is shown, and says it is not removed by clicking", () => {
  // court:cleveland never reaches the local filters -- the server parses it out
  // of the query -- so a reader would otherwise see a narrowed list with no
  // sign of what narrowed it.
  const chips = activeFilterChips(EMPTY_SEARCH, FACETS, { court: ["cleveland"] });
  assert.deepEqual(chips, [{ field: "court", value: "cleveland", label: "court: cleveland", removable: false }]);
});

test("a search with no model says so rather than leaving it to be inferred", () => {
  const status = aiStatus({
    retrieval: "deterministic-bm25",
    rerank: { requested: false, applied: false, reason: "No model was asked to reorder them." },
    synthesis: { requested: false, applied: false, reason: "" },
  });
  assert.equal(status.tone, "deterministic");
  assert.match(status.headline, /No AI/);
});

test("a search a model touched names what it did", () => {
  const status = aiStatus({
    rerank: { requested: true, applied: true, window: 25, moved: 6, reason: "A model reordered the first 25 results." },
    synthesis: { requested: true, applied: true, reason: "A model wrote the summary above." },
  });
  assert.equal(status.tone, "assisted");
  assert.match(status.headline, /reordered 25 results/);
  assert.match(status.headline, /wrote the summary/);
  // Which results those were is the server's to say -- it knows the page.
  assert.match(status.detail, /the first 25 results/);
});

test("a model that was asked for and failed is reported, not hidden behind the results", () => {
  const status = aiStatus({
    rerank: { requested: true, applied: false, reason: "The reranker could not be reached." },
    synthesis: { requested: false, applied: false, reason: "" },
  });
  assert.equal(status.tone, "degraded");
  assert.match(status.headline, /could not run/);
  assert.match(status.detail, /could not be reached/);
});

test("expansion lists the extra terms and where each came from", () => {
  const status = expansionStatus({
    mode: "all",
    suppressed: false,
    applied: [
      {
        term: "habitability",
        expansions: [
          { term: "fit and habitable", basis: "thesaurus", verification: "verified", note: "Landlord repair obligations" },
          { term: "warranty", basis: "distributional", verification: "learned", note: "" },
        ],
      },
    ],
    status: { distributional: { available: true } },
  });
  assert.equal(status.terms.length, 2);
  assert.deepEqual(status.terms.map((item) => item.basis), ["thesaurus", "distributional"]);
  assert.match(status.summary, /2 related terms/);
  assert.equal(status.unavailable, "");
});

test("an exact query says why it was not broadened", () => {
  const status = expansionStatus({
    mode: "all",
    suppressed: true,
    suppressedReason: "This query names an exact phrase or citation, so it was run literally.",
    applied: [],
  });
  assert.match(status.summary, /run literally/);
  assert.deepEqual(status.terms, []);
});

test("an unbuilt neighbour table is reported rather than read as having no neighbours", () => {
  const status = expansionStatus({
    mode: "distributional",
    applied: [],
    status: { distributional: { available: false, reason: "Run `manage.py build_research_index`." } },
  });
  assert.match(status.unavailable, /build_research_index/);
});

test("a snippet is split into marked spans without markup reaching the source text", () => {
  const snippet = "… the notice to leave the premises was defective …";
  const segments = snippetSegments(snippet, [
    { start: 6, end: 34, kind: "exact" },
    { start: 39, end: 48, kind: "expansion" },
  ]);
  assert.deepEqual(segments, [
    { text: "… the ", kind: "" },
    { text: "notice to leave the premises", kind: "exact" },
    { text: " was ", kind: "" },
    { text: "defective", kind: "expansion" },
    { text: " …", kind: "" },
  ]);
  assert.equal(segments.map((segment) => segment.text).join(""), snippet);
});

test("overlapping or out-of-range spans never duplicate or drop snippet text", () => {
  const snippet = "rent abatement";
  const segments = snippetSegments(snippet, [
    { start: 0, end: 4, kind: "term" },
    { start: 2, end: 8, kind: "term" },
    { start: 5, end: 99, kind: "term" },
  ]);
  assert.equal(segments.map((segment) => segment.text).join(""), snippet);
});

test("a result line carries what is needed to judge relevance without opening it", () => {
  const line = resultMetaLine({
    corpusLabel: "Case law",
    facets: { court: "Cleveland Municipal Court", county: "Cuyahoga", appellateDistrict: "Eighth District", year: "2019" },
    metadata: { decisionDate: "2019-04-02", publicationStatus: "unpublished", documentTypeLabel: "Holdings" },
  });
  assert.equal(
    line,
    "Case law · Cleveland Municipal Court · Eighth District · 2019-04-02 · unpublished · Holdings",
  );
});

test("a reversed decision and an unchecked one both say so instead of being hidden", () => {
  const warnings = resultWarnings({
    metadata: { supersededOrCriticized: true, warning: "Treatment/currentness has not been checked." },
    missingConcepts: ["escrow"],
  });
  assert.equal(warnings.length, 3);
  assert.match(warnings[0], /reversed, vacated, or criticized/);
  assert.match(warnings[2], /Does not mention: escrow/);
});

test("an ordinance recorded from the enacting act says so", () => {
  const warnings = resultWarnings({ metadata: { textBasis: "enacted_act" } });
  assert.match(warnings[0], /not the chapter as it stands today/);
});

test("a stale index says it is stale", () => {
  const line = indexStatusLine({ documentCount: 15071, documentsByCorpus: { cases: 12878 }, stale: true });
  assert.match(line, /15,071 passages/);
  assert.match(line, /has changed since this index was built/);
});

test("paging stops at both ends of the result set", () => {
  assert.deepEqual(pageOffsets(0, 20, 0), { hasPrevious: false, hasNext: false, previous: 0, next: 20, from: 0, to: 0 });
  const middle = pageOffsets(45, 20, 20);
  assert.equal(middle.hasPrevious, true);
  assert.equal(middle.hasNext, true);
  assert.equal(middle.from, 21);
  assert.equal(middle.to, 40);
  assert.equal(pageOffsets(45, 20, 40).hasNext, false);
});

test("a half-failed AI request is reported as degraded, not as AI working", () => {
  const status = aiStatus({
    rerank: { requested: true, applied: true, window: 20, reason: "A model reordered the first 20 results." },
    synthesis: { requested: true, applied: false, reason: "The answer could not be generated." },
  });
  assert.equal(status.tone, "degraded");
  assert.match(status.headline, /reordered 20 results/);
  assert.match(status.headline, /the summary could not/);
});

test("a thesaurus that could not be read is reported, not read as a corpus with nothing in it", () => {
  const status = expansionStatus({
    mode: "thesaurus",
    applied: [],
    status: { thesaurus: { available: false }, distributional: { available: true } },
  });
  assert.match(status.unavailable, /reviewed thesaurus could not be read/);
});

test("a search using only the reviewed thesaurus does not complain about the learned table", () => {
  const status = expansionStatus({
    mode: "thesaurus",
    applied: [],
    status: { thesaurus: { available: true }, distributional: { available: false, reason: "Not built." } },
  });
  assert.equal(status.unavailable, "");
});

test("an index still being built says so rather than reporting an empty corpus", () => {
  assert.match(indexStatusLine({ building: true, documentCount: 0, documentsByCorpus: {} }), /Preparing the index/);
});

import assert from "node:assert/strict";
import test from "node:test";

import {
  INDICATOR_DELAY_MS,
  SLOW_AFTER_MS,
  catalogLabel,
  documentLoadLabel,
  filterLabel,
  isSlow,
  shouldShowIndicator,
  slowExplanation,
} from "../src/components/loadingStatus.js";

test("a wait short enough to feel instant shows nothing at all", () => {
  assert.equal(shouldShowIndicator({ busy: true, elapsedMs: 40 }), false);
  assert.equal(shouldShowIndicator({ busy: true, elapsedMs: INDICATOR_DELAY_MS }), true);
});

test("nothing is announced when nothing is loading, however long ago it was", () => {
  assert.equal(shouldShowIndicator({ busy: false, elapsedMs: 9000 }), false);
  assert.equal(isSlow({ busy: false, elapsedMs: 9000 }), false);
  assert.equal(shouldShowIndicator(), false);
});

test("a wait past the slow threshold earns an explanation of what is taking time", () => {
  assert.equal(isSlow({ busy: true, elapsedMs: SLOW_AFTER_MS - 1 }), false);
  assert.equal(isSlow({ busy: true, elapsedMs: SLOW_AFTER_MS }), true);
  assert.match(slowExplanation("document"), /first time/);
  assert.match(slowExplanation("catalog"), /counted/);
  assert.equal(slowExplanation("something else"), "Still working.");
});

test("opening a document names the document and its size", () => {
  assert.equal(
    documentLoadLabel({ title: "Ohio Revised Code", sectionCount: 652 }),
    "Opening Ohio Revised Code — 652 sections",
  );
  assert.equal(documentLoadLabel({ title: "The Green Book", sectionCount: 1 }), "Opening The Green Book — 1 section");
  assert.equal(documentLoadLabel({ title: "A Book" }), "Opening A Book");
  assert.equal(documentLoadLabel(null), "Opening the document");
});

test("filtering says what is being filtered and for what", () => {
  assert.equal(
    filterLabel({ title: "Ohio Revised Code" }, "5321.04"),
    "Filtering the contents of Ohio Revised Code for “5321.04”",
  );
  assert.equal(filterLabel(null, "rent"), "Filtering the contents for “rent”");
});

test("the catalog wait distinguishes a first load from a narrowing and from paging", () => {
  assert.equal(catalogLabel({ corpusTotal: 532 }), "Loading 532 cases");
  assert.equal(catalogLabel({}), "Loading the case catalog");
  assert.equal(catalogLabel({ corpusTotal: 532, appending: true }), "Loading more cases");
  assert.equal(
    catalogLabel({ corpusTotal: 532, filterCount: 2 }),
    "Narrowing 532 cases by 2 filters",
  );
  assert.equal(
    catalogLabel({ corpusTotal: 532, query: " habitability ", filterCount: 1 }),
    "Narrowing 532 cases by “habitability” and 1 filter",
  );
});

import assert from "node:assert/strict";
import test from "node:test";

import {
  applyRecommendations,
  groupByTopic,
  moveSection,
  readingGradeLabel,
  reviewWarnings,
  selectedSections,
  toggleSection,
} from "../src/components/adviceLetter.js";

const SECTIONS = [
  { slug: "decarlo", title: "DeCarlo", topic: "Presenting Defenses", needsReview: true, reviewReason: "2 comments dropped" },
  { slug: "zoom", title: "Getting Zoom Info", topic: "Misc.", needsReview: false },
  { slug: "seal", title: "Motion to Seal", topic: "Pro se How-To", needsReview: false },
];

test("sections group by topic in a stable order", () => {
  const groups = groupByTopic(SECTIONS);
  assert.deepEqual(groups.map((group) => group.topic), ["Misc.", "Presenting Defenses", "Pro se How-To"]);
});

test("a section with no topic falls under Other", () => {
  const groups = groupByTopic([{ slug: "x", title: "X", topic: "" }]);
  assert.equal(groups[0].topic, "Other");
});

test("selection is ordered, so a letter reads in the order it was built", () => {
  let selected = [];
  selected = toggleSection(selected, "seal");
  selected = toggleSection(selected, "decarlo");
  assert.deepEqual(selected, ["seal", "decarlo"]);
});

test("toggling an already chosen section removes it", () => {
  assert.deepEqual(toggleSection(["seal", "decarlo"], "seal"), ["decarlo"]);
});

test("a section can be moved through the order", () => {
  assert.deepEqual(moveSection(["a", "b", "c"], "c", -1), ["a", "c", "b"]);
  assert.deepEqual(moveSection(["a", "b", "c"], "a", 1), ["b", "a", "c"]);
});

test("moving past either end leaves the order alone", () => {
  assert.deepEqual(moveSection(["a", "b"], "a", -1), ["a", "b"]);
  assert.deepEqual(moveSection(["a", "b"], "b", 1), ["a", "b"]);
});

test("selected sections resolve in chosen order, skipping unknown slugs", () => {
  const chosen = selectedSections(["seal", "missing", "decarlo"], SECTIONS);
  assert.deepEqual(chosen.map((section) => section.slug), ["seal", "decarlo"]);
});

test("unreviewed sections in the selection are surfaced as warnings", () => {
  const warnings = reviewWarnings(["seal", "decarlo"], SECTIONS);
  assert.equal(warnings.length, 1);
  assert.equal(warnings[0].slug, "decarlo");
  assert.equal(warnings[0].reason, "2 comments dropped");
});

test("a fully reviewed selection warns about nothing", () => {
  assert.deepEqual(reviewWarnings(["seal", "zoom"], SECTIONS), []);
});

test("applying suggestions keeps existing choices and appends new ones", () => {
  const recommendations = [
    { section: { slug: "decarlo" }, score: 80 },
    { section: { slug: "zoom" }, score: 40 },
    { section: { slug: "seal" }, score: 0 },
  ];
  assert.deepEqual(applyRecommendations(["seal"], recommendations), ["seal", "decarlo", "zoom"]);
});

test("applying suggestions twice does not duplicate", () => {
  const recommendations = [{ section: { slug: "decarlo" }, score: 80 }];
  const once = applyRecommendations([], recommendations);
  assert.deepEqual(applyRecommendations(once, recommendations), ["decarlo"]);
});

test("reading grade says whether it clears the target", () => {
  assert.match(readingGradeLabel({ metrics: { flesch_kincaid_grade: 6.2 } }), /within target/);
  assert.match(readingGradeLabel({ metrics: { flesch_kincaid_grade: 10.1 } }), /above the 8th-grade target/);
  assert.equal(readingGradeLabel({}), "");
});

import assert from "node:assert/strict";
import test from "node:test";

import {
  countSections,
  documentSubtitle,
  expandedForFilter,
  sectionCitation,
  shelves,
  toggleNode,
} from "../src/components/libraryBrowse.js";

const DOCUMENTS = [
  { slug: "ohio-revised-code", title: "Ohio Revised Code", contentKind: "statute", jurisdiction: "Ohio", sectionCount: 652 },
  { slug: "green-book", title: "The Green Book", contentKind: "treatise", version: "6th ed. 2025", sectionCount: 13 },
];

const TREE = [
  {
    id: "Chapter 1",
    label: "Chapter 1",
    chunkId: "",
    count: 2,
    children: [
      { id: "Chapter 1/Repairs", label: "Repairs", chunkId: "0001", count: 1, children: [] },
      {
        id: "Chapter 1/Defenses",
        label: "Defenses",
        chunkId: "",
        count: 1,
        children: [{ id: "Chapter 1/Defenses#1", label: "Defenses, part 1", chunkId: "0002", count: 1, children: [] }],
      },
    ],
  },
  { id: "Chapter 2", label: "Chapter 2", chunkId: "0003", count: 1, children: [] },
];

test("statutes and treatises are separate shelves, each keeping its own documents", () => {
  const [treatises, statutes] = shelves(DOCUMENTS);

  assert.deepEqual(treatises.documents.map((item) => item.slug), ["green-book"]);
  assert.deepEqual(statutes.documents.map((item) => item.slug), ["ohio-revised-code"]);
});

test("a shelf with nothing on it still says what it is missing", () => {
  const [treatises] = shelves([]);

  assert.deepEqual(treatises.documents, []);
  assert.match(treatises.empty, /treatise/i);
});

test("a document is labelled with the edition and reach a reader has to check", () => {
  assert.equal(documentSubtitle(DOCUMENTS[0]), "Ohio · 652 sections");
  assert.equal(documentSubtitle(DOCUMENTS[1]), "6th ed. 2025 · 13 sections");
  assert.equal(documentSubtitle(null), "");
});

test("expanding and collapsing one branch leaves the others where they were", () => {
  const opened = toggleNode(["Chapter 2"], "Chapter 1");
  const closed = toggleNode(opened, "Chapter 2");

  assert.deepEqual(opened, ["Chapter 2", "Chapter 1"]);
  assert.deepEqual(closed, ["Chapter 1"]);
});

test("a filtered table of contents opens its branches, or it would hide the matches", () => {
  assert.deepEqual(expandedForFilter(TREE), ["Chapter 1", "Chapter 1/Defenses"]);
  assert.deepEqual(expandedForFilter([]), []);
});

test("the section count covers the whole tree, not just its top level", () => {
  assert.equal(countSections(TREE), 3);
});

test("a section opened from the tree is the same source a citation points at", () => {
  const citation = sectionCitation(DOCUMENTS[0], {
    id: "Chapter 5321/§ 5321.04",
    label: "§ 5321.04",
    chunkId: "orc-5321-04-01",
    citation: "Ohio Rev. Code § 5321.04",
    effectiveDate: "March 27, 1985",
    pages: [],
  });

  assert.equal(citation.sourceKind, "rag");
  assert.equal(citation.metadata.documentSlug, "ohio-revised-code");
  assert.equal(citation.metadata.chunkId, "orc-5321-04-01");
  assert.deepEqual(citation.metadata.sectionPath, ["Chapter 5321", "§ 5321.04"]);
  assert.equal(citation.citation, "Ohio Rev. Code § 5321.04");
});

test("a heading with no chunk behind it opens nothing rather than an empty viewer", () => {
  assert.equal(sectionCitation(DOCUMENTS[0], { id: "Chapter 1", label: "Chapter 1", chunkId: "" }), null);
  assert.equal(sectionCitation(null, { chunkId: "0001" }), null);
});

/**
 * Walking the managed content library as a table of contents.
 *
 * A section reached by expanding the tree has to open the same chunk a
 * citation points at, so nodes carry the generated chunk id and are turned
 * into the citation shape the source modal already knows how to read.
 */

export const SHELVES = [
  { id: "treatise", label: "Treatises and handbooks", empty: "No treatises or handbooks are indexed." },
  { id: "statute", label: "Statutes", empty: "No statute collections are indexed." },
  { id: "ordinance", label: "Local ordinances", empty: "No municipal codes are indexed." },
];

export function shelves(documents = []) {
  return SHELVES.map((shelf) => ({
    ...shelf,
    documents: documents.filter((document) => document.contentKind === shelf.id),
  }));
}

export function documentSubtitle(document) {
  if (!document) return "";
  const parts = [
    document.version,
    document.jurisdiction,
    document.sectionCount ? `${document.sectionCount} section${document.sectionCount === 1 ? "" : "s"}` : "",
    // A municipality can be in the corpus with nothing readable in it yet.
    // Saying "2 declared" is the difference between "we checked and there is
    // no local law here" and "we have not been able to get the text".
    document.pendingCount ? `${document.pendingCount} declared, not yet acquired` : "",
  ];
  return parts.filter(Boolean).join(" · ");
}

export function toggleNode(expandedIds, nodeId) {
  return expandedIds.includes(nodeId)
    ? expandedIds.filter((item) => item !== nodeId)
    : [...expandedIds, nodeId];
}

/**
 * Node ids to open after a filter runs.
 *
 * A filtered table of contents whose branches are all collapsed hides the very
 * sections the reader asked for, so every remaining branch is opened.
 */
export function expandedForFilter(tree = []) {
  const ids = [];
  const walk = (nodes) => {
    nodes.forEach((node) => {
      if (node.children?.length) {
        ids.push(node.id);
        walk(node.children);
      }
    });
  };
  walk(tree);
  return ids;
}

export function countSections(tree = []) {
  return tree.reduce((total, node) => total + (node.count || 0), 0);
}

/** The citation shape `SourceBrowserModal` reads for content-library sources. */
export function sectionCitation(document, node) {
  if (!document || !node?.chunkId) return null;
  return {
    id: `content:${document.slug}:${node.chunkId}`,
    title: `${document.title} — ${node.label}`,
    snippet: "",
    sourceKind: "rag",
    sourceLabel: "Managed legal content library",
    citation: node.citation || "",
    url: "",
    metadata: {
      chunkId: node.chunkId,
      documentSlug: document.slug,
      documentVersion: document.version || "",
      sectionPath: String(node.id || "").split("#")[0].split("/").filter(Boolean),
      pdfPages: node.pages || [],
      sourcePath: document.sourcePath || "",
      jurisdiction: document.jurisdiction || "",
      effectiveDate: node.effectiveDate || "",
    },
  };
}

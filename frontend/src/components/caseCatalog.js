/**
 * Narrowing state for browsing the imported case-law corpus.
 *
 * The research search starts from a question; this starts from the shelf, so
 * the reader's state is a set of facet selections rather than a query, and the
 * server counts each facet against the others.  Values inside one facet are
 * alternatives; facets combine.
 */

export const FACET_ORDER = [
  "county",
  "court",
  "judge",
  "decisionYear",
  "authorityLevel",
  "publicationStatus",
  "treatmentStatus",
  "caseType",
  "subsidyProgram",
  "statute",
  "regulation",
  "issue",
  "caseCitation",
];

export const SORT_OPTIONS = [
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "title", label: "By case name" },
];

export const DEFAULT_PAGE_SIZE = 25;

export function toggleFacetValue(filters, facet, value) {
  const current = filters[facet] || [];
  const next = current.includes(value)
    ? current.filter((item) => item !== value)
    : [...current, value];
  const updated = { ...filters };
  if (next.length) updated[facet] = next;
  else delete updated[facet];
  return updated;
}

export function removeFacetValue(filters, facet, value) {
  if (!(filters[facet] || []).includes(value)) return filters;
  return toggleFacetValue(filters, facet, value);
}

export function filterCount(filters) {
  return Object.values(filters).reduce((total, values) => total + values.length, 0);
}

/** Selected values as flat chips, so a reader can undo one narrowing at a time. */
export function activeFilters(filters, facetLabels = {}) {
  return FACET_ORDER.filter((facet) => (filters[facet] || []).length).flatMap((facet) =>
    filters[facet].map((value) => ({ facet, value, label: facetLabels[facet] || facet })),
  );
}

/** Facet groups in reading order, dropping the ones this corpus never fills in. */
export function orderedFacets(facets = {}, facetLabels = {}) {
  const known = FACET_ORDER.filter((facet) => (facets[facet] || []).length);
  const extra = Object.keys(facets).filter((facet) => !FACET_ORDER.includes(facet) && facets[facet].length);
  return [...known, ...extra].map((facet) => ({
    facet,
    label: facetLabels[facet] || facet,
    items: facets[facet],
  }));
}

/** Query parameters, repeating a facet name once per selected value. */
export function catalogParams({ query = "", filters = {}, sort = "newest", limit = DEFAULT_PAGE_SIZE, offset = 0 } = {}) {
  const params = [];
  if (query.trim()) params.push(["q", query.trim()]);
  FACET_ORDER.forEach((facet) => {
    (filters[facet] || []).forEach((value) => params.push([facet, value]));
  });
  Object.keys(filters)
    .filter((facet) => !FACET_ORDER.includes(facet))
    .forEach((facet) => filters[facet].forEach((value) => params.push([facet, value])));
  if (sort && sort !== "newest") params.push(["sort", sort]);
  if (limit !== DEFAULT_PAGE_SIZE) params.push(["limit", String(limit)]);
  if (offset) params.push(["offset", String(offset)]);
  return params;
}

export function pageSummary({ total = 0, offset = 0, shown = 0, corpusTotal = 0 } = {}) {
  if (!total) return corpusTotal ? `No cases match. ${corpusTotal} in the corpus.` : "No cases imported yet.";
  const first = offset + 1;
  const last = offset + shown;
  const scope = corpusTotal && corpusTotal !== total ? ` (of ${corpusTotal} imported)` : "";
  return `${first}–${last} of ${total}${scope}`;
}

export function hasMore({ total = 0, offset = 0, shown = 0 } = {}) {
  return offset + shown < total;
}

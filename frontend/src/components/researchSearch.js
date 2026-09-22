/**
 * Reading a deterministic research search.
 *
 * Research mode's promise is that a lawyer can tell what the library said and
 * what, if anything, a model said about it. That promise is kept mostly in
 * wording, so the wording lives here in plain JavaScript where it can be
 * tested, rather than inside a component where it can only be looked at.
 *
 * Nothing here decides relevance. The server has already ranked, narrowed and
 * explained; these functions turn that into chips, labels and highlighted
 * spans.
 */

export const EXPANSION_MODES = [
  {
    id: "none",
    label: "Exactly what I typed",
    description: "Only your own words are searched for.",
  },
  {
    id: "thesaurus",
    label: "Reviewed terms of art",
    description: "Adds synonyms from the maintained thesaurus, such as eviction for forcible entry and detainer.",
  },
  {
    id: "distributional",
    label: "Terms learned from this corpus",
    description:
      "Adds neighbours computed offline from how words co-occur here, and only when the table was built " +
      "from the corpus being searched. No model is involved.",
  },
  {
    id: "all",
    label: "Both",
    description: "Reviewed terms of art and learned neighbours together.",
  },
];

export const EMPTY_SEARCH = {
  query: "",
  corpora: [],
  filters: {},
  expansion: "thesaurus",
  aiRerank: false,
  aiSynthesis: false,
  offset: 0,
};

/** The request body for one search, leaving out everything at its default. */
export function buildSearchRequest(state, { matterId = null, limit = 20 } = {}) {
  const filters = Object.fromEntries(
    Object.entries(state.filters || {}).filter(([, values]) => values?.length),
  );
  return {
    query: (state.query || "").trim(),
    corpora: state.corpora || [],
    filters,
    expansion: state.expansion || "thesaurus",
    aiRerank: Boolean(state.aiRerank),
    aiSynthesis: Boolean(state.aiSynthesis),
    limit,
    offset: state.offset || 0,
    ...(matterId ? { matterId } : {}),
  };
}

/** Add or remove one facet value, and return to the first page of results. */
export function toggleFilterValue(state, field, value) {
  const current = state.filters?.[field] || [];
  const next = current.includes(value)
    ? current.filter((item) => item !== value)
    : [...current, value];
  const filters = { ...(state.filters || {}) };
  if (next.length) filters[field] = next;
  else delete filters[field];
  return { ...state, filters, offset: 0 };
}

export function clearFilters(state) {
  return { ...state, filters: {}, corpora: [], offset: 0 };
}

/**
 * Every narrowing currently in force.
 *
 * The server merges two sources of narrowing: the facets a reader clicked and
 * the field filters they typed into the query (`court:cleveland`). Both are
 * shown, because a reader looking at a short result list needs to know what is
 * being left out however it got there. Only the clicked ones can be taken off
 * by clicking; a typed one is removed by editing the query, and a chip that
 * silently did nothing when clicked would be worse than one that says so.
 */
export function activeFilterChips(state, facets = [], appliedFilters = null) {
  const labels = Object.fromEntries(facets.map((facet) => [facet.field, facet.label]));
  const applied = appliedFilters || state.filters || {};
  return Object.entries(applied).flatMap(([field, values]) =>
    (values || []).map((value) => ({
      field,
      value,
      label: `${labels[field] || field}: ${value}`,
      removable: Boolean((state.filters || {})[field]?.includes(value)),
    })),
  );
}

/**
 * One sentence saying whether a model touched this result set.
 *
 * Stated in every state, including the ordinary one. A reader who has to infer
 * "no AI" from the absence of a badge is inferring, and the whole point of the
 * mode is that they do not have to.
 */
export function aiStatus(ai) {
  if (!ai) return { tone: "deterministic", headline: "", detail: "" };
  const rerank = ai.rerank || {};
  const synthesis = ai.synthesis || {};
  const failedParts = [
    rerank.requested && !rerank.applied ? "reordering" : "",
    synthesis.requested && !synthesis.applied ? "the summary" : "",
  ].filter(Boolean);
  const appliedParts = [
    rerank.applied ? `a model reordered ${rerank.window} results` : "",
    synthesis.applied ? "a model wrote the summary" : "",
  ].filter(Boolean);
  const detail = [rerank.requested ? rerank.reason : "", synthesis.requested ? synthesis.reason : ""]
    .filter(Boolean).join(" ");

  // A half-failure is still a failure, and it is the state most likely to
  // mislead: the reader sees a reordered list, assumes the summary they asked
  // for is simply still loading, and never learns it did not run.
  if (failedParts.length && appliedParts.length) {
    return {
      tone: "degraded",
      headline: `AI partly ran: ${appliedParts.join(" and ")}, but ${failedParts.join(" and ")} could not.`,
      detail,
    };
  }
  if (failedParts.length) {
    return {
      tone: "degraded",
      headline: "AI was asked for and could not run. These results are the library's own.",
      detail,
    };
  }
  if (appliedParts.length) {
    return { tone: "assisted", headline: `AI is on: ${appliedParts.join(", and ")}.`, detail };
  }
  return {
    tone: "deterministic",
    headline: "No AI. These results came from searching the corpus text.",
    detail: rerank.reason || "",
  };
}

/** What the expansion layers did, and what they could not do. */
export function expansionStatus(expansion) {
  if (!expansion) return { summary: "", terms: [], unavailable: "" };
  if (expansion.suppressed) {
    return { summary: expansion.suppressedReason, terms: [], unavailable: "" };
  }
  const terms = (expansion.applied || []).flatMap((entry) =>
    (entry.expansions || []).map((item) => ({
      from: entry.term,
      term: item.term,
      basis: item.basis,
      verification: item.verification,
      note: item.note,
    })),
  );
  // Both layers report themselves, because either one being absent is a
  // narrower search than the reader asked for. A missing thesaurus is the
  // easier one to miss: it is the default mode, and its absence just looks
  // like a corpus with nothing in it.
  const status = expansion.status || {};
  const wantsLearned = expansion.mode === "distributional" || expansion.mode === "all";
  const wantsThesaurus = expansion.mode === "thesaurus" || expansion.mode === "all";
  const missing = [];
  if (wantsThesaurus && status.thesaurus && !status.thesaurus.available) {
    missing.push("The reviewed thesaurus could not be read, so no terms of art were added.");
  }
  if (wantsLearned && !status.distributional?.available) {
    // A table built from another corpus is a different problem from no table
    // at all, and the reader needs to be able to tell them apart: one is a
    // command they have not run, the other is a file that does not describe
    // what they are searching.
    missing.push(status.distributional?.reason || "The learned term-neighbour table has not been built.");
  }
  const unavailable = missing.join(" ");
  return {
    summary: terms.length
      ? `Also searched for ${terms.length} related term${terms.length === 1 ? "" : "s"}.`
      : "Only the words you typed were searched for.",
    terms,
    unavailable,
  };
}

/**
 * Split a snippet into plain and marked segments.
 *
 * The server returns match offsets rather than marked-up text, so the
 * highlighting cannot introduce markup into a legal source. Offsets are into
 * the snippet as returned, including its leading ellipsis.
 */
export function snippetSegments(snippet = "", matches = []) {
  const ordered = [...matches].sort((first, second) => first.start - second.start);
  const segments = [];
  let cursor = 0;
  ordered.forEach((match) => {
    const start = Math.max(cursor, match.start);
    const end = Math.min(snippet.length, match.end);
    if (end <= start) return;
    if (start > cursor) segments.push({ text: snippet.slice(cursor, start), kind: "" });
    segments.push({ text: snippet.slice(start, end), kind: match.kind });
    cursor = end;
  });
  if (cursor < snippet.length) segments.push({ text: snippet.slice(cursor), kind: "" });
  return segments.filter((segment) => segment.text);
}

/** The metadata line under a result, in the order a lawyer reads it. */
export function resultMetaLine(result) {
  const facets = result?.facets || {};
  const metadata = result?.metadata || {};
  return [
    result?.corpusLabel,
    facets.court,
    facets.county && !facets.court ? facets.county : "",
    facets.municipality,
    facets.appellateDistrict,
    metadata.decisionDate || facets.year,
    metadata.publicationStatus,
    metadata.documentTypeLabel,
  ].filter(Boolean).join(" · ");
}

/**
 * Warnings a result carries about itself.
 *
 * A decision whose treatment was never checked, an ordinance recorded from the
 * act that created it rather than the chapter as it stands, a partial match --
 * each is something the reader has to know before relying on the result, and
 * none of them is a reason to hide it.
 */
export function resultWarnings(result) {
  const metadata = result?.metadata || {};
  const warnings = [];
  if (metadata.supersededOrCriticized) {
    warnings.push("This decision has been reversed, vacated, or criticized. Read the later history.");
  }
  if (metadata.warning) warnings.push(metadata.warning);
  if (metadata.textBasis === "enacted_act") {
    warnings.push("Recorded from the act that enacted it, not the chapter as it stands today.");
  }
  if (metadata.resultType === "coverage-notice") {
    warnings.push("This local law is declared in the coverage scope but its text has not been acquired.");
  }
  if (result?.missingConcepts?.length) {
    warnings.push(`Does not mention: ${result.missingConcepts.join(", ")}.`);
  }
  return warnings;
}

/** A one-line description of how fresh and how complete the index is. */
export function indexStatusLine(index) {
  if (!index) return "";
  // A worker that has just started builds the index in the background. Saying
  // "searching 0 passages" while that happens reads as an empty corpus.
  if (index.building) {
    return "Preparing the index for this corpus. The first search will wait a few seconds for it.";
  }
  const counts = Object.entries(index.documentsByCorpus || {})
    .map(([corpus, count]) => `${count.toLocaleString()} ${corpus}`)
    .join(", ");
  const stale = index.stale ? " The corpus has changed since this index was built; it will rebuild on the next search." : "";
  return `Searching ${(index.documentCount || 0).toLocaleString()} passages (${counts}).${stale}`;
}

/** Page offsets for a result count, so paging never runs past the end. */
export function pageOffsets(total, limit, offset) {
  const safeLimit = Math.max(1, limit || 20);
  return {
    hasPrevious: offset > 0,
    hasNext: offset + safeLimit < total,
    previous: Math.max(0, offset - safeLimit),
    next: offset + safeLimit,
    from: total ? offset + 1 : 0,
    to: Math.min(total, offset + safeLimit),
  };
}

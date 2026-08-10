/**
 * Saying what the reader is waiting for.
 *
 * Opening a code or recounting the corpus takes long enough to look like
 * nothing happened, so a wait needs a name ("Opening the Ohio Revised Code")
 * rather than a bare spinner. Two thresholds keep that honest: a short delay
 * before showing anything, because a cached document arrives in a few
 * milliseconds and a flashed spinner reads as a glitch, and a longer one after
 * which the wait is worth explaining instead of leaving the reader guessing.
 */

export const INDICATOR_DELAY_MS = 250;
export const SLOW_AFTER_MS = 3000;

export function shouldShowIndicator({ busy = false, elapsedMs = 0, delayMs = INDICATOR_DELAY_MS } = {}) {
  return Boolean(busy) && elapsedMs >= delayMs;
}

export function isSlow({ busy = false, elapsedMs = 0, slowAfterMs = SLOW_AFTER_MS } = {}) {
  return Boolean(busy) && elapsedMs >= slowAfterMs;
}

/** The one-line reason a wait is taking longer than it looks like it should. */
export function slowExplanation(kind) {
  if (kind === "document") return "A large document is read and indexed the first time it is opened.";
  if (kind === "catalog") return "Every imported case is being counted against the narrowing in force.";
  return "Still working.";
}

export function documentLoadLabel(document) {
  if (!document) return "Opening the document";
  const sections = document.sectionCount
    ? ` — ${document.sectionCount} section${document.sectionCount === 1 ? "" : "s"}`
    : "";
  return `Opening ${document.title}${sections}`;
}

export function filterLabel(document, query) {
  const where = document?.title ? ` of ${document.title}` : "";
  return `Filtering the contents${where} for “${query}”`;
}

export function catalogLabel({ query = "", filterCount = 0, corpusTotal = 0, appending = false } = {}) {
  if (appending) return "Loading more cases";
  const narrowing = [
    query.trim() ? `“${query.trim()}”` : "",
    filterCount ? `${filterCount} filter${filterCount === 1 ? "" : "s"}` : "",
  ].filter(Boolean).join(" and ");
  if (!narrowing) return corpusTotal ? `Loading ${corpusTotal} cases` : "Loading the case catalog";
  return `Narrowing ${corpusTotal ? `${corpusTotal} cases ` : "cases "}by ${narrowing}`;
}

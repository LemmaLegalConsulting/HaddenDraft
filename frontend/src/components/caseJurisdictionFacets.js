// Narrowing case-law results by where they were decided.
//
// The connector deliberately does not filter cases by jurisdiction: municipal
// and common pleas decisions are persuasive everywhere and binding nowhere, so
// one from the next county over is worth reading. That leaves the reader to
// narrow, which they can only do fairly if they can see what they are setting
// aside. Hence chips carrying counts, built from the results actually in hand.
//
// Only case-law results are narrowed. Treatise and statute results were not
// decided by a court and stay visible whatever chip is active, or picking a
// county would silently drop the statute the answer rests on.
//
// Grouping is by county rather than by court. Counties are how a lawyer thinks
// about how far afield a case is, and there are far fewer of them: one corpus
// query returns cases from thirteen distinct courts but half as many counties.
// The corpus records a county two ways -- "Cuyahoga" and "Cuyahoga County" --
// so the name is normalized before grouping, or the same county would appear as
// two chips that each hide half its cases.

export const CASE_SOURCE_KIND = "local_cases";

const COUNTY_SUFFIX = /\s+county$/i;
const UNATTRIBUTED = "Unattributed";

function isCase(result) {
  return result?.sourceKind === CASE_SOURCE_KIND;
}

function countyLabel(value) {
  const bare = (value || "").trim().replace(COUNTY_SUFFIX, "").trim();
  return bare ? `${bare} County` : "";
}

/**
 * The bucket a case result belongs to: `{ key, label }`.
 *
 * `key` is what narrowing compares, so it survives the corpus spelling a county
 * two ways. County first, then the court, then the recorded jurisdiction.
 */
export function jurisdictionOf(result) {
  const metadata = result?.metadata || {};
  const county = countyLabel(metadata.county);
  if (county) return { key: county.toLowerCase(), label: county };
  const fallback = (metadata.court || metadata.jurisdiction || "").trim();
  if (fallback) return { key: fallback.toLowerCase(), label: fallback };
  return { key: "", label: UNATTRIBUTED };
}

/**
 * Chips for the counties present in `results`, commonest first, ties by name.
 *
 * Returns [] when there is nothing to choose between — no cases, or every case
 * from one county — because a lone chip that narrows to everything is noise.
 * Cases with no county recorded get an "Unattributed" chip rather than being
 * dropped, so the counts always add up to the number of cases shown.
 */
export function jurisdictionFacets(results = []) {
  const buckets = new Map();
  for (const result of results) {
    if (!isCase(result)) continue;
    const { key, label } = jurisdictionOf(result);
    const bucket = buckets.get(key) || { value: key, label, count: 0 };
    bucket.count += 1;
    buckets.set(key, bucket);
  }
  if (buckets.size < 2) return [];
  return [...buckets.values()].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

/** Total number of case-law results, for the "Everywhere" chip. */
export function caseCount(results = []) {
  return results.filter(isCase).length;
}

/**
 * `results` with case law narrowed to the bucket `jurisdiction`.
 *
 * An empty `jurisdiction` means "everywhere", and a bucket no longer present
 * also falls back to everywhere rather than to an empty list, so a stale chip
 * from a previous search cannot blank the results.
 */
export function narrowResults(results = [], jurisdiction = "") {
  if (!jurisdiction) return results;
  const inBucket = (result) => isCase(result) && jurisdictionOf(result).key === jurisdiction;
  if (!results.some(inBucket)) return results;
  return results.filter((result) => !isCase(result) || inBucket(result));
}

/**
 * Selection restricted to what a reader can currently see.
 *
 * Narrowing has to deselect the cases it hides. Leaving them selected would
 * push sources into a draft that the reader had visibly excluded, which is the
 * kind of quiet mismatch this workflow exists to prevent.
 */
export function selectionAfterNarrowing(results = [], jurisdiction = "", selectedIds = []) {
  const visible = new Set(narrowResults(results, jurisdiction).map((result) => result.id));
  return selectedIds.filter((id) => visible.has(id));
}

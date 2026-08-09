/** How the case-list filters read back to the advocate who set them. */

export const DEFAULT_CASE_FILTERS = { status: "open", assigned: "all", problem: "", sort: "activity" };

const STATUS_LABELS = { open: "Open", closed: "Closed", all: "Open and closed" };
const ASSIGNED_LABELS = { all: "", mine: "cases I handle" };
const SORT_LABELS = { activity: "by last activity", opened: "by date opened" };

/**
 * How many filters differ from the default view.
 *
 * Shown on the filter button so a narrowed list never looks like an empty one:
 * "no cases" and "no cases matching three filters" are different problems.
 */
export function activeFilterCount(filters = {}) {
  return ["status", "assigned", "problem", "sort"].filter((key) => (
    (filters[key] ?? DEFAULT_CASE_FILTERS[key]) !== DEFAULT_CASE_FILTERS[key]
  )).length;
}

/** A one-line summary of what the list is currently showing. */
export function describeFilters(filters = {}, { total = 0, shown = 0 } = {}) {
  const status = STATUS_LABELS[filters.status] ?? STATUS_LABELS.open;
  const parts = [`${status.toLowerCase()} cases`];
  const assigned = ASSIGNED_LABELS[filters.assigned];
  if (assigned) parts.push(assigned);
  if (filters.problem) parts.push(filters.problem);
  const sorted = SORT_LABELS[filters.sort] ?? SORT_LABELS.activity;
  const counted = total && shown < total ? `${shown} of ${total} ` : `${shown} `;
  return `${counted}${parts.join(", ")}, sorted ${sorted}`;
}

// Selection and ordering rules for the advice-letter picker.
//
// Kept out of the component so the ordering behaviour can be tested without a
// browser. The order an advocate picks sections in is the order they appear in
// the letter, which is the one piece of state a naive checkbox list gets wrong.

export function groupByTopic(sections) {
  const groups = new Map();
  for (const section of sections) {
    const topic = section.topic || "Other";
    if (!groups.has(topic)) groups.set(topic, []);
    groups.get(topic).push(section);
  }
  return [...groups.entries()]
    .map(([topic, items]) => ({ topic, sections: items }))
    .sort((a, b) => a.topic.localeCompare(b.topic));
}

// Selection is an ordered list, not a set: adding a section appends it, so the
// letter reads in the order the advocate built it.
export function toggleSection(selected, slug) {
  return selected.includes(slug)
    ? selected.filter((item) => item !== slug)
    : [...selected, slug];
}

export function moveSection(selected, slug, direction) {
  const index = selected.indexOf(slug);
  if (index < 0) return selected;
  const target = index + direction;
  if (target < 0 || target >= selected.length) return selected;
  const next = [...selected];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function selectedSections(selected, sections) {
  const bySlug = new Map(sections.map((section) => [section.slug, section]));
  return selected.map((slug) => bySlug.get(slug)).filter(Boolean);
}

// Sections that still need an attorney's eye are offered, so the advocate has
// to be told which of the ones they picked are unverified.
export function reviewWarnings(selected, sections) {
  return selectedSections(selected, sections)
    .filter((section) => section.needsReview)
    .map((section) => ({
      slug: section.slug,
      title: section.title,
      reason: section.reviewReason || "Not reviewed yet.",
    }));
}

export function applyRecommendations(selected, recommendations) {
  const suggested = recommendations
    .filter((entry) => entry.score > 0)
    .map((entry) => entry.section.slug);
  // Keep anything already chosen; append suggestions not already present.
  return [...selected, ...suggested.filter((slug) => !selected.includes(slug))];
}

export function estimatePages(readability) {
  const pages = readability?.estimatedPages;
  return typeof pages === "number" ? pages : null;
}

export function readingGradeLabel(readability) {
  const grade = readability?.metrics?.flesch_kincaid_grade;
  if (typeof grade !== "number") return "";
  const target = grade <= 8 ? "within target" : "above the 8th-grade target";
  return `Reading grade ${grade} (${target})`;
}

// How a saved session reads in a list: what it is, what it was for, how far
// it got. Derived from the server's summary row only.

export function sessionRowLabels(row) {
  const documents = (row.plannedDocuments || []).filter(Boolean);
  const title = row.templateTitle || documents.join(", ") || "Drafting session without a document yet";
  const count = row.draftCount || 0;
  const progress = count > 0 ? `${count} ${count === 1 ? "document" : "documents"} drafted` : documents.length ? "Planned, not drafted" : "Not planned yet";
  return { title, goal: row.goal || "", progress };
}

// Append a page of rows without repeating one already listed.
export function mergeSessionPages(current, incoming) {
  const known = new Set(current.map((row) => row.id));
  return [...current, ...incoming.filter((row) => !known.has(row.id))];
}

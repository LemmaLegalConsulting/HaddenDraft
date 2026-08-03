/**
 * Read the filing package a drafting session produced.
 *
 * The backend records what each document is within the package and how the
 * documents depend on each other. This turns that graph into sentences, and
 * pulls the cross-document validation findings out of the per-document
 * findings so package problems can be read in one place.
 */

export const ROLE_LABELS = {
  motion: "Motion",
  memorandum: "Memorandum",
  declaration: "Declaration",
  proposed_order: "Proposed order",
  answer: "Answer",
  hearing_statement: "Hearing statement",
  exhibit: "Exhibit",
  other: "Document",
};

const RELATIONSHIP_PHRASES = {
  implements_relief: "implements the relief requested by",
  incorporates: "is incorporated into",
  depends_on: "supports",
  cites: "cites",
  authenticates_exhibit: "authenticates an exhibit for",
};

export const PACKAGE_FINDING_CATEGORY = "package_consistency";

export function roleLabel(role) {
  return ROLE_LABELS[role] || ROLE_LABELS.other;
}

export function relationshipPhrase(relationshipType) {
  return RELATIONSHIP_PHRASES[relationshipType] || relationshipType.replace(/_/g, " ");
}

/**
 * Documents in the package with their roles, and relationships as readable lines.
 */
export function packageView(packageData) {
  const documents = packageData?.documents || [];
  const titles = new Map(documents.map((item) => [item.id, item.title]));
  return {
    documents: documents.map((item) => ({ ...item, roleLabel: roleLabel(item.role) })),
    relationships: (packageData?.relationships || [])
      .filter((item) => titles.has(item.sourceDocumentId) && titles.has(item.targetDocumentId))
      .map((item) => ({
        ...item,
        description: `${titles.get(item.sourceDocumentId)} ${relationshipPhrase(item.relationshipType)} ${titles.get(item.targetDocumentId)}.`,
      })),
    isPackage: documents.length > 1,
  };
}

/**
 * Cross-document findings across every document validated so far.
 *
 * Findings live on the document they were raised against, so a reviewer looking
 * at one document cannot otherwise see that another document disagrees with it.
 */
export function packageFindings(drafts = []) {
  return drafts.flatMap((draft) => (
    (draft.validationFlags || [])
      .filter((finding) => finding.category === PACKAGE_FINDING_CATEGORY)
      .map((finding) => ({
        ...finding,
        documentId: draft.id,
        documentTitle: draft.title,
      }))
  ));
}

/**
 * Documents nobody has validated yet, so an empty package-findings list is not
 * mistaken for a checked package. A document's findings are empty both when it
 * is clean and when it has never been run.
 */
export function unvalidatedDocuments(drafts = [], validatedDraftIds = []) {
  return drafts.filter((draft) => !validatedDraftIds.includes(draft.id)).map((draft) => draft.title);
}

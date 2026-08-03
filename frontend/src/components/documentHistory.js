/**
 * Shape the component-history and operation APIs into what a reviewer reads.
 *
 * The backend keeps every version of every section and every change proposed
 * against a document. This turns that into two answers: "where did this section's
 * text come from, and what may it be cited for" and "what has been done to this
 * document".
 */

export const ORIGIN_LABELS = {
  template: "From template",
  ai: "AI generated",
  human: "Edited by reviewer",
  validation_repair: "Validation repair",
  rollback: "Restored earlier version",
};

export const ROLE_LABELS = {
  record_evidence: "Record evidence",
  legal_authority: "Legal authority",
  procedural_rule: "Procedural rule",
  example_language: "Example language only",
  background_reference: "Background",
};

export const OPERATION_LABELS = {
  replace_component: "Replaced section",
  insert_component: "Added section",
  delete_component: "Removed section",
  move_component: "Moved section",
  revert_component: "Restored earlier version",
};

// Roles a draft may cite as authority; mirrors CITABLE_ROLES on the backend.
const CITABLE_ROLES = new Set(["legal_authority", "procedural_rule"]);
const STYLE_ONLY_ROLES = new Set(["example_language"]);

export function originLabel(origin) {
  return ORIGIN_LABELS[origin] || origin || "Unknown";
}

export function roleLabel(role) {
  return ROLE_LABELS[role] || role || "Unclassified";
}

export function operationLabel(operationType) {
  return OPERATION_LABELS[operationType] || operationType || "Change";
}

/**
 * Per-section history, newest version first, with the sources each version used.
 */
export function componentHistoryEntries(components = []) {
  return components.map((component) => {
    const versions = [...(component.versions || [])].sort((left, right) => right.sequence - left.sequence);
    const current = versions.find((version) => version.sequence === component.currentVersionSequence) || versions[0] || null;
    return {
      id: component.id,
      stableKey: component.stableKey,
      label: component.label || component.stableKey,
      removed: Boolean(component.removed),
      versionCount: versions.length,
      currentSequence: component.currentVersionSequence ?? null,
      versions: versions.map((version) => ({
        ...version,
        originLabel: originLabel(version.origin),
        isCurrent: version.sequence === component.currentVersionSequence,
      })),
      support: supportSummary(current?.sourceBindings || []),
    };
  });
}

/**
 * What a section's current text is allowed to rest on.
 */
export function supportSummary(bindings = []) {
  const roles = new Map();
  bindings.forEach((binding) => {
    const entry = roles.get(binding.role) || { role: binding.role, label: roleLabel(binding.role), sources: [] };
    entry.sources.push({
      key: binding.sourceKey,
      label: binding.label || binding.citation || binding.sourceKey,
      citation: binding.citation || "",
      excerpt: binding.excerpt || "",
      verified: Boolean(binding.verified),
    });
    roles.set(binding.role, entry);
  });
  const groups = [...roles.values()];
  return {
    groups,
    total: bindings.length,
    hasAuthority: groups.some((group) => CITABLE_ROLES.has(group.role)),
    styleOnlyOnly: groups.length > 0 && groups.every((group) => STYLE_ONLY_ROLES.has(group.role)),
  };
}

/**
 * The document's change log, newest first, as sentences a reviewer can scan.
 */
export function changeLogEntries(operations = []) {
  return operations.map((operation) => ({
    id: operation.id,
    label: operationLabel(operation.operationType),
    status: operation.status,
    target: operation.targetComponentKey || "",
    rationale: operation.rationale || "",
    origin: originLabel(operation.origin),
    requestedBy: operation.requestedBy || "",
    createdAt: operation.createdAt,
    resolvedAt: operation.resolvedAt,
    pending: operation.status === "proposed",
  }));
}

export function pendingOperations(operations = []) {
  return changeLogEntries(operations).filter((entry) => entry.pending);
}

/**
 * The request that restores an earlier version of a section.
 */
export function restoreVersionRequest(stableKey, sequence) {
  return {
    operationType: "revert_component",
    payload: { stableKey, sequence },
    rationale: `Reviewer restored version ${sequence} of ${stableKey}.`,
    apply: true,
  };
}

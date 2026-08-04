export function detailValue(item, label) {
  return (item?.details || []).find((detail) => detail.label === label)?.value || "";
}

export function caseTitleFor(item) {
  return item?.title || item?.client || "Unnamed case";
}

export function caseNumberFor(item) {
  return item?.caseNumber || detailValue(item, "Case number") || item?.id || "";
}

export function isLegalServerCase(item) {
  return (item?.sourceSystem || "LegalServer").toLowerCase() === "legalserver";
}

export function isQuickCase(item) {
  return (item?.sourceSystem || "").toLowerCase() === "manual";
}

export function lastActivityLabel(item, now = Date.now()) {
  if (!isLegalServerCase(item) || !item?.lastActivityAt) return "";
  const lastActivity = new Date(item.lastActivityAt);
  if (Number.isNaN(lastActivity.getTime())) return "";
  const days = Math.max(0, Math.floor((now - lastActivity.getTime()) / 86400000));
  if (days === 0) return "Active today";
  if (days === 1) return "1 day inactive";
  return `${days} days inactive`;
}

export function caseDocumentPreviewKind(document) {
  const mimeType = String(document?.mimeType || "").toLowerCase();
  const filename = String(document?.filename || document?.title || "").toLowerCase().split("?", 1)[0];
  if (mimeType === "application/pdf" || filename.endsWith(".pdf")) return "pdf";
  if (mimeType.startsWith("image/") || /\.(png|jpe?g|gif|webp|bmp|svg|tiff?)$/.test(filename)) return "image";
  return "";
}

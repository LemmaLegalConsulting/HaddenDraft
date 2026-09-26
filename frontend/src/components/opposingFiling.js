// Rules for the "Responding to" panel: which filing a draft answers.
//
// A template states what it answers in `metadata.respondsTo`. A reply requires
// the brief in opposition; a motion to dismiss recommends the complaint. The
// panel shows only when a planned template says something, and generation is
// held back only when one requires it -- the server refuses too, so this is
// about telling the advocate before they press Generate, not enforcing it.

export const FILING_KIND_LABELS = {
  complaint: "Complaint",
  amended_complaint: "Amended complaint",
  counterclaim: "Counterclaim",
  motion: "Motion",
  brief_in_opposition: "Brief in opposition",
};

export function filingKindLabel(kind) {
  return FILING_KIND_LABELS[kind] || String(kind || "").replaceAll("_", " ");
}

// The combined requirement of the templates a plan will draft, or null when
// none of them answers a filing.
export function respondsToRequirement(templates) {
  const declaring = (templates || []).filter(
    (template) => template && Object.keys(template.metadata?.respondsTo || {}).length > 0,
  );
  if (!declaring.length) return null;
  const required = declaring.filter((template) => template.metadata.respondsTo.required);
  const lead = (required[0] || declaring[0]).metadata.respondsTo;
  return {
    required: required.length > 0,
    recommended: declaring.some((template) => template.metadata.respondsTo.recommended),
    question: lead.question || "Which filing does this document answer?",
    help: lead.help || "",
    expects: [...new Set(declaring.flatMap((template) => template.metadata.respondsTo.expects || []))],
    templateTitles: (required.length ? required : declaring).map((template) => template.title),
  };
}

// "not_needed" | "identified" | "missing_required" | "missing_optional"
export function filingStatus(requirement, filing) {
  if (!requirement) return "not_needed";
  if (filing) return "identified";
  return requirement.required ? "missing_required" : "missing_optional";
}

export function blocksGeneration(requirement, filing) {
  return filingStatus(requirement, filing) === "missing_required";
}

export function caseFileOptionLabel(document) {
  const date = String(document?.date || "").slice(0, 10);
  return date ? `${document.title} (${date})` : document?.title || "Case document";
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

// A filing date as the API takes it: "" (unknown) or YYYY-MM-DD. The browser's
// date input already produces that shape; anything else is refused here with
// the same words the server would use.
export function filedOnError(value) {
  const text = String(value || "").trim();
  if (!text || ISO_DATE.test(text)) return "";
  return "Give the filing date as YYYY-MM-DD.";
}

export function sourceSummary(filing) {
  if (!filing) return "";
  if (filing.sourceType === "matter_document") return "Linked from the case file. Its text is read from LegalServer when the draft is written.";
  const pages = filing.pageCount ? `${filing.pageCount} page${filing.pageCount === 1 ? "" : "s"}` : "";
  const exhibits = filing.exhibits?.length
    ? `${filing.exhibits.length} attached exhibit${filing.exhibits.length === 1 ? "" : "s"} set aside`
    : "";
  const parts = [`Uploaded ${filing.originalFilename || "file"}`, pages, exhibits].filter(Boolean);
  return `${parts.join(" · ")}.`;
}

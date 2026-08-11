// Rules for the "save to LegalServer" choice, kept out of the components so
// they can be tested without a browser.
//
// The default differs by what is being saved. A generated document is lost work
// if it is not filed, so it defaults on. A research answer or triage assessment
// is a working judgment the advocate may not want on the case file, so those
// default off.

export const SAVE_KINDS = ["documents", "research", "triage"];

const FALLBACK_DEFAULTS = { documents: true, research: false, triage: false };

export function saveDefault(bootstrapSave, kind) {
  const defaults = (bootstrapSave && bootstrapSave.defaults) || {};
  return kind in defaults ? Boolean(defaults[kind]) : Boolean(FALLBACK_DEFAULTS[kind]);
}

// A case that does not exist in LegalServer, or a site with no credentials
// configured, cannot be written to. Say so instead of offering a checkbox that
// silently does nothing.
export function saveAvailability({ bootstrapSave, caseStatus } = {}) {
  const configured = bootstrapSave ? Boolean(bootstrapSave.configured) : true;
  if (!configured) {
    return { available: false, hint: "LegalServer is not connected, so nothing can be saved to the case file." };
  }
  if (caseStatus && caseStatus.canSave === false) {
    return {
      available: false,
      hint: caseStatus.message || "This case cannot be saved to LegalServer.",
    };
  }
  return { available: true, hint: "" };
}

export function saveLabel(kind) {
  if (kind === "documents") return "Save a copy to the LegalServer case file";
  if (kind === "research") return "Save this research to the LegalServer case file";
  if (kind === "triage") return "Save this assessment to the LegalServer case file";
  return "Save to the LegalServer case file";
}

// A binary download carries its upload result in headers, since the body is the
// document itself.
export function deliveryFromHeaders(response) {
  const headers = response && response.headers;
  if (!headers || typeof headers.get !== "function") return null;
  const status = headers.get("X-LegalServer-Delivery");
  if (!status) return null;
  return { status, message: headers.get("X-LegalServer-Delivery-Message") || "" };
}

export function deliveryTone(delivery) {
  if (!delivery) return "";
  if (delivery.status === "saved") return "success";
  if (delivery.status === "failed") return "error";
  return "info";
}

export function deliveryMessage(delivery) {
  if (!delivery) return "";
  if (delivery.message) return delivery.message;
  if (delivery.status === "saved") return "Saved to LegalServer.";
  if (delivery.status === "failed") return "Could not save to LegalServer.";
  if (delivery.status === "dry_run") return "Previewed only; LegalServer was not changed.";
  return "Not sent to LegalServer.";
}

// The triage response reports two separate outcomes: the note and the case
// property update. Collapse them into the lines the panel shows.
export function triageDeliveryLines(legalserver) {
  if (!legalserver) return [];
  return ["casenote", "caseUpdate"]
    .map((key) => legalserver[key])
    .filter(Boolean)
    .map((delivery) => ({
      key: delivery.kind,
      tone: deliveryTone(delivery),
      message: deliveryMessage(delivery),
      fields: delivery.fields || {},
    }));
}

// A dry-run case update is the interesting one to show in full: it is the
// office's chance to check the mapping before it starts writing to case files.
export function previewedFieldRows(delivery) {
  if (!delivery || !delivery.fields) return [];
  return Object.entries(delivery.fields).flatMap(([name, value]) =>
    name === "custom_fields" && value && typeof value === "object"
      ? Object.entries(value).map(([custom, customValue]) => ({ name: custom, value: String(customValue) }))
      : [{ name, value: String(value) }],
  );
}

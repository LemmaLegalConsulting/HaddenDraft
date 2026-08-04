import React, { useEffect } from "react";
import { ExternalLink, X } from "lucide-react";

import { api } from "../api/client.js";
import { caseDocumentPreviewKind } from "./casePresentation.js";

export function CaseDocumentPreviewModal({ matterId, document, onClose }) {
  useEffect(() => {
    if (!document) return undefined;
    function closeOnEscape(event) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [document, onClose]);

  if (!matterId || !document) return null;
  const kind = caseDocumentPreviewKind(document);
  const fileUrl = api.caseDocumentFileUrl(matterId, document.id);

  return (
    <div className="modal-backdrop document-preview-backdrop" data-case-document-preview role="presentation" onMouseDown={onClose}>
      <section
        className="editor-modal document-preview-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="document-preview-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-heading">
          <div>
            <span className="block-kicker">Case document</span>
            <h4 id="document-preview-title">{document.title || document.filename || "Document preview"}</h4>
          </div>
          <div className="modal-heading-actions">
            <a className="icon-button" href={fileUrl} target="_blank" rel="noreferrer" aria-label="Open document in a new tab" title="Open in a new tab">
              <ExternalLink size={18} />
            </a>
            <button className="icon-button" type="button" aria-label="Close document preview" title="Close document preview" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
        </div>
        <div className="document-preview-body">
          {kind === "image" ? (
            <img src={fileUrl} alt={document.title || document.filename || "Case document"} />
          ) : (
            <iframe src={fileUrl} title={document.title || document.filename || "Case document"} />
          )}
        </div>
      </section>
    </div>
  );
}

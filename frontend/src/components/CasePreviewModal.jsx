import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  ExternalLink,
  FilePlus2,
  Maximize2,
  MessageSquare,
  Minimize2,
  Pencil,
  X,
} from "lucide-react";

import { CaseMaterialsPanel } from "./CaseMaterialsPanel.jsx";
import { caseTitleFor, isLegalServerCase, isQuickCase } from "./casePresentation.js";

export function CasePreviewModal({
  matter,
  isActive,
  manualCaseBusy,
  onClose,
  onMakeActive,
  onModeChange,
  onUpdateManualCase,
}) {
  const [fullscreen, setFullscreen] = useState(false);
  const [editCaseOpen, setEditCaseOpen] = useState(false);

  useEffect(() => {
    setFullscreen(false);
    setEditCaseOpen(false);
  }, [matter?.id]);

  useEffect(() => {
    if (!matter) return undefined;
    function closeOnEscape(event) {
      if (event.key === "Escape" && !document.querySelector("[data-case-document-preview]")) onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [matter, onClose]);

  if (!matter) return null;

  function activateAndGo(mode) {
    if (!isActive) onMakeActive(matter.id);
    onClose();
    onModeChange(mode);
  }

  return (
    <div className="modal-backdrop case-preview-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className={`editor-modal case-preview-modal ${fullscreen ? "fullscreen" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="case-preview-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-heading case-preview-heading">
          <div>
            <span className="block-kicker">Case preview</span>
            <h4 id="case-preview-title">{caseTitleFor(matter)}</h4>
            {matter.title && matter.client && matter.title !== matter.client && <p>Client or household: {matter.client}</p>}
          </div>
          <div className="modal-heading-actions">
            <button
              className="icon-button"
              type="button"
              aria-label={fullscreen ? "Restore case preview" : "Make case preview full screen"}
              title={fullscreen ? "Restore case preview" : "Make case preview full screen"}
              onClick={() => setFullscreen((value) => !value)}
            >
              {fullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            </button>
            <button className="icon-button" type="button" aria-label="Close case preview" title="Close case preview" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="case-preview-toolbar">
          {isActive ? (
            <span className="active-case-indicator"><CheckCircle2 size={16} /> Active case</span>
          ) : (
            <button className="btn btn-outline-secondary" type="button" onClick={() => onMakeActive(matter.id)}>
              <CheckCircle2 size={16} /> Make active case
            </button>
          )}
          {isLegalServerCase(matter) && matter.legalserverUrl && (
            <a className="btn btn-outline-secondary link-button" href={matter.legalserverUrl} target="_blank" rel="noreferrer noopener">
              <ExternalLink size={16} /> Open in LegalServer
            </a>
          )}
          <button className="btn btn-primary" type="button" onClick={() => activateAndGo("case_chat")}>
            <MessageSquare size={16} /> Chat with case
          </button>
        </div>

        <div className="case-preview-body">
          <section className="case-preview-summary">
            <dl className="case-details">
              {(matter.details || []).map((item) => (
                <div key={item.label}>
                  <dt>{item.label}</dt>
                  <dd>{item.value}</dd>
                </div>
              ))}
            </dl>
            {matter.summary && <section className="case-summary"><h4>Case summary</h4><p>{matter.summary}</p></section>}
            {isActive && isQuickCase(matter) && (
              <div className="case-actions">
                <button className="btn btn-outline-secondary" type="button" onClick={() => setEditCaseOpen((current) => !current)}>
                  <Pencil size={16} /> Edit quick case
                </button>
                <button className="btn btn-outline-secondary" type="button" disabled title="LegalServer draft-intake preview is backend-only until posting is configured">
                  <FilePlus2 size={16} /> Create LegalServer draft intake
                </button>
              </div>
            )}
            {editCaseOpen && isActive && isQuickCase(matter) && (
              <form
                className="manual-case-form edit-case-form"
                onSubmit={async (event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  const saved = await onUpdateManualCase?.({
                    clientName: form.get("clientName"),
                    matterType: form.get("matterType"),
                    jurisdiction: form.get("jurisdiction"),
                    posture: form.get("posture"),
                    summary: form.get("summary"),
                  });
                  if (saved) setEditCaseOpen(false);
                }}
              >
                <div className="manual-case-grid">
                  <label className="field"><span>Client or household</span><input className="form-control" name="clientName" defaultValue={matter.client || ""} /></label>
                  <label className="field"><span>Legal problem</span><input className="form-control" name="matterType" defaultValue={matter.matter || ""} /></label>
                  <label className="field"><span>Court or county</span><input className="form-control" name="jurisdiction" defaultValue={matter.jurisdiction || ""} /></label>
                  <label className="field"><span>Posture</span><input className="form-control" name="posture" defaultValue={matter.posture || ""} /></label>
                </div>
                <label className="field"><span>Case description or intake notes</span><textarea className="form-control" name="summary" defaultValue={matter.summary || ""} rows={5} /></label>
                <button className="btn btn-primary full" type="submit" disabled={manualCaseBusy}>
                  <Pencil size={16} /> Save quick case
                </button>
              </form>
            )}
          </section>

          <CaseMaterialsPanel matter={matter} readOnly embedded />
        </div>
      </section>
    </div>
  );
}

import React from "react";
import { Loader2, Sparkles, X } from "lucide-react";

export function RevisionPlanModal({ plan, busy, onClose, onUpdateItem, onApply }) {
  if (!plan) return null;
  const items = plan.plan || [];
  const includedCount = items.filter((item) => item.include).length;

  return (
    <div className="modal-backdrop" role="presentation">
      <div className="editor-modal revision-plan-modal" role="dialog" aria-modal="true" aria-label="AI revision plan">
        <div className="modal-heading">
          <h4><Sparkles size={16} /> AI revision plan</h4>
          <button className="icon-button secondary" type="button" onClick={onClose} title="Close"><X size={16} /></button>
        </div>
        <p className="muted">
          Review and edit the instructions below before the AI revises each section. Uncheck a section to leave it as is.
        </p>
        {items.length === 0 ? (
          <div className="empty-state compact">
            <p>No findings are tied to a specific section, so there is nothing to auto-revise. See the notes below for items that need manual review.</p>
          </div>
        ) : (
          <div className="revision-plan-list">
            {items.map((item) => (
              <div className={`revision-plan-item ${item.include ? "" : "excluded"}`} key={item.blockKey}>
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={item.include}
                    onChange={(event) => onUpdateItem(item.blockKey, { include: event.target.checked })}
                  />
                  <strong>{item.sectionLabel}</strong>
                  <span className="muted">{item.findingIds.length} finding{item.findingIds.length === 1 ? "" : "s"}</span>
                </label>
                <textarea
                  value={item.instruction}
                  disabled={!item.include}
                  onChange={(event) => onUpdateItem(item.blockKey, { instruction: event.target.value })}
                  rows={4}
                />
              </div>
            ))}
          </div>
        )}
        {plan.unscoped?.length > 0 && (
          <div className="revision-plan-unscoped">
            <strong>Not auto-revisable — needs manual review:</strong>
            <ul>
              {plan.unscoped.map((finding) => (
                <li key={finding.findingId}>{finding.message}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="button-row step-actions">
          <button className="secondary" type="button" onClick={onClose}>Cancel</button>
          <button className="primary" type="button" disabled={busy || includedCount === 0} onClick={onApply}>
            {busy ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />} Apply revision to {includedCount} section{includedCount === 1 ? "" : "s"}
          </button>
        </div>
      </div>
    </div>
  );
}

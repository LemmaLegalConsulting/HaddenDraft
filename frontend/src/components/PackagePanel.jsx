import React, { useEffect, useState } from "react";
import { AlertTriangle, ChevronDown, Layers3, Loader2 } from "lucide-react";

import { api } from "../api/client.js";
import { packageFindings, packageView, unvalidatedDocuments } from "./documentPackage.js";

/**
 * The filing package: what was generated, what each document is, how they
 * depend on each other, and where they disagree.
 *
 * Cross-document findings are raised against whichever document was validated,
 * so a reviewer working in one document would otherwise never see that another
 * document contradicts it.
 */
export function PackagePanel({ sessionId, drafts = [], validatedDraftIds = [], activeDraftId, onSelectDocument }) {
  const [open, setOpen] = useState(false);
  const [packageData, setPackageData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const documentCount = drafts.length;

  useEffect(() => {
    if (!open || !sessionId) return undefined;
    let cancelled = false;
    setLoading(true);
    setError("");
    api.sessionPackage(sessionId)
      .then((response) => {
        if (!cancelled) setPackageData(response.package || null);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, sessionId, documentCount]);

  if (documentCount < 2) return null;

  const view = packageView(packageData);
  const findings = packageFindings(drafts);
  const unchecked = unvalidatedDocuments(drafts, validatedDraftIds);

  return (
    <section className="package-panel">
      <button className="package-panel-header" type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <span><Layers3 size={16} /> Filing package ({documentCount} documents)</span>
        {findings.length > 0 && (
          <span className="package-finding-count"><AlertTriangle size={14} /> {findings.length}</span>
        )}
        <ChevronDown className={open ? "chevron open" : "chevron"} size={16} />
      </button>
      {open && (
        <div className="package-panel-content">
          {error && <div className="inline-error alert alert-danger">{error}</div>}
          {loading && <p className="document-history-loading"><Loader2 className="spin" size={16} /> Loading package…</p>}

          <ul className="package-document-list">
            {view.documents.map((item) => (
              <li key={item.id}>
                <button
                  className={item.id === activeDraftId ? "package-document active" : "package-document"}
                  type="button"
                  onClick={() => onSelectDocument?.(item.id)}
                >
                  <span className="package-document-title">{item.title}</span>
                  <span className="package-role">{item.roleLabel}</span>
                </button>
              </li>
            ))}
          </ul>

          {view.relationships.length > 0 && (
            <div className="package-relationships">
              <h4>How these documents relate</h4>
              <ul>
                {view.relationships.map((item) => (
                  <li key={`${item.sourceDocumentId}-${item.relationshipType}-${item.targetDocumentId}`}>
                    {item.description}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="package-findings">
            <h4>Cross-document checks</h4>
            {findings.length === 0 ? (
              <p className="package-findings-clear">No cross-document problems were reported.</p>
            ) : (
              <ul>
                {findings.map((finding) => (
                  <li key={finding.findingId}>
                    <span className="finding-rule-code">{finding.ruleCode}</span>
                    <button className="package-finding-document" type="button" onClick={() => onSelectDocument?.(finding.documentId)}>
                      {finding.documentTitle}
                    </button>
                    <span>{finding.message}</span>
                  </li>
                ))}
              </ul>
            )}
            {unchecked.length > 0 && (
              <p className="package-findings-unchecked">
                Not yet validated: {unchecked.join(", ")}. Cross-document checks run when a document is validated.
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

import React, { useEffect, useState } from "react";
import { AlertTriangle, ChevronDown, History, Loader2, RotateCcw, ShieldCheck } from "lucide-react";

import { api } from "../api/client.js";
import {
  changeLogEntries,
  componentHistoryEntries,
  restoreVersionRequest,
} from "./documentHistory.js";

function formatTimestamp(value) {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function SupportSummary({ support }) {
  if (!support.total) {
    return <p className="component-support-empty">No sources are recorded for this version.</p>;
  }
  return (
    <div className="component-support">
      {support.styleOnlyOnly && (
        <p className="component-support-warning">
          <AlertTriangle size={14} /> This section rests only on example language, which guides wording but is not
          authority.
        </p>
      )}
      {support.groups.map((group) => (
        <div className="component-support-group" key={group.role}>
          <span className={`support-role support-role-${group.role}`}>{group.label}</span>
          <ul>
            {group.sources.map((source) => (
              <li key={source.key} title={source.excerpt}>
                {source.label}
                {source.verified && <ShieldCheck size={13} className="support-verified" aria-label="Verified" />}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function ComponentHistory({ entry, busy, onRestore }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`component-history${entry.removed ? " component-history-removed" : ""}`}>
      <button className="component-history-toggle" type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <span className="component-history-label">
          {entry.label}
          {entry.removed && <span className="component-removed-badge">removed</span>}
        </span>
        <span className="component-history-meta">
          {entry.versionCount} version{entry.versionCount === 1 ? "" : "s"}
          {entry.support.hasAuthority && <span className="support-role support-role-legal_authority">authority</span>}
        </span>
        <ChevronDown className={open ? "chevron open" : "chevron"} size={16} />
      </button>
      {open && (
        <div className="component-history-body">
          <SupportSummary support={entry.support} />
          <ol className="version-list">
            {entry.versions.map((version) => (
              <li className={version.isCurrent ? "version-item version-current" : "version-item"} key={version.sequence}>
                <div className="version-heading">
                  <span className="version-origin">{version.originLabel}</span>
                  <span className="version-time">{formatTimestamp(version.createdAt)}</span>
                  {version.isCurrent ? (
                    <span className="version-current-badge">current</span>
                  ) : (
                    <button
                      className="btn btn-outline-secondary btn-sm"
                      type="button"
                      disabled={busy || entry.removed}
                      onClick={() => onRestore(entry.stableKey, version.sequence)}
                    >
                      <RotateCcw size={14} /> Restore
                    </button>
                  )}
                </div>
                {version.instruction && <p className="version-instruction">“{version.instruction}”</p>}
                <pre className="version-body">{version.body || "(empty)"}</pre>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

/**
 * Where a document's text came from, what it may rest on, and what has been
 * done to it. Restoring a version goes through the same operation API the
 * backend records every other change with.
 */
export function DocumentHistoryPanel({ draft, busy = false, onDraftRestored }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [components, setComponents] = useState([]);
  const [operations, setOperations] = useState([]);
  const [error, setError] = useState("");
  const draftId = draft?.id ?? null;
  const updatedAt = draft?.updatedAt ?? null;

  useEffect(() => {
    if (!open || !draftId) return undefined;
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([api.draftComponents(draftId), api.draftOperations(draftId)])
      .then(([componentResponse, operationResponse]) => {
        if (cancelled) return;
        setComponents(componentResponse.components || []);
        setOperations(operationResponse.operations || []);
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
  }, [open, draftId, updatedAt]);

  async function restoreVersion(stableKey, sequence) {
    if (!draftId) return;
    setLoading(true);
    setError("");
    try {
      const response = await api.proposeDraftOperation(draftId, restoreVersionRequest(stableKey, sequence));
      // The restored text changes the draft's updatedAt, which reloads history.
      onDraftRestored?.(response.draft);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (!draft) return null;

  const entries = componentHistoryEntries(components);
  const changes = changeLogEntries(operations);

  return (
    <section className="document-history-panel">
      <button className="document-history-header" type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <span><History size={16} /> Version history and sources</span>
        <ChevronDown className={open ? "chevron open" : "chevron"} size={16} />
      </button>
      {open && (
        <div className="document-history-content">
          {error && <div className="inline-error alert alert-danger">{error}</div>}
          {loading && <p className="document-history-loading"><Loader2 className="spin" size={16} /> Loading history…</p>}
          {!loading && entries.length === 0 && <p>No recorded history for this document yet.</p>}
          {entries.map((entry) => (
            <ComponentHistory key={entry.stableKey} entry={entry} busy={busy || loading} onRestore={restoreVersion} />
          ))}
          {changes.length > 0 && (
            <div className="change-log">
              <h4>Change log</h4>
              <ul>
                {changes.map((change) => (
                  <li key={change.id}>
                    <span className="change-log-label">{change.label}</span>
                    {change.target && <span className="change-log-target">{change.target}</span>}
                    <span className={`change-log-status change-log-${change.status}`}>{change.status}</span>
                    <span className="change-log-origin">{change.origin}</span>
                    {change.rationale && <span className="change-log-rationale">“{change.rationale}”</span>}
                    <span className="change-log-time">{formatTimestamp(change.createdAt)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

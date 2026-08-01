import React from "react";
import { AlertTriangle, FileText } from "lucide-react";

// A plan can produce several documents. Without a switcher only the first one
// is ever reachable, and the rest are stranded in the database.
export function DraftSwitcher({ drafts, activeDraftId, onSelect, busy }) {
  if (!drafts || drafts.length < 2) return null;

  return (
    <nav className="draft-switcher" aria-label="Planned documents">
      <span className="block-kicker">{drafts.length} documents in this plan</span>
      <ul className="draft-switcher-list">
        {drafts.map((item, index) => {
          const active = item.id === activeDraftId;
          const errorCount = (item.validationFlags || []).filter((flag) => flag.severity === "error").length;
          return (
            <li key={item.id}>
              <button
                type="button"
                className={`draft-switcher-tab ${active ? "selected" : ""}`}
                aria-current={active ? "page" : undefined}
                disabled={busy}
                onClick={() => onSelect(item.id)}
              >
                <FileText size={16} />
                <span className="draft-switcher-title">{item.title || `Document ${index + 1}`}</span>
                {errorCount > 0 && (
                  <span className="draft-switcher-flag" title={`${errorCount} validation error(s)`}>
                    <AlertTriangle size={14} /> {errorCount}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

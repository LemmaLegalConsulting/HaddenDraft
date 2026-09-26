import React from "react";
import { FilePlus2, FileText, Loader2 } from "lucide-react";

import { PanelHeading } from "./PanelHeading.jsx";
import { sessionRowLabels } from "../state/savedSessions.js";

// A case's saved work in one workspace. Every row is a link to the saved
// session; the only action here is starting something new, and even that only
// opens the setup screen -- nothing is created until the advocate says so.
export function SavedSessionList({ matter, title, description, sessions, total, hasMore, loading, error, onLoadMore, sessionHref, newHref, newLabel, onNavigate }) {
  function follow(event, href) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onNavigate(href);
  }

  return (
    <section className="panel saved-session-list">
      <PanelHeading title={title} description={description}>
        {matter && (
          <a className="btn btn-primary" href={newHref} onClick={(event) => follow(event, newHref)}>
            <FilePlus2 size={16} /> {newLabel}
          </a>
        )}
      </PanelHeading>
      {!matter && <p className="muted">Choose a case to see its saved work.</p>}
      {error && <div className="inline-error alert alert-danger">{error}</div>}
      {matter && !loading && !error && sessions.length === 0 && (
        <div className="empty-state compact-empty">
          <strong className="empty-state-title">No saved work for this case yet</strong>
        </div>
      )}
      {sessions.length > 0 && (
        <ul className="saved-session-rows" aria-label={`${title}: ${total} saved`}>
          {sessions.map((row) => {
            const labels = sessionRowLabels(row);
            const href = sessionHref(row);
            return (
              <li key={row.id}>
                <a className="saved-session-row" href={href} onClick={(event) => follow(event, href)}>
                  <FileText size={16} />
                  <span className="saved-session-text">
                    <strong>{labels.title}</strong>
                    {labels.goal && <span>{labels.goal}</span>}
                    <small className="muted">{labels.progress} · updated {new Date(row.updatedAt).toLocaleString()}</small>
                  </span>
                </a>
              </li>
            );
          })}
        </ul>
      )}
      {loading && <p className="muted"><Loader2 className="spin" size={16} /> Loading saved work</p>}
      {hasMore && !loading && (
        <button className="btn btn-light" type="button" onClick={onLoadMore}>Show more</button>
      )}
    </section>
  );
}

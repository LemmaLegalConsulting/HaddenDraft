import React from "react";
import { AlertTriangle, CheckCircle2, Loader2, Save } from "lucide-react";

// Whether what is on screen is saved. Four ordinary states and one that needs
// a decision: another window saved first, and the advocate chooses whose
// version stands. Nothing is merged or discarded without that choice.
export function SaveStatusBar({ status, thing = "session", error = "", onSave, onKeepMine, onLoadTheirs }) {
  if (status === "saved") {
    return (
      <div className="save-status save-status-saved" role="status">
        <CheckCircle2 size={14} /> All changes saved
      </div>
    );
  }
  if (status === "saving") {
    return (
      <div className="save-status" role="status" aria-busy="true">
        <Loader2 className="spin" size={14} /> Saving
      </div>
    );
  }
  if (status === "conflict") {
    return (
      <div className="save-status save-status-conflict" role="alert">
        <AlertTriangle size={14} />
        <span>This {thing} was changed in another window. Your changes are still here, not saved.</span>
        <div className="button-row compact">
          <button className="btn btn-light" type="button" onClick={onLoadTheirs}>Load the saved version (discard mine)</button>
          <button className="btn btn-primary" type="button" onClick={onKeepMine}>Keep mine and save over it</button>
        </div>
      </div>
    );
  }
  return (
    <div className={`save-status ${status === "failed" ? "save-status-failed" : "save-status-dirty"}`} role="status">
      {status === "failed" ? <AlertTriangle size={14} /> : null}
      <span>{status === "failed" ? `Not saved${error ? `: ${error}` : ""}` : "Unsaved changes"}</span>
      {onSave && (
        <button className="btn btn-light" type="button" onClick={onSave}>
          <Save size={14} /> {status === "failed" ? "Try again" : "Save"}
        </button>
      )}
    </div>
  );
}

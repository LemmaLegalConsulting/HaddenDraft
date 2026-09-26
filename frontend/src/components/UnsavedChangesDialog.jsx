import React, { useRef } from "react";
import { Loader2 } from "lucide-react";

import { useModalDismiss } from "../hooks/useModalDismiss.js";

// Leaving saved work with changes nobody has saved. Three choices, and "Stay"
// is what dismissing the dialog means: closing it must never discard.
export function UnsavedChangesDialog({ open, busy = false, error = "", onSave, onDiscard, onStay }) {
  const dialogRef = useRef(null);
  useModalDismiss(dialogRef, onStay, { active: open });
  if (!open) return null;
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="profile-modal unsaved-dialog" ref={dialogRef} role="alertdialog" aria-modal="true" aria-labelledby="unsaved-dialog-title" aria-describedby="unsaved-dialog-text">
        <h4 id="unsaved-dialog-title">Leave with unsaved changes?</h4>
        <p id="unsaved-dialog-text" className="muted">Changes on this screen have not been saved. Save them, discard them, or stay here.</p>
        {error && <div className="inline-error alert alert-danger">Could not save: {error}</div>}
        <div className="button-row">
          <button className="btn btn-primary" type="button" disabled={busy} onClick={onSave}>
            {busy ? <Loader2 className="spin" size={16} /> : null} Save and leave
          </button>
          <button className="btn btn-light" type="button" disabled={busy} onClick={onDiscard}>Discard changes</button>
          <button className="btn btn-light" type="button" disabled={busy} onClick={onStay}>Stay</button>
        </div>
      </div>
    </div>
  );
}

import { AlertTriangle, CheckCircle2, Info, Upload } from "lucide-react";

import {
  deliveryMessage,
  deliveryTone,
  saveAvailability,
  saveButtonLabel,
  saveButtonTitle,
} from "./legalServerSave.js";

const TONE_ICONS = { success: CheckCircle2, error: AlertTriangle, info: Info };

/**
 * An explicit "file this on the case" action, for work an advocate revises in
 * place. A checkbox on a download suits a one-shot export; a letter that gets
 * rewritten four times needs a button that says whether the next click adds a
 * copy or replaces the one already there.
 */
export default function LegalServerSaveButton({
  onSave,
  busy = false,
  delivery = null,
  bootstrapSave = null,
  caseStatus = null,
  disabled = false,
}) {
  const { available, hint } = saveAvailability({ bootstrapSave, caseStatus });
  const tone = deliveryTone(delivery);
  const ToneIcon = TONE_ICONS[tone] || Info;

  return (
    <div className="legalserver-save">
      <button
        className="btn btn-outline-secondary"
        type="button"
        disabled={disabled || busy || !available}
        title={saveButtonTitle({ delivery, available, hint })}
        onClick={onSave}
      >
        <Upload size={16} aria-hidden="true" /> {saveButtonLabel({ delivery, busy })}
      </button>
      {!available && <p className="muted legalserver-save-hint">{hint}</p>}
      {delivery && (
        <p className={`legalserver-save-result ${tone}`} role="status">
          <ToneIcon size={14} aria-hidden="true" /> {deliveryMessage(delivery)}
        </p>
      )}
    </div>
  );
}

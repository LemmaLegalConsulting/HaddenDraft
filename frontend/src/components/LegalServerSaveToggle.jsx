import { AlertTriangle, CheckCircle2, Info, Upload } from "lucide-react";

import { deliveryMessage, deliveryTone, saveAvailability, saveLabel } from "./legalServerSave.js";

const TONE_ICONS = {
  success: CheckCircle2,
  error: AlertTriangle,
  info: Info,
};

/**
 * The opt-in/opt-out for writing this piece of work back to the case file,
 * plus the outcome of the last attempt.
 */
export default function LegalServerSaveToggle({
  kind,
  checked,
  onChange,
  bootstrapSave,
  caseStatus,
  delivery = null,
  disabled = false,
  label = "",
}) {
  const { available, hint } = saveAvailability({ bootstrapSave, caseStatus });
  const tone = deliveryTone(delivery);
  const ToneIcon = TONE_ICONS[tone] || Info;

  return (
    <div className="legalserver-save">
      <label className="checkbox-row legalserver-save-row">
        <input
          type="checkbox"
          checked={available && checked}
          disabled={disabled || !available}
          onChange={(event) => onChange(event.target.checked)}
        />
        <span>
          <Upload size={16} aria-hidden="true" /> {label || saveLabel(kind)}
        </span>
      </label>
      {!available && <p className="muted legalserver-save-hint">{hint}</p>}
      {delivery && (
        <p className={`legalserver-save-result ${tone}`} role="status">
          <ToneIcon size={14} aria-hidden="true" /> {deliveryMessage(delivery)}
        </p>
      )}
    </div>
  );
}

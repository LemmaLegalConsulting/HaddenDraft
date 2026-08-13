import React, { useEffect, useState } from "react";
import { Cloud } from "lucide-react";

import { subscribeToWake } from "../api/wakeNotice.js";

/**
 * The one thing worth saying while the server comes back up.
 *
 * Deliberately a strip rather than a modal: the reader keeps whatever is
 * already on screen, and the request they made is still on its way — there is
 * nothing for them to do here but know why it is taking a moment.
 */
export function WakingNotice() {
  const [waking, setWaking] = useState(false);
  useEffect(() => subscribeToWake(setWaking), []);
  if (!waking) return null;
  return (
    <div className="waking-notice" role="status" aria-live="polite">
      <Cloud className="spin" size={16} aria-hidden="true" />
      <span>
        <strong>Waking the server back up.</strong>{" "}
        <small>It sleeps when nobody is using it. Your request will go through in a few seconds.</small>
      </span>
    </div>
  );
}

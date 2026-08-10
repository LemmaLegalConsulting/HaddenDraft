import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { INDICATOR_DELAY_MS, isSlow, shouldShowIndicator, slowExplanation } from "./loadingStatus.js";

function useElapsed(busy) {
  const [elapsedMs, setElapsedMs] = useState(0);
  useEffect(() => {
    if (!busy) {
      setElapsedMs(0);
      return undefined;
    }
    const startedAt = Date.now();
    setElapsedMs(0);
    const timer = setInterval(() => setElapsedMs(Date.now() - startedAt), 120);
    return () => clearInterval(timer);
  }, [busy]);
  return elapsedMs;
}

/**
 * A named wait over the region that is actually loading.
 *
 * Scoped rather than app-modal on purpose: the reader can still read what is
 * already on screen and switch away mid-load, which a blocking dialog would
 * take away for no gain.
 */
export function LoadingOverlay({ busy, label, kind = "", delayMs = INDICATOR_DELAY_MS }) {
  const elapsedMs = useElapsed(busy);
  const visible = shouldShowIndicator({ busy, elapsedMs, delayMs });
  const slow = isSlow({ busy, elapsedMs });
  if (!visible) return null;
  return (
    <div className="loading-overlay" role="status" aria-live="polite">
      <div className="loading-overlay-card">
        <Loader2 className="spin" size={18} aria-hidden="true" />
        <strong>{label}</strong>
        {slow && <small>{slowExplanation(kind)}</small>}
      </div>
    </div>
  );
}

/** The same wait, stated inline where there is no content to sit on top of. */
export function LoadingNotice({ busy, label, kind = "", delayMs = INDICATOR_DELAY_MS }) {
  const elapsedMs = useElapsed(busy);
  const slow = isSlow({ busy, elapsedMs });
  if (!shouldShowIndicator({ busy, elapsedMs, delayMs })) return null;
  return (
    <p className="loading-notice" role="status" aria-live="polite">
      <Loader2 className="spin" size={14} aria-hidden="true" /> {label}
      {slow && <small>{slowExplanation(kind)}</small>}
    </p>
  );
}

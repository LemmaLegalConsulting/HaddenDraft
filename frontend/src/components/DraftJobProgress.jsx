import React from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

import { PanelHeading } from "./PanelHeading.jsx";

const STATUS_TEXT = {
  pending: "Waiting to start",
  running: "Generating the documents in this plan",
  complete: "Finished; opening the documents",
};

// A generation already under way, reconnected to by its URL. This screen only
// watches: a reload lands back here and keeps watching the same job rather
// than starting another.
export function DraftJobProgress({ progress, onBackToPlan }) {
  const failed = progress.status === "failed";
  return (
    <section className="panel draft-job-progress" aria-live="polite" aria-busy={!failed}>
      <PanelHeading
        eyebrow="Draft"
        title={failed ? "The draft could not be generated" : "Generating the draft"}
        description={failed ? progress.error : `${STATUS_TEXT[progress.status] || STATUS_TEXT.pending}. You can leave this page; the link returns here.`}
        icon={failed ? <AlertTriangle size={18} /> : <Loader2 className="spin" size={18} />}
      >
        {failed && <button className="btn btn-primary" type="button" onClick={onBackToPlan}>Back to plan</button>}
      </PanelHeading>
    </section>
  );
}

import React from "react";
import { ClipboardList, Loader2 } from "lucide-react";

import { PanelHeading } from "./PanelHeading.jsx";

// What a link opened, when it did not open a screen of work. A case that does
// not exist and a case this account may not open read the same, so a guessed
// URL never confirms that a case exists.
const COPY = {
  loading: (caseKey) => ({
    title: `Opening case ${caseKey}`,
    description: "Loading the case this link names.",
  }),
  unavailable: (caseKey) => ({
    title: `Case ${caseKey} is not available`,
    description:
      "No case with this number is available to your account. It may not exist, or it may be assigned to someone else. Nothing from another case is shown in its place.",
  }),
  error: (caseKey) => ({
    title: `Case ${caseKey} could not be opened`,
    description: "The case could not be loaded just now. The message above says why.",
  }),
  not_found: () => ({
    title: "This page does not exist",
    description:
      "The link may be mistyped, or it may point to saved work this version cannot open yet.",
  }),
};

export function RouteNotice({ kind, caseKey = "", onChooseCase }) {
  const copy = (COPY[kind] || COPY.not_found)(caseKey);
  return (
    <section className="panel route-notice" aria-live="polite" aria-busy={kind === "loading"}>
      <PanelHeading
        title={copy.title}
        description={copy.description}
        icon={kind === "loading" ? <Loader2 className="spin" size={18} /> : null}
      >
        {kind !== "loading" && onChooseCase && (
          <button className="btn btn-primary" type="button" onClick={onChooseCase}>
            <ClipboardList size={16} /> Choose a case
          </button>
        )}
      </PanelHeading>
    </section>
  );
}

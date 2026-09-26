import React from "react";
import { ClipboardList, Link2, Loader2 } from "lucide-react";

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
  // About the account, not the case: the same words for any case number.
  not_connected: (caseKey) => ({
    title: `Connect LegalServer to open case ${caseKey}`,
    description:
      "Your account is not connected to LegalServer yet, so no LegalServer case can open here. Connect it, and this case opens if it is one you can see in LegalServer.",
  }),
  identity_mismatch: (caseKey) => ({
    title: `Check your LegalServer connection to open case ${caseKey}`,
    description:
      "The LegalServer account connected here does not match the account you signed in with, so LegalServer cases cannot open. Update the connection to your own LegalServer account.",
  }),
  error: (caseKey) => ({
    title: `Case ${caseKey} could not be opened`,
    description: "The case could not be loaded just now. The message above says why.",
  }),
  session_loading: () => ({
    title: "Opening saved drafting work",
    description: "Loading the session this link names, as it was saved. Nothing is regenerated.",
  }),
  session_unavailable: () => ({
    title: "This drafting session is not available",
    description:
      "No saved session with this number belongs to this case in your account. Nothing from another session is shown in its place.",
  }),
  session_error: () => ({
    title: "This drafting session could not be opened",
    description: "The session could not be loaded just now. The message above says why.",
  }),
  draft_unavailable: () => ({
    title: "This document is not part of this session",
    description: "The session opened, but it has no document with this number.",
  }),
  not_found: () => ({
    title: "This page does not exist",
    description:
      "The link may be mistyped, or it may point to saved work this version cannot open yet.",
  }),
};

// Where the button goes depends on the notice: a missing case goes back to
// the case list, a missing session to the case's saved work.
const ACTION_LABEL = {
  session_unavailable: "Saved drafting work",
  session_error: "Saved drafting work",
  draft_unavailable: "Open the session",
};

// `action` ({ label, onClick }) replaces the default button with the step
// that fixes this notice, such as connecting LegalServer.
export function RouteNotice({ kind, caseKey = "", onChooseCase, action = null }) {
  const copy = (COPY[kind] || COPY.not_found)(caseKey);
  const loading = kind === "loading" || kind === "session_loading";
  return (
    <section className="panel route-notice" aria-live="polite" aria-busy={loading}>
      <PanelHeading
        title={copy.title}
        description={copy.description}
        icon={loading ? <Loader2 className="spin" size={18} /> : null}
      >
        {!loading && action && (
          <button className="btn btn-primary" type="button" onClick={action.onClick}>
            <Link2 size={16} /> {action.label}
          </button>
        )}
        {!loading && !action && onChooseCase && (
          <button className="btn btn-primary" type="button" onClick={onChooseCase}>
            <ClipboardList size={16} /> {ACTION_LABEL[kind] || "Choose a case"}
          </button>
        )}
      </PanelHeading>
    </section>
  );
}

import React, { useEffect, useId, useState } from "react";
import { FileUp, Link2, Loader2, Trash2 } from "lucide-react";

import { api } from "../api/client.js";
import {
  caseFileOptionLabel,
  filedOnError,
  filingKindLabel,
  filingStatus,
  sourceSummary,
} from "./opposingFiling.js";

// "Responding to": the other side's filing the planned document answers.
// Shown only when a planned template declares one (see opposingFiling.js).
export function OpposingFilingPanel({ sessionId, requirement, onFilingChange }) {
  const [state, setState] = useState({ loading: true, filing: null, documents: [], problem: "" });
  const [source, setSource] = useState("case_file");
  const [documentId, setDocumentId] = useState("");
  const [file, setFile] = useState(null);
  const [description, setDescription] = useState("");
  const [filedOn, setFiledOn] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const ids = { help: useId() };

  function apply(response) {
    const filing = response.opposingFiling || null;
    setState((current) => ({
      ...current,
      loading: false,
      filing,
      documents: response.caseFileDocuments ?? current.documents,
      problem: response.caseFileProblem ?? current.problem,
    }));
    setDescription(filing?.description || "");
    setFiledOn(filing?.filedOn || "");
    onFilingChange?.(filing);
  }

  useEffect(() => {
    if (!sessionId) return undefined;
    const controller = new AbortController();
    api
      .opposingFiling(sessionId, { signal: controller.signal })
      .then(apply)
      .catch((err) => {
        if (err?.name === "AbortError") return;
        setState((current) => ({ ...current, loading: false }));
        setError(err.message);
      });
    return () => controller.abort();
    // `apply` only closes over setters and the change callback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  async function run(action) {
    const dateError = filedOnError(filedOn);
    if (dateError) {
      setError(dateError);
      return;
    }
    setBusy(true);
    setError("");
    try {
      apply(await action());
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function identify() {
    if (source === "case_file") {
      return run(() => api.chooseOpposingFiling(sessionId, { documentId, description, filedOn }));
    }
    const form = new FormData();
    form.append("file", file);
    if (description) form.append("description", description);
    if (filedOn) form.append("filedOn", filedOn);
    return run(() => api.uploadOpposingFiling(sessionId, form));
  }

  const status = filingStatus(requirement, state.filing);
  const filing = state.filing;
  const canIdentify = source === "case_file" ? Boolean(documentId) : Boolean(file);
  const detailsChanged = Boolean(filing) && (description !== (filing.description || "") || filedOn !== (filing.filedOn || ""));

  return (
    <section className="panel" aria-labelledby={`${ids.help}-title`}>
      <h3 id={`${ids.help}-title`}>Responding to</h3>
      <p id={ids.help} className="field-help">
        {requirement.question}
        {requirement.required ? " Required before the draft is written." : " Optional."}
        {requirement.help ? ` ${requirement.help}` : ""}
      </p>
      {status === "missing_required" && (
        <div className="warning-panel">
          {requirement.templateTitles.join(" and ")} answers the other side&apos;s filing, so it cannot be drafted until that filing is identified.
        </div>
      )}
      {error && <div className="warning-panel" role="alert">{error}</div>}
      {state.loading ? (
        <p className="muted"><Loader2 className="spin" size={16} /> Loading the case file…</p>
      ) : filing ? (
        <div className="stack">
          <p>
            <strong>{filing.displayName}</strong>
            <br />
            <span className="muted">{filingKindLabel(filing.filingKind)}. {sourceSummary(filing)}</span>
          </p>
          <label className="field">
            <span>How the brief names it</span>
            <input className="form-control" value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <label className="field">
            <span>Date filed</span>
            <input className="form-control" type="date" value={filedOn} onChange={(event) => setFiledOn(event.target.value)} />
          </label>
          <div className="button-row compact">
            <button className="btn btn-primary" type="button" disabled={busy || !detailsChanged} onClick={() => run(() => api.updateOpposingFiling(sessionId, { description, filedOn }))}>
              Save name and date
            </button>
            <button className="btn btn-light" type="button" disabled={busy} onClick={() => run(() => api.removeOpposingFiling(sessionId))}>
              <Trash2 size={16} /> Choose a different filing
            </button>
          </div>
        </div>
      ) : (
        <div className="stack">
          <fieldset className="field">
            <legend className="form-label">Where is it?</legend>
            <label className="checkbox-row">
              <input type="radio" name={`${ids.help}-source`} checked={source === "case_file"} onChange={() => setSource("case_file")} />
              <span>In the case file</span>
            </label>
            <label className="checkbox-row">
              <input type="radio" name={`${ids.help}-source`} checked={source === "upload"} onChange={() => setSource("upload")} />
              <span>Not in the case file -- upload the copy you were served</span>
            </label>
          </fieldset>
          {source === "case_file" ? (
            <label className="field">
              <span>Case file document</span>
              <select className="form-select" value={documentId} onChange={(event) => setDocumentId(event.target.value)}>
                <option value="">Choose a document…</option>
                {state.documents.map((document) => (
                  <option key={document.documentId} value={document.documentId}>{caseFileOptionLabel(document)}</option>
                ))}
              </select>
              {state.problem && <small className="field-help">The list may be incomplete: {state.problem}</small>}
              {!state.problem && !state.documents.length && <small className="field-help">No documents in this case file. Upload the filing instead.</small>}
            </label>
          ) : (
            <label className="field">
              <span>Filing to upload (PDF or Word)</span>
              <input className="form-control" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] || null)} />
              <small className="field-help">Exhibits attached to it are set aside, so only the brief is read.</small>
            </label>
          )}
          <label className="field">
            <span>Date filed (optional)</span>
            <input className="form-control" type="date" value={filedOn} onChange={(event) => setFiledOn(event.target.value)} />
          </label>
          <div className="button-row compact">
            <button className="btn btn-primary" type="button" disabled={busy || !canIdentify} onClick={identify}>
              {busy ? <Loader2 className="spin" size={16} /> : source === "case_file" ? <Link2 size={16} /> : <FileUp size={16} />}{" "}
              {source === "case_file" ? "Use this document" : "Upload"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

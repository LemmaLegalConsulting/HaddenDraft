import React from "react";
import { ClipboardCheck, FilePlus2, Loader2, Play, Upload } from "lucide-react";

export function TriagePanel({
  cases,
  matter,
  selectedMatterId,
  onSelectMatter,
  rubrics,
  selectedRubricId,
  onSelectRubric,
  assessment,
  history,
  busy,
  manualCaseBusy,
  onRunTriage,
  onCreateManualCase,
}) {
  const [manualCaseOpen, setManualCaseOpen] = React.useState(!matter);
  const [manualCase, setManualCase] = React.useState({
    clientName: "",
    matterType: "Eviction defense",
    jurisdiction: "Cleveland Municipal Court - Housing Division",
    posture: "",
    notes: "",
  });
  const [manualFiles, setManualFiles] = React.useState([]);

  async function submitManualCase(event) {
    event.preventDefault();
    const created = await onCreateManualCase?.({ ...manualCase, files: manualFiles });
    if (created) {
      setManualCase({ clientName: "", matterType: "Eviction defense", jurisdiction: "Cleveland Municipal Court - Housing Division", posture: "", notes: "" });
      setManualFiles([]);
      event.currentTarget.reset();
      setManualCaseOpen(false);
    }
  }

  const activeRubric = rubrics.find((rubric) => String(rubric.id) === String(selectedRubricId)) || rubrics[0];
  const activeAssessment = assessment || history?.[0] || null;

  return (
    <section className="triage-layout">
      <div className="panel triage-control-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Triage</p>
            <h3>Screen for representation priority</h3>
          </div>
        </div>

        <label className="field">
          <span>Rubric standard</span>
          <select value={selectedRubricId || activeRubric?.id || ""} onChange={(event) => onSelectRubric(event.target.value)}>
            {rubrics.map((rubric) => (
              <option key={rubric.id} value={rubric.id}>{rubric.name}</option>
            ))}
          </select>
        </label>
        {activeRubric && (
          <div className="rubric-summary">
            <strong>{activeRubric.description || activeRubric.name}</strong>
            <p>{activeRubric.standard}</p>
          </div>
        )}

        <label className="field">
          <span>Existing case</span>
          <select value={selectedMatterId || ""} onChange={(event) => onSelectMatter(event.target.value)} disabled={!cases.length}>
            {!cases.length && <option value="">No cases available</option>}
            {cases.map((item) => (
              <option key={item.id} value={item.id}>{item.client} - {item.matter || item.id}</option>
            ))}
          </select>
        </label>

        <div className="triage-selected-case">
          {matter ? (
            <>
              <strong>{matter.client}</strong>
              <span>{matter.matter}{matter.posture ? ` · ${matter.posture}` : ""}</span>
              <small>{matter.sourceSystem || "Case"} {matter.id}</small>
            </>
          ) : (
            <span>Select an existing case or create an ad-hoc intake.</span>
          )}
        </div>

        <button className="primary full" type="button" disabled={!matter || !activeRubric || busy} onClick={() => onRunTriage?.(activeRubric.id)}>
          {busy ? <Loader2 className="spin" size={16} /> : <Play size={16} />} Run triage
        </button>

        <div className="manual-case-panel triage-upload-panel">
          <button
            className="secondary full"
            type="button"
            aria-expanded={manualCaseOpen}
            onClick={() => setManualCaseOpen((current) => !current)}
          >
            <FilePlus2 size={16} /> Ad-hoc document upload
          </button>
          {manualCaseOpen && (
            <form className="manual-case-form" onSubmit={submitManualCase}>
              <div className="manual-case-grid">
                <label className="field">
                  <span>Client or household</span>
                  <input value={manualCase.clientName} onChange={(event) => setManualCase((current) => ({ ...current, clientName: event.target.value }))} />
                </label>
                <label className="field">
                  <span>Legal problem</span>
                  <input value={manualCase.matterType} onChange={(event) => setManualCase((current) => ({ ...current, matterType: event.target.value }))} />
                </label>
                <label className="field">
                  <span>Court or county</span>
                  <input value={manualCase.jurisdiction} onChange={(event) => setManualCase((current) => ({ ...current, jurisdiction: event.target.value }))} />
                </label>
                <label className="field">
                  <span>Posture</span>
                  <input value={manualCase.posture} onChange={(event) => setManualCase((current) => ({ ...current, posture: event.target.value }))} />
                </label>
              </div>
              <label className="field">
                <span>Intake notes</span>
                <textarea value={manualCase.notes} onChange={(event) => setManualCase((current) => ({ ...current, notes: event.target.value }))} rows={4} />
              </label>
              <label className="field">
                <span>Documents</span>
                <input
                  type="file"
                  multiple
                  accept=".txt,.md,.csv,.json,.html,.htm,.docx,.pdf,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(event) => setManualFiles(Array.from(event.target.files || []))}
                />
              </label>
              <button className="primary full" type="submit" disabled={manualCaseBusy || (!manualCase.notes.trim() && manualFiles.length === 0)}>
                {manualCaseBusy ? <Loader2 className="spin" size={16} /> : <Upload size={16} />} Create intake
              </button>
            </form>
          )}
        </div>
      </div>

      <div className="panel triage-result-panel">
        {activeAssessment ? (
          <>
            <div className="triage-result-heading">
              <ClipboardCheck size={20} />
              <div>
                <p className="eyebrow">Result</p>
                <h3>{activeAssessment.priority ? "Priority for full representation" : "Needs review"}</h3>
              </div>
              <span className={`status-pill ${activeAssessment.priority ? "approved" : "needs_review"}`}>
                {activeAssessment.confidence}
              </span>
            </div>
            <div className="triage-result-grid">
              <div>
                <span>Case type</span>
                <strong>{activeAssessment.caseType || "Unclassified"}</strong>
              </div>
              <div>
                <span>Label</span>
                <strong>{activeAssessment.priorityLabel || "needs_review"}</strong>
              </div>
            </div>
            {activeAssessment.summary && <p>{activeAssessment.summary}</p>}
            {activeAssessment.reasoning && <p>{activeAssessment.reasoning}</p>}
            <TriageList title="Matched criteria" items={activeAssessment.matchedCriteria} />
            <TriageList title="Missing information" items={activeAssessment.missingInformation} />
            <TriageEvidence evidence={activeAssessment.evidence} />
          </>
        ) : (
          <div className="empty-state compact-empty">
            <strong className="empty-state-title">No triage result yet</strong>
            <p>Select or create a case, choose a rubric, then run triage.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function TriageList({ title, items }) {
  if (!items?.length) return null;
  return (
    <div className="triage-list">
      <strong>{title}</strong>
      <ul>
        {items.map((item, index) => <li key={`${title}-${index}`}>{String(item)}</li>)}
      </ul>
    </div>
  );
}

function TriageEvidence({ evidence }) {
  if (!evidence?.length) return null;
  return (
    <div className="triage-list">
      <strong>Evidence</strong>
      <div className="triage-evidence-list">
        {evidence.map((item, index) => (
          <div className="triage-evidence" key={`evidence-${index}`}>
            <span>{item.label || "Evidence"}</span>
            <p>{item.excerpt || String(item)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

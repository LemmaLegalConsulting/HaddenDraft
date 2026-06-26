import React from "react";
import { AlertTriangle, ClipboardCheck, Loader2, Play, Upload } from "lucide-react";

export function TriagePanel({
  matter,
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
  const [caseSource, setCaseSource] = React.useState("existing");
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
      setCaseSource("existing");
    }
  }

  const activeRubric = rubrics.find((rubric) => String(rubric.id) === String(selectedRubricId)) || rubrics[0];
  const activeAssessment = assessment || history?.[0] || null;
  const canRun = Boolean(matter && activeRubric && !busy);
  const rubricSummary = activeRubric ? shortRubricSummary(activeRubric) : "";

  return (
    <section className="panel triage-panel">
      <div className="triage-control-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Triage</p>
            <h3>Triage case</h3>
          </div>
        </div>

        <div className="triage-source-options" role="radiogroup" aria-label="Case source">
          <label className="research-ai-toggle">
            <input
              type="radio"
              checked={caseSource === "existing"}
              onChange={() => setCaseSource("existing")}
            />
            <span>Existing case</span>
          </label>
          <label className="research-ai-toggle">
            <input
              type="radio"
              checked={caseSource === "upload"}
              onChange={() => setCaseSource("upload")}
            />
            <span>Upload case docs</span>
          </label>
        </div>

        {caseSource === "existing" && matter && (
          <div className="triage-selected-case" aria-label="Selected case">
            <span>Using selected case</span>
            <strong>{matter.client}</strong>
          </div>
        )}

        {caseSource === "existing" && !matter && (
          <div className="triage-missing-info">
            <AlertTriangle size={16} />
            <span>Select a case on the Case screen before running triage.</span>
          </div>
        )}

        {caseSource === "upload" && (
          <form className="manual-case-form triage-upload-panel" onSubmit={submitManualCase}>
            <label className="field">
              <span>Notes</span>
              <textarea
                value={manualCase.notes}
                onChange={(event) => setManualCase((current) => ({ ...current, notes: event.target.value }))}
                rows={5}
                placeholder="Paste intake notes or key facts."
              />
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

        <label className="field">
          <span>Rubric standard</span>
          <select value={selectedRubricId || activeRubric?.id || ""} onChange={(event) => onSelectRubric(event.target.value)}>
            {rubrics.map((rubric) => (
              <option key={rubric.id} value={rubric.id}>{rubric.name}</option>
            ))}
          </select>
        </label>
        {rubricSummary && (
          <div className="rubric-summary">
            <strong>{activeRubric.name}</strong>
            <p>{rubricSummary}</p>
          </div>
        )}

        <button className="primary full" type="button" disabled={!canRun} onClick={() => onRunTriage?.(activeRubric.id)}>
          {busy ? <Loader2 className="spin" size={16} /> : <Play size={16} />} Run triage
        </button>

        {activeAssessment ? (
          <div className="triage-result-panel">
            <div className="triage-result-heading">
              <ClipboardCheck size={20} />
              <div>
                <p className="eyebrow">Result</p>
                <h3>{triageResultTitle(activeAssessment)}</h3>
              </div>
              <span className={`status-pill ${activeAssessment.priority ? "approved" : "needs_review"}`}>
                {activeAssessment.confidence}
              </span>
            </div>
            <TriageText title="Summary" value={activeAssessment.summary} defaultOpen />
            <TriageText title="Reasoning" value={activeAssessment.reasoning} />
            <TriageList title="Missing details / unanswered questions" items={activeAssessment.missingInformation} important defaultOpen />
            <TriageList title="Matched criteria" items={activeAssessment.matchedCriteria} />
            <TriageEvidence evidence={activeAssessment.evidence} />
          </div>
        ) : (
          <div className="empty-state compact-empty">
            <strong className="empty-state-title">No triage result yet</strong>
            <p>Choose a rubric, then run triage.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function shortRubricSummary(rubric) {
  if (rubric.description) return rubric.description;
  const criteria = rubric.criteria || [];
  if (criteria.length) return criteria.slice(0, 2).join(" ");
  return "";
}

function triageResultTitle(assessment) {
  const label = String(assessment?.priorityLabel || "").trim();
  if (!label || label === "needs_review") {
    return assessment?.priority ? "Priority for full representation" : "Needs review";
  }
  return label
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function displayLines(value) {
  if (Array.isArray(value)) return value.map((item) => String(item).replace(/^[-*]\s*/, "").trim()).filter(Boolean);
  if (!value) return [];
  const text = String(value).trim();
  if (!text) return [];
  if (text.startsWith("[") && text.endsWith("]")) {
    try {
      const normalized = text.replaceAll("'", "\"");
      const parsed = JSON.parse(normalized);
      if (Array.isArray(parsed)) return displayLines(parsed);
    } catch {
      // Fall through to line cleanup.
    }
  }
  return text
    .split(/\r?\n/)
    .map((line) => line.replace(/^[-*]\s*/, "").trim())
    .filter(Boolean);
}

function TriageText({ title, value, defaultOpen = false }) {
  const lines = displayLines(value);
  if (!lines.length) return null;
  return (
    <details className="triage-accordion" open={defaultOpen}>
      <summary>{title}</summary>
      {lines.length > 1 ? (
        <ul>
          {lines.map((line, index) => <li key={`${title}-${index}`}>{line}</li>)}
        </ul>
      ) : (
        <p>{lines[0]}</p>
      )}
    </details>
  );
}

function TriageList({ title, items, important = false, defaultOpen = false }) {
  if (!items?.length) return null;
  return (
    <details className={`triage-accordion ${important ? "important" : ""}`} open={defaultOpen}>
      <summary>{title}</summary>
      <ul>
        {items.map((item, index) => <li key={`${title}-${index}`}>{String(item).replace(/^[-*]\s*/, "")}</li>)}
      </ul>
    </details>
  );
}

function TriageEvidence({ evidence }) {
  if (!evidence?.length) return null;
  return (
    <details className="triage-accordion">
      <summary>Evidence</summary>
      <div className="triage-evidence-list">
        {evidence.map((item, index) => (
          <div className="triage-evidence" key={`evidence-${index}`}>
            <span>{item.label || "Evidence"}</span>
            <p>{item.excerpt || String(item)}</p>
          </div>
        ))}
      </div>
    </details>
  );
}

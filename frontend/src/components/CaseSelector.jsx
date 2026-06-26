import React from "react";
import { ClipboardCheck, FilePlus2, FileText, Loader2, MessageSquare, RotateCcw, Search, Upload } from "lucide-react";

function detailValue(item, label) {
  return (item.details || []).find((detail) => detail.label === label)?.value || "";
}

function caseNumberFor(item) {
  return item.caseNumber || detailValue(item, "Case number") || item.id;
}

function isLegalServerCase(item) {
  return (item.sourceSystem || "LegalServer").toLowerCase() === "legalserver";
}

function lastActivityLabel(item) {
  if (!isLegalServerCase(item) || !item.lastActivityAt) return "";
  const lastActivity = new Date(item.lastActivityAt);
  if (Number.isNaN(lastActivity.getTime())) return "";
  const days = Math.max(0, Math.floor((Date.now() - lastActivity.getTime()) / 86400000));
  if (days === 0) return "Active today";
  if (days === 1) return "1 day inactive";
  return `${days} days inactive`;
}

export function CaseSelector({
  cases,
  selectedMatterId,
  onSelect,
  matter,
  legalserver,
  legalserverLoading = false,
  search,
  onSearchChange,
  onSearch,
  onSearchReset,
  caseBusy,
  manualCaseBusy,
  onCreateManualCase,
  onModeChange,
}) {
  const [manualCaseOpen, setManualCaseOpen] = React.useState(false);
  const [caseSource, setCaseSource] = React.useState("legalserver");
  const [manualCase, setManualCase] = React.useState({
    clientName: "",
    matterType: "",
    jurisdiction: "",
    posture: "",
    notes: "",
  });
  const [manualFiles, setManualFiles] = React.useState([]);
  const connected = Boolean(legalserver?.connected);
  const legalserverCases = cases.filter(isLegalServerCase);
  const localCases = cases.filter((item) => !isLegalServerCase(item));
  const visibleCases = caseSource === "local" ? localCases : legalserverCases;

  React.useEffect(() => {
    if (!legalserverLoading && !connected && caseSource === "legalserver" && !legalserverCases.length && localCases.length) {
      setCaseSource("local");
    }
  }, [caseSource, connected, legalserverCases.length, legalserverLoading, localCases.length]);

  return (
    <div className="panel">
      <div className="case-source-row">
        <div className="case-source-toggle" role="radiogroup" aria-label="Case source">
          <label className={caseSource === "legalserver" ? "selected" : ""}>
            <input
              type="radio"
              name="case-source"
              value="legalserver"
              checked={caseSource === "legalserver"}
              disabled={legalserverLoading}
              onChange={() => setCaseSource("legalserver")}
            />
            {legalserverLoading ? "Checking LegalServer" : "LegalServer case"}
          </label>
          <label className={caseSource === "local" ? "selected" : ""}>
            <input
              type="radio"
              name="case-source"
              value="local"
              checked={caseSource === "local"}
              onChange={() => setCaseSource("local")}
            />
            Local case
          </label>
        </div>
        <button
          className="primary new-local-case-button"
          type="button"
          aria-expanded={manualCaseOpen}
          onClick={() => {
            setCaseSource("local");
            setManualCaseOpen((current) => !current);
          }}
        >
          <FilePlus2 size={16} /> New local case
        </button>
      </div>
      <div className="manual-case-panel">
        {manualCaseOpen && (
          <form
            className="manual-case-form"
            onSubmit={async (event) => {
              event.preventDefault();
              const created = await onCreateManualCase?.({ ...manualCase, files: manualFiles });
              if (created) {
                setCaseSource("local");
                setManualCase({ clientName: "", matterType: "", jurisdiction: "", posture: "", notes: "" });
                setManualFiles([]);
                event.currentTarget.reset();
                setManualCaseOpen(false);
              }
            }}
          >
            <div className="manual-case-grid">
              <label className="field">
                <span>Client or household</span>
                <input
                  value={manualCase.clientName}
                  onChange={(event) => setManualCase((current) => ({ ...current, clientName: event.target.value }))}
                  placeholder="Client name"
                />
              </label>
              <label className="field">
                <span>Legal problem</span>
                <input
                  value={manualCase.matterType}
                  onChange={(event) => setManualCase((current) => ({ ...current, matterType: event.target.value }))}
                  placeholder="Eviction, conditions, subsidy..."
                />
              </label>
              <label className="field">
                <span>Court or county</span>
                <input
                  value={manualCase.jurisdiction}
                  onChange={(event) => setManualCase((current) => ({ ...current, jurisdiction: event.target.value }))}
                  placeholder="Optional"
                />
              </label>
              <label className="field">
                <span>Posture</span>
                <input
                  value={manualCase.posture}
                  onChange={(event) => setManualCase((current) => ({ ...current, posture: event.target.value }))}
                  placeholder="Intake, pre-hearing..."
                />
              </label>
            </div>
            <label className="field">
              <span>Case description or intake notes</span>
              <textarea
                value={manualCase.notes}
                onChange={(event) => setManualCase((current) => ({ ...current, notes: event.target.value }))}
                placeholder="Type the facts, timeline, defenses, relief requested, or raw intake notes."
                rows={5}
              />
            </label>
            <label className="field">
              <span>Case files</span>
              <input
                type="file"
                multiple
                accept=".txt,.md,.csv,.json,.html,.htm,.docx,.pdf,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) => setManualFiles(Array.from(event.target.files || []))}
              />
            </label>
            <button className="primary full" type="submit" disabled={manualCaseBusy || (!manualCase.notes.trim() && manualFiles.length === 0)}>
              {manualCaseBusy ? <Loader2 className="spin" size={16} /> : <Upload size={16} />} Create and select
            </button>
          </form>
        )}
      </div>
      {connected && caseSource === "legalserver" && !legalserverLoading && (
        <form className="case-search" onSubmit={onSearch}>
          <input
            aria-label="Search LegalServer matters"
            placeholder="Party, matter, or case ID"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
          <button className="secondary" type="submit" disabled={caseBusy}>
            {caseBusy ? <Loader2 className="spin" size={16} /> : <Search size={16} />} Search
          </button>
          <button className="secondary icon-button" type="button" disabled={caseBusy || !search} onClick={onSearchReset} title="Show assigned matters">
            <RotateCcw size={16} />
          </button>
        </form>
      )}
      <div className="case-list">
        {visibleCases.map((item) => {
          const activity = lastActivityLabel(item);
          const status = item.posture || detailValue(item, "Status");
          return (
            <button
              key={item.id}
              className={`case-card ${selectedMatterId === item.id ? "selected" : ""}`}
              onClick={() => onSelect(item.id)}
              type="button"
              aria-label={`${item.client || "Unnamed client"}, case ${caseNumberFor(item)}`}
            >
              <strong className="case-client">{item.client || "Unnamed client"}</strong>
              <span className="case-number">{caseNumberFor(item)}</span>
              <span className="case-muted case-type">{item.matter || "Case"}</span>
              <span className="case-muted case-status">{status}</span>
              {activity && <span className="case-muted case-activity">{activity}</span>}
            </button>
          );
        })}
        {!visibleCases.length && (
          <div className="empty-state compact-empty">
            <strong className="empty-state-title">
              {caseSource === "legalserver" ? (legalserverLoading ? "Checking LegalServer" : connected ? "No matters found" : "No LegalServer cases") : "No local cases yet"}
            </strong>
            <p>
              {caseSource === "legalserver"
                ? legalserverLoading
                  ? "Checking your LegalServer connection and assigned matters."
                  : connected
                  ? "LegalServer did not return matters for this identifier."
                  : "Connect LegalServer to load assigned matters."
                : "Create a local case with notes or files."}
            </p>
          </div>
        )}
      </div>
      {matter && (
        <div className="matter-summary">
          <dl className="case-details">
            {(matter.details || []).map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
          {matter.summary && <p>{matter.summary}</p>}
          <div className="case-actions">
            <button className="primary" type="button" onClick={() => onModeChange("case_chat")}>
              <MessageSquare size={16} /> Chat
            </button>
            <button className="secondary" type="button" onClick={() => onModeChange("research")}>
              <Search size={16} /> Search sources
            </button>
            <button className="secondary" type="button" onClick={() => onModeChange("triage")}>
              <ClipboardCheck size={16} /> Triage
            </button>
            <button className="secondary" type="button" onClick={() => onModeChange("draft")}>
              <FileText size={16} /> Draft
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

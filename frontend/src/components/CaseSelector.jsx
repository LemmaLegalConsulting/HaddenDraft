import React from "react";
import { ChevronDown, FilePlus2, FileText, Link2, Loader2, MessageSquare, RotateCcw, Search, Unplug, Upload } from "lucide-react";

export function CaseSelector({
  cases,
  selectedMatterId,
  onSelect,
  matter,
  legalserver,
  identifier,
  onIdentifierChange,
  onConnect,
  onDisconnect,
  accountBusy,
  search,
  onSearchChange,
  onSearch,
  onSearchReset,
  caseBusy,
  manualCaseBusy,
  onCreateManualCase,
  onModeChange,
}) {
  const [connectionDetailsOpen, setConnectionDetailsOpen] = React.useState(false);
  const [manualCaseOpen, setManualCaseOpen] = React.useState(false);
  const [manualCase, setManualCase] = React.useState({
    clientName: "",
    matterType: "",
    jurisdiction: "",
    posture: "",
    notes: "",
  });
  const [manualFiles, setManualFiles] = React.useState([]);
  const connected = Boolean(legalserver?.connected);
  const configured = legalserver?.configured !== false;
  const syncError = legalserver?.syncError;
  const connectionSummary = !configured
    ? "LegalServer not configured"
    : connected
      ? "LegalServer connected"
      : "LegalServer disconnected";

  return (
    <div className="panel">
      <form className="connection-panel" onSubmit={onConnect}>
        <button
          className="connection-summary-toggle"
          type="button"
          aria-expanded={connectionDetailsOpen}
          onClick={() => setConnectionDetailsOpen((current) => !current)}
        >
          <span>{connectionSummary}</span>
          <ChevronDown className={connectionDetailsOpen ? "chevron open" : "chevron"} size={16} />
        </button>
        {connectionDetailsOpen && (
          <>
            <div className="connection-detail">
              <span>{connected ? "Connected as" : "No LegalServer account connected"}</span>
              {connected && <strong>{legalserver.identifier}</strong>}
              {!connected && configured && <small>Use the username or email for assigned matters.</small>}
              {!configured && <small>LegalServer API credentials are not configured for this environment.</small>}
            </div>
            {configured && (
              <div className="connection-controls">
                <input
                  aria-label="LegalServer identifier"
                  placeholder={legalserver?.suggestedIdentifier || "LegalServer username or email"}
                  value={identifier}
                  onChange={(event) => onIdentifierChange(event.target.value)}
                />
                <button className="secondary" type="submit" disabled={accountBusy || !identifier.trim()}>
                  {accountBusy ? <Loader2 className="spin" size={16} /> : <Link2 size={16} />} Connect
                </button>
                {connected && (
                  <button className="secondary icon-button" type="button" disabled={accountBusy} onClick={onDisconnect} title="Disconnect LegalServer account">
                    <Unplug size={16} />
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </form>
      {connectionDetailsOpen && syncError && syncError !== "not_connected" && <div className="inline-error">LegalServer sync: {syncError}</div>}
      <div className="manual-case-panel">
        <button
          className="secondary full"
          type="button"
          aria-expanded={manualCaseOpen}
          onClick={() => setManualCaseOpen((current) => !current)}
        >
          <FilePlus2 size={16} /> New local case
        </button>
        {manualCaseOpen && (
          <form
            className="manual-case-form"
            onSubmit={async (event) => {
              event.preventDefault();
              const created = await onCreateManualCase?.({ ...manualCase, files: manualFiles });
              if (created) {
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
      {connected && (
        connectionDetailsOpen && (
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
        )
      )}
      <div className="case-list">
        {cases.map((item) => (
          <button
            key={item.id}
            className={`case-card ${selectedMatterId === item.id ? "selected" : ""}`}
            onClick={() => onSelect(item.id)}
          >
            <span>{item.client}</span>
            <strong>{item.matter}</strong>
            <small>{item.posture}</small>
          </button>
        ))}
        {!cases.length && (
          <div className="empty-state compact-empty">
            <strong className="empty-state-title">{connected ? "No matters found" : "No cases yet"}</strong>
            <p>
              {connected
                ? "LegalServer did not return matters for this identifier."
                : "Create a local case with notes or files, or connect LegalServer to load assigned matters."}
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
            <button className="secondary" type="button" onClick={() => onModeChange("draft")}>
              <FileText size={16} /> Draft
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

import React from "react";
import { CheckCircle2, ChevronDown, FilePlus2, FolderOpen, ListFilter, Loader2, RotateCcw, Search, Upload } from "lucide-react";

import { caseNumberFor, caseTitleFor, detailValue, isLegalServerCase, lastActivityLabel } from "./casePresentation.js";
import { DEFAULT_CASE_FILTERS, activeFilterCount, describeFilters } from "./caseFilters.js";

const STATUS_OPTIONS = [
  ["open", "Open cases"],
  ["closed", "Closed cases"],
  ["all", "Open and closed"],
];

const ASSIGNED_OPTIONS = [
  ["all", "All cases I can see"],
  ["mine", "Only cases I handle"],
];

const SORT_OPTIONS = [
  ["activity", "Last activity"],
  ["opened", "Date opened"],
];

export function CaseSelector({
  cases,
  selectedMatterId,
  onSelect,
  onPreview,
  legalserver,
  legalserverLoading = false,
  search,
  onSearchChange,
  onSearch,
  onSearchReset,
  filters,
  onFiltersChange,
  listMeta,
  onShowMore,
  caseBusy,
  manualCaseBusy,
  onCreateManualCase,
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
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const connected = Boolean(legalserver?.connected);
  const legalserverCases = cases.filter(isLegalServerCase);
  const localCases = cases.filter((item) => !isLegalServerCase(item));
  const visibleCases = caseSource === "local" ? localCases : legalserverCases;
  const activeFilters = { ...DEFAULT_CASE_FILTERS, ...(filters || {}) };
  const filterCount = activeFilterCount(activeFilters);
  const problemCodes = listMeta?.problemCodes || [];
  const total = listMeta?.total ?? visibleCases.length;
  // Quick cases are held entirely in this browser's list, so paging through the
  // server's results only applies to the LegalServer tab.
  const showMoreAvailable = caseSource === "legalserver" && Boolean(listMeta?.hasMore);

  function updateFilter(key, value) {
    onFiltersChange?.({ ...activeFilters, [key]: value });
  }

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
            Quick case
          </label>
        </div>
        <button
          className="btn btn-primary new-local-case-button"
          type="button"
          aria-expanded={manualCaseOpen}
          onClick={() => {
            setCaseSource("local");
            setManualCaseOpen((current) => !current);
          }}
        >
          <FilePlus2 size={16} /> New quick case
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
                <input className="form-control"
                  value={manualCase.clientName}
                  onChange={(event) => setManualCase((current) => ({ ...current, clientName: event.target.value }))}
                  placeholder="Client name"
                />
              </label>
              <label className="field">
                <span>Legal problem</span>
                <input className="form-control"
                  value={manualCase.matterType}
                  onChange={(event) => setManualCase((current) => ({ ...current, matterType: event.target.value }))}
                  placeholder="Eviction, conditions, subsidy..."
                />
              </label>
              <label className="field">
                <span>Court or county</span>
                <input className="form-control"
                  value={manualCase.jurisdiction}
                  onChange={(event) => setManualCase((current) => ({ ...current, jurisdiction: event.target.value }))}
                  placeholder="Optional"
                />
              </label>
              <label className="field">
                <span>Posture</span>
                <input className="form-control"
                  value={manualCase.posture}
                  onChange={(event) => setManualCase((current) => ({ ...current, posture: event.target.value }))}
                  placeholder="Intake, pre-hearing..."
                />
              </label>
            </div>
            <label className="field">
              <span>Case description or intake notes</span>
              <textarea className="form-control"
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
            <button className="btn btn-primary full" type="submit" disabled={manualCaseBusy || (!manualCase.notes.trim() && manualFiles.length === 0)}>
              {manualCaseBusy ? <Loader2 className="spin" size={16} /> : <Upload size={16} />} Create and select
            </button>
          </form>
        )}
      </div>
      {connected && caseSource === "legalserver" && !legalserverLoading && (
        <>
          <form className="case-search" onSubmit={onSearch}>
            <input className="form-control"
              aria-label="Search LegalServer matters"
              placeholder="Party, matter, or case ID"
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
            />
            <button className="btn btn-outline-secondary" type="submit" disabled={caseBusy}>
              {caseBusy ? <Loader2 className="spin" size={16} /> : <Search size={16} />} Search
            </button>
            <button
              className={filterCount ? "btn btn-outline-secondary case-filter-toggle has-filters" : "btn btn-outline-secondary case-filter-toggle"}
              type="button"
              aria-expanded={filtersOpen}
              aria-controls="case-filter-panel"
              onClick={() => setFiltersOpen((current) => !current)}
            >
              <ListFilter size={16} /> Filter
              {filterCount > 0 && <span className="case-filter-count">{filterCount}</span>}
              <ChevronDown className={filtersOpen ? "chevron open" : "chevron"} size={15} />
            </button>
            <button className="btn btn-outline-secondary icon-button" type="button" disabled={caseBusy || (!search && !filterCount)} onClick={onSearchReset} title="Reset search and filters" aria-label="Reset search and filters">
              <RotateCcw size={16} />
            </button>
          </form>
          {filtersOpen && (
            <div className="case-filter-panel" id="case-filter-panel">
              <label className="field compact-field">
                <span>Status</span>
                <select className="form-select" value={activeFilters.status} onChange={(event) => updateFilter("status", event.target.value)}>
                  {STATUS_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label className="field compact-field">
                <span>Case handler</span>
                <select className="form-select" value={activeFilters.assigned} onChange={(event) => updateFilter("assigned", event.target.value)}>
                  {ASSIGNED_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label className="field compact-field">
                <span>Legal problem</span>
                <select className="form-select" value={activeFilters.problem} onChange={(event) => updateFilter("problem", event.target.value)}>
                  <option value="">Every legal problem</option>
                  {problemCodes.map((code) => <option key={code} value={code}>{code}</option>)}
                </select>
              </label>
              <label className="field compact-field">
                <span>Sort by</span>
                <select className="form-select" value={activeFilters.sort} onChange={(event) => updateFilter("sort", event.target.value)}>
                  {SORT_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
            </div>
          )}
          {visibleCases.length > 0 && (
            <p className="case-list-summary muted">
              {/* The total spans quick cases too, so it is only quoted when
                  there is genuinely another page to fetch. */}
              {describeFilters(activeFilters, { total: showMoreAvailable ? total : 0, shown: visibleCases.length })}
            </p>
          )}
        </>
      )}
      <div className="case-list">
        {visibleCases.length > 0 && (
          <div className="case-list-header" aria-hidden="true">
            <span>Case title</span><span>Case number</span><span>Legal problem</span><span>Status</span><span>Recent activity</span><span>Actions</span>
          </div>
        )}
        {visibleCases.map((item) => {
          const activity = lastActivityLabel(item);
          const status = item.posture || detailValue(item, "Status");
          return (
            <article
              key={item.id}
              className={`case-card case-card-activatable ${selectedMatterId === item.id ? "selected" : ""}`}
              aria-current={selectedMatterId === item.id ? "true" : undefined}
              title={selectedMatterId === item.id ? "Active case" : "Make this the active case"}
              onClick={() => { if (selectedMatterId !== item.id) onSelect(item.id); }}
            >
              <strong className="case-client">{caseTitleFor(item)}</strong>
              <span className="case-number">{caseNumberFor(item)}</span>
              <span className="case-muted case-type">{item.matter || "Case"}</span>
              <span className="case-muted case-status">{status}</span>
              <span className="case-muted case-activity">{activity}</span>
              <span className="case-row-actions">
                {selectedMatterId === item.id ? (
                  <span className="active-case-indicator"><CheckCircle2 size={15} /> Active</span>
                ) : (
                  <button className="btn btn-outline-secondary case-activate-button" type="button" onClick={(event) => { event.stopPropagation(); onSelect(item.id); }}>
                    Make active
                  </button>
                )}
                <button
                  className="btn btn-outline-secondary icon-button"
                  type="button"
                  aria-label={`Open case preview for ${caseTitleFor(item)}`}
                  title="Open case preview"
                  onClick={(event) => { event.stopPropagation(); onPreview(item.id); }}
                >
                  <FolderOpen size={17} />
                </button>
              </span>
            </article>
          );
        })}
        {!visibleCases.length && (
          <div className="empty-state compact-empty">
            <strong className="empty-state-title">
              {caseSource !== "legalserver"
                ? "No quick cases yet"
                : legalserverLoading
                ? "Checking LegalServer"
                : !connected
                ? "No LegalServer cases"
                : filterCount > 0
                ? "No cases match these filters"
                : "No matters found"}
            </strong>
            <p>
              {caseSource !== "legalserver"
                ? "Create a quick case with notes or files."
                : legalserverLoading
                ? "Checking your LegalServer connection and assigned matters."
                : !connected
                ? "Connect LegalServer to load assigned matters."
                : filterCount > 0
                ? "Widen the filter to see closed cases, a colleague's caseload, or every legal problem."
                : "LegalServer did not return matters for this identifier."}
            </p>
          </div>
        )}
      </div>
      {showMoreAvailable && (
        <div className="case-list-more">
          <button className="btn btn-outline-secondary" type="button" disabled={caseBusy} onClick={onShowMore}>
            {caseBusy ? <Loader2 className="spin" size={16} /> : <ChevronDown size={16} />}
            {" "}Show {Math.min(20, Math.max(total - visibleCases.length, 0)) || 20} more
          </button>
        </div>
      )}
    </div>
  );
}

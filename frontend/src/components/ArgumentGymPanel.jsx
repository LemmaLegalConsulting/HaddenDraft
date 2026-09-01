import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Check,
  ClipboardCopy,
  FileText,
  FolderOpen,
  Gavel,
  Landmark,
  ListChecks,
  Loader2,
  Plus,
  Printer,
  Ruler,
  Scale,
  Search,
  Swords,
  Upload,
  X,
} from "lucide-react";

import { api } from "../api/client.js";
import { useModalDismiss } from "../hooks/useModalDismiss.js";
import {
  CASE_CONTEXT_CHOICES,
  COURT_RULE_MODES,
  JURISDICTION_MODES,
  canStartRun,
  challengeSummary,
  checkStatusSummary,
  checklistItemsFromText,
  checklistItemsToText,
  checklistSummary,
  checksByStatus,
  cleanJurisdictionDetail,
  complianceGroups,
  complianceSummary,
  copyTextForChallenge,
  courtSummary,
  coverageSummary,
  effectiveSelection,
  elementState,
  exhibitSummary,
  findingCounts,
  findingsByCheck,
  groupChecks,
  matterFilterOptions,
  materialsByOrigin,
  rankedChallenges,
  replaceChallenge,
  rerunSummary,
  revisionTargets,
  ruleAuditSummary,
  sessionStatus,
  sessionSubtitle,
  sortSessions,
  targetLabel,
  toggleCheck,
  truncationNotice,
  unverifiedRules,
  updatePlanItem,
  usesMunicipality,
} from "./argumentGym.js";

const FILTERS = [
  { id: "open", label: "Open" },
  { id: "all", label: "All" },
  { id: "resolved", label: "Handled" },
];

function SessionList({ sessions, matters, matterId, onMatterChange, query, onQueryChange, activeId, onOpen, onNew, busy }) {
  return (
    <aside className="gym-sessions">
      <div className="gym-sessions-header">
        <h4>Sessions</h4>
        <button className="btn btn-primary" type="button" onClick={onNew} disabled={busy}>
          <Plus size={16} /> New
        </button>
      </div>
      <label className="form-label">
        Case
        <select className="form-select" value={matterId} onChange={(event) => onMatterChange(event.target.value)}>
          {matterFilterOptions(matters).map((option) => (
            <option key={option.id || "all"} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <input
        className="form-control"
        type="search"
        placeholder="Find a session"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
      />
      {sessions.length === 0 ? (
        <p className="muted">No sessions yet. Start one with New.</p>
      ) : (
        <ul className="gym-session-list">
          {sortSessions(sessions).map((session) => (
            <li key={session.id}>
              <button
                type="button"
                className={`gym-session${session.id === activeId ? " active" : ""}`}
                onClick={() => onOpen(session)}
              >
                <strong>{session.title}</strong>
                <span className="muted">{sessionSubtitle(session)}</span>
                <span className="muted">{sessionStatus(session)}</span>
                {session.verdict && <span className="gym-session-verdict">{session.verdict}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

function JurisdictionControls({ workspace, courts, courtTypes, detection, busy, onChange, onDetect }) {
  const detail = workspace?.jurisdictionDetail || {};
  const manual = workspace?.jurisdictionMode === "manual";
  const courtType = detail.courtType || workspace?.court?.courtType || "";
  const municipalityApplies = usesMunicipality(courtType, courtTypes);

  const patchDetail = (patch) =>
    onChange({
      jurisdictionMode: "manual",
      jurisdictionDetail: cleanJurisdictionDetail({ ...detail, ...patch }, courtTypes),
    });

  return (
    <details className="gym-jurisdiction" open={!workspace?.court}>
      <summary>
        <Landmark size={16} /> Jurisdiction and filing rules
      </summary>
      <div className="gym-jurisdiction-body">
        <div className="gym-mode-row">
          {JURISDICTION_MODES.map((mode) => (
            <label key={mode.id} className={`gym-mode ${workspace?.jurisdictionMode === mode.id ? "active" : ""}`}>
              <input
                type="radio"
                name="gym-jurisdiction-mode"
                checked={workspace?.jurisdictionMode === mode.id}
                onChange={() => onChange({ jurisdictionMode: mode.id })}
              />
              {mode.label}
            </label>
          ))}
          <button className="btn btn-outline-secondary" type="button" onClick={onDetect} disabled={busy}>
            <Search size={16} /> What would detection pick?
          </button>
        </div>

        {detection && (
          <p className="muted gym-detection">
            {detection.detected
              ? `Detection picks ${detection.court?.label}. ${detection.reason}`
              : detection.reason}
          </p>
        )}

        {manual && (
          <div className="gym-jurisdiction-fields">
            <label className="form-label">
              Court type
              <select
                className="form-select"
                value={courtType}
                onChange={(event) => patchDetail({ courtType: event.target.value })}
              >
                <option value="">Choose…</option>
                {courtTypes.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-label">
              State
              <input className="form-control" value={detail.state || ""} onChange={(event) => patchDetail({ state: event.target.value })} />
            </label>
            <label className="form-label">
              County
              <input className="form-control" value={detail.county || ""} onChange={(event) => patchDetail({ county: event.target.value })} />
            </label>
            {municipalityApplies ? (
              <label className="form-label">
                Municipality
                <input
                  className="form-control"
                  value={detail.municipality || ""}
                  onChange={(event) => patchDetail({ municipality: event.target.value })}
                />
              </label>
            ) : (
              <label className="form-label">
                Division or district
                <input
                  className="form-control"
                  placeholder="Eighth Appellate District"
                  value={detail.division || ""}
                  onChange={(event) => patchDetail({ division: event.target.value })}
                />
              </label>
            )}
          </div>
        )}

        <div className="gym-mode-row">
          {COURT_RULE_MODES.map((mode) => (
            <label key={mode.id} className={`gym-mode ${workspace?.courtRuleMode === mode.id ? "active" : ""}`}>
              <input
                type="radio"
                name="gym-rule-mode"
                checked={workspace?.courtRuleMode === mode.id}
                onChange={() => onChange({ courtRuleMode: mode.id })}
              />
              {mode.label}
            </label>
          ))}
        </div>

        {workspace?.courtRuleMode === "manual" && (
          <label className="form-label">
            Court whose rules apply
            <select
              className="form-select"
              value={workspace?.court?.slug || ""}
              onChange={(event) => onChange({ courtSlug: event.target.value })}
            >
              <option value="">Choose a court…</option>
              {courts.map((court) => (
                <option key={court.slug} value={court.slug}>
                  {court.label}
                  {court.place ? ` — ${court.place}` : ""}
                  {court.verification === "verified" ? "" : " (unverified)"}
                </option>
              ))}
            </select>
          </label>
        )}
        <p className="muted">{courtSummary({ court: workspace?.court, detection: { mode: workspace?.courtRuleMode } })}</p>
      </div>
    </details>
  );
}

function CompliancePanel({ compliance }) {
  const groups = complianceGroups(compliance);
  const profile = compliance?.profile;
  return (
    <section className="gym-compliance">
      <h4>
        <Ruler size={16} /> Filing format
      </h4>
      <p className="muted">
        {courtSummary({ court: profile ? { ...profile, label: profile.name } : null, detection: compliance?.detection })}
      </p>
      <p className={groups.errors.length ? "gym-compliance-bad" : "muted"}>{complianceSummary(compliance)}</p>
      {groups.total > 0 && (
        <ul className="gym-source-list">
          {[...groups.errors, ...groups.warnings, ...groups.unmeasured].map((finding) => (
            <li key={finding.findingId} className={`gym-finding gym-finding-${finding.severity}`}>
              <strong>{finding.target}</strong>
              <p className="gym-source-snippet">{finding.message}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function CheckSelector({ catalog, defaults, selected, settings, checklists, checklistId, busy, onToggle, onSettings, onChecklist }) {
  const passiveSettings = settings?.passive_voice || {};
  return (
    <details className="gym-checks" open>
      <summary>
        <ListChecks size={16} /> Checks to run ({selected.length} of {catalog.length})
      </summary>
      <div className="gym-checks-body">
        <p className="muted">
          Nothing runs that you have not chosen. A check you turn off produces no findings at all, which is not the
          same as a check that found nothing.
        </p>
        {groupChecks(catalog).map((group) => (
          <fieldset key={group.id} className="gym-check-group">
            <legend>{group.label}</legend>
            {group.checks.map((check) => (
              <label key={check.id} className="gym-check">
                <input
                  type="checkbox"
                  checked={selected.includes(check.id)}
                  disabled={busy}
                  onChange={() => onToggle(check.id)}
                />
                <span>
                  <strong>{check.label}</strong>
                  <span className="gym-check-kind">{check.kind === "model" ? "AI" : "deterministic"}</span>
                  <span className="muted">{check.description}</span>
                  {check.requires.length > 0 && (
                    <span className="muted">Needs: {check.requires.join(", ").replace(/_/g, " ")}</span>
                  )}
                </span>
              </label>
            ))}
          </fieldset>
        ))}

        {selected.includes("passive_voice") && (
          <label className="form-label">
            Passive phrases this court expects (one per line)
            <textarea
              className="form-control"
              rows={3}
              defaultValue={(passiveSettings.acceptedPassivePhrases || []).join("\n")}
              onBlur={(event) =>
                onSettings({
                  passive_voice: {
                    acceptedPassivePhrases: event.target.value
                      .split("\n")
                      .map((line) => line.trim())
                      .filter(Boolean),
                  },
                })
              }
            />
          </label>
        )}

        {selected.includes("custom_checklist") && (
          <label className="form-label">
            Your checklist
            <select className="form-select" value={checklistId || ""} onChange={(event) => onChecklist(event.target.value)}>
              <option value="">Choose a checklist…</option>
              {checklists.map((checklist) => (
                <option key={checklist.id} value={checklist.id}>
                  {checklist.title} ({checklist.items.length} item{checklist.items.length === 1 ? "" : "s"})
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
    </details>
  );
}

function ChecklistEditor({ checklists, activeId, busy, onSave, onDelete, onSelect }) {
  const active = checklists.find((item) => String(item.id) === String(activeId)) || null;
  const [title, setTitle] = useState(active?.title || "");
  const [text, setText] = useState(checklistItemsToText(active?.items || []));

  useEffect(() => {
    setTitle(active?.title || "");
    setText(checklistItemsToText(active?.items || []));
  }, [active?.id]);

  return (
    <details className="gym-checklist-editor">
      <summary>
        <ListChecks size={16} /> Your checklists
      </summary>
      <div className="gym-checks-body">
        <p className="muted">
          Write one review question per line. An item may need to look something up — the case record, an authority,
          a passage of the brief — and the run reports what it read before answering.
        </p>
        <label className="form-label">
          Checklist
          <select className="form-select" value={activeId || ""} onChange={(event) => onSelect(event.target.value)}>
            <option value="">New checklist…</option>
            {checklists.map((checklist) => (
              <option key={checklist.id} value={checklist.id}>
                {checklist.title}
              </option>
            ))}
          </select>
        </label>
        <label className="form-label">
          Name
          <input className="form-control" value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label className="form-label">
          Items
          <textarea
            className="form-control"
            rows={6}
            placeholder={"Every date in the statement of facts appears in a document in the file.\nEach authority cited is still good law."}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </label>
        <div className="button-row compact">
          <button
            className="btn btn-primary"
            type="button"
            disabled={busy || !title.trim()}
            onClick={() => onSave({ id: active?.id, title: title.trim(), items: checklistItemsFromText(text) })}
          >
            {busy ? <Loader2 className="spin" size={16} /> : <ListChecks size={16} />} {active ? "Save" : "Create"}
          </button>
          {active && (
            <button className="btn btn-outline-secondary" type="button" disabled={busy} onClick={() => onDelete(active.id)}>
              <X size={16} /> Delete
            </button>
          )}
        </div>
      </div>
    </details>
  );
}

function CheckFindings({ run }) {
  const groups = findingsByCheck(run.checkResults, run.checksRun);
  const counts = findingCounts(groups);
  const unavailable = checksByStatus(run.checksRun, "unavailable");
  const off = checksByStatus(run.checksRun, "off");
  if (!groups.length && !unavailable.length && !off.length) return null;
  return (
    <section className="gym-check-findings">
      <h4>
        <ListChecks size={16} /> Checks
      </h4>
      <p className="muted">{checkStatusSummary(run.checksRun)}</p>
      {(counts.errors > 0 || counts.warnings > 0) && (
        <p className={counts.errors ? "gym-compliance-bad" : "muted"}>
          {counts.errors} error{counts.errors === 1 ? "" : "s"}, {counts.warnings} warning
          {counts.warnings === 1 ? "" : "s"}, {counts.infos} note{counts.infos === 1 ? "" : "s"}.
        </p>
      )}
      {groups.map((group) => (
        <details key={group.id} className="gym-check-result" open={group.errors.length > 0}>
          <summary>
            {group.label}
            <span className="muted">
              {group.findings.length === 0 ? " no findings" : ` ${group.findings.length} finding(s)`}
            </span>
          </summary>
          {group.summary && <p className="muted">{group.summary}</p>}
          {group.findings.length === 0 ? (
            <p className="muted">This check ran and found nothing.</p>
          ) : (
            <ul className="gym-source-list">
              {group.findings.map((finding) => (
                <li key={finding.findingId} className={`gym-finding gym-finding-${finding.severity}`}>
                  <strong>{finding.target}</strong>
                  <p className="gym-source-snippet">{finding.message}</p>
                  {finding.details?.excerpt && <blockquote className="gym-quote">{finding.details.excerpt}</blockquote>}
                </li>
              ))}
            </ul>
          )}
        </details>
      ))}
      {unavailable.length > 0 && (
        <div className="gym-check-unavailable">
          <strong>Could not run — this is not a pass:</strong>
          <ul>
            {unavailable.map((entry) => (
              <li key={entry.id}>
                {entry.label}. {entry.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
      {off.length > 0 && (
        <p className="muted">Turned off for this session: {off.map((entry) => entry.label).join(", ")}.</p>
      )}
    </section>
  );
}

function RuleAudit({ ruleAudit = [] }) {
  if (!ruleAudit.length) return null;
  const unverified = unverifiedRules(ruleAudit);
  return (
    <section className="gym-rule-audit">
      <h4>
        <Scale size={16} /> Rules the brief invoked
      </h4>
      <p className="muted">{ruleAuditSummary(ruleAudit)}</p>
      {unverified.length > 0 && (
        <p className="muted">
          Element lists for {unverified.join(", ")} are unverified starting points. Read the rule before relying on a
          clean result.
        </p>
      )}
      {ruleAudit.map((audit) => (
        <details key={audit.slug} className="gym-rule" open={audit.unmetCount > 0}>
          <summary>
            <strong>{audit.label}</strong>
            <span className="muted"> {audit.verdict}</span>
          </summary>
          <p className="muted">
            Invoked by {audit.invokedBy === "citation" ? "a citation" : "a phrase, without citing the rule"}: “
            {audit.matched}”.
          </p>
          <ul className="gym-source-list">
            {audit.elements.map((element) => (
              <li key={element.id} className={element.unmet ? "gym-element-unmet" : "gym-element-met"}>
                <strong>{element.label}</strong>
                <span className="muted"> — {elementState(element)}</span>
                {element.origin === "decision_table" && <span className="gym-check-kind">from decision table</span>}
                {element.explanation && <p className="gym-source-snippet">{element.explanation}</p>}
                {element.quote && <blockquote className="gym-quote">{element.quote}</blockquote>}
              </li>
            ))}
          </ul>
        </details>
      ))}
    </section>
  );
}

function ChecklistResults({ results }) {
  const items = results?.results || [];
  if (!items.length) return null;
  return (
    <section className="gym-checklist-results">
      <h4>
        <ListChecks size={16} /> {results.title || "Your checklist"}
      </h4>
      <p className="muted">{checklistSummary(results)}</p>
      <ul className="gym-source-list">
        {items.map((item) => (
          <li key={item.itemId} className={`gym-checklist-${item.outcome}`}>
            <strong>{item.item}</strong>
            <span className="muted"> — {item.outcome.replace("_", " ")}</span>
            <p className="gym-source-snippet">{item.finding}</p>
            {item.suggestion && <p className="gym-source-snippet">Suggested: {item.suggestion}</p>}
            {item.lookups?.length > 0 && (
              <p className="muted">
                Looked up: {item.lookups.map((lookup) => `${lookup.tool.replace(/_/g, " ")} (${lookup.query})`).join("; ")}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function SourceList({ sources = [], emptyLabel }) {
  if (!sources.length) return <p className="muted">{emptyLabel}</p>;
  return (
    <ul className="gym-source-list">
      {sources.map((source, index) => (
        <li key={`${source.externalId || source.title}-${index}`}>
          <strong>{source.citation || source.title}</strong>
          {source.sourceLabel && <span className="muted"> · {source.sourceLabel}</span>}
          {source.snippet && <p className="gym-source-snippet">{source.snippet}</p>}
          {source.url && (
            <a href={source.url} target="_blank" rel="noreferrer">
              Open source
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}

function RecordList({ sources = [] }) {
  if (!sources.length) return <p className="muted">No case material was matched to this challenge.</p>;
  return (
    <ul className="gym-source-list">
      {sources.map((source) => (
        <li key={source.materialId}>
          <strong>{source.title}</strong>
          {source.status && <span className="muted"> · {source.status.replace("_", " ")}</span>}
          {source.quote && <p className="gym-source-snippet">“{source.quote}”</p>}
        </li>
      ))}
    </ul>
  );
}

function ChallengeCard({ challenge, busy, queued, onDisposition, onResearch, onQueueRevision, onCopy }) {
  const target = targetLabel(challenge.target);
  return (
    <article className={`gym-challenge gym-severity-${challenge.severity} gym-${challenge.disposition}`}>
      <header className="gym-challenge-header">
        <span className="gym-category">{challenge.categoryLabel}</span>
        <span className="gym-severity">{challenge.severity} severity</span>
        <span className="muted">confidence: {challenge.confidence}</span>
        {challenge.disposition !== "open" && <span className="gym-disposition">{challenge.disposition}</span>}
        {challenge.recurring && (
          <span className="gym-recurring" title="This challenge was raised in an earlier run too">
            raised again{challenge.previousDisposition === "addressed" ? " after being marked addressed" : ""}
          </span>
        )}
      </header>

      <h4>{challenge.opponentArgument}</h4>
      {target && <p className="gym-target">Targets {target}</p>}
      {challenge.whyItMatters && (
        <p className="gym-why">
          <strong>Why it matters.</strong> {challenge.whyItMatters}
        </p>
      )}

      <div className="gym-challenge-grid">
        <section>
          <h5>Legal support</h5>
          <SourceList sources={challenge.legalSources} emptyLabel="No retrieved authority backs this yet." />
        </section>
        <section>
          <h5>Case-record support or conflict</h5>
          <RecordList sources={challenge.recordSources} />
        </section>
        <section>
          <h5>What the brief currently says</h5>
          {challenge.briefCurrentlySays ? (
            <blockquote className="gym-quote">{challenge.briefCurrentlySays}</blockquote>
          ) : (
            <p className="muted">The brief does not address this point.</p>
          )}
        </section>
        <section>
          <h5>Judge assessment</h5>
          <p>
            {challenge.judgeVerdict && <span className="gym-verdict">{challenge.judgeVerdict}. </span>}
            {challenge.judgeAssessment || "No assessment was recorded."}
          </p>
        </section>
      </div>

      {(challenge.suggestedResponse || challenge.recommendation) && (
        <section className="gym-suggested">
          <h5>Suggested response</h5>
          {challenge.recommendation && <p>{challenge.recommendation}</p>}
          {challenge.suggestedResponse && <blockquote className="gym-quote">{challenge.suggestedResponse}</blockquote>}
        </section>
      )}

      <p className="gym-coverage muted">{coverageSummary(challenge.researchCoverage)}</p>
      {challenge.researchCoverage?.remainingVulnerability && (
        <p className="gym-remaining">
          <AlertTriangle size={14} /> Still exposed: {challenge.researchCoverage.remainingVulnerability}
        </p>
      )}

      <div className="button-row compact">
        <button className="btn btn-outline-secondary" type="button" disabled={busy} onClick={() => onResearch(challenge)}>
          {busy ? <Loader2 className="spin" size={16} /> : <Search size={16} />} Research further
        </button>
        {challenge.target?.blockKey && (
          <button
            className={`btn ${queued ? "btn-primary" : "btn-outline-secondary"}`}
            type="button"
            onClick={() => onQueueRevision(challenge)}
          >
            {queued ? <Check size={16} /> : <FileText size={16} />} {queued ? "In revision plan" : "Add to revision plan"}
          </button>
        )}
        <button className="btn btn-outline-secondary" type="button" onClick={() => onCopy(challenge)}>
          <ClipboardCopy size={16} /> Copy suggested response
        </button>
        <button
          className="btn btn-outline-secondary"
          type="button"
          disabled={busy}
          onClick={() => onDisposition(challenge, challenge.disposition === "addressed" ? "open" : "addressed")}
        >
          <Check size={16} /> {challenge.disposition === "addressed" ? "Reopen" : "Mark addressed"}
        </button>
        <button
          className="btn btn-outline-secondary"
          type="button"
          disabled={busy}
          onClick={() => onDisposition(challenge, challenge.disposition === "dismissed" ? "open" : "dismissed")}
        >
          <X size={16} /> {challenge.disposition === "dismissed" ? "Undismiss" : "Dismiss"}
        </button>
      </div>
    </article>
  );
}

function MaterialsConsidered({ run, materials, onToggle, busy }) {
  const considered = materialsByOrigin(run?.materials || []);
  return (
    <details className="gym-materials">
      <summary>
        <FolderOpen size={16} /> Materials considered ({(run?.materials || []).length})
      </summary>
      {(run?.materials || []).length === 0 ? (
        <p className="muted">This run tested the legal argument only. No case record was read.</p>
      ) : (
        <ul className="gym-source-list">
          {[...considered.matter_document, ...considered.upload].map((material) => (
            <li key={material.id}>
              <strong>{material.title}</strong>
              <span className="muted"> · {material.origin === "upload" ? "uploaded" : "case file"}</span>
              {material.reason && <p className="gym-source-snippet">{material.reason}</p>}
            </li>
          ))}
        </ul>
      )}
      {materials.length > 0 && (
        <>
          <h5>Available case materials</h5>
          <p className="muted">Uncheck a document to leave it out of the next run. Nothing is copied into the gym.</p>
          <ul className="gym-material-toggles">
            {materials.map((material) => (
              <li key={material.id}>
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={!material.excluded}
                    disabled={busy}
                    onChange={(event) => onToggle(material, !event.target.checked)}
                  />
                  <span>{material.title}</span>
                  <span className="muted">{material.origin === "upload" ? "uploaded" : "case file"}</span>
                </label>
              </li>
            ))}
          </ul>
        </>
      )}
    </details>
  );
}

function ArtifactModal({ artifact, onClose }) {
  const dialogRef = useRef(null);
  useModalDismiss(dialogRef, onClose, { active: Boolean(artifact) });
  if (!artifact) return null;
  const isPrepSheet = artifact.kind === "opposition_prep_sheet";
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="editor-modal gym-artifact-modal" ref={dialogRef} role="dialog" aria-modal="true" aria-label={artifact.title}>
        <div className="modal-heading">
          <h4>{artifact.title}</h4>
          <div className="button-row compact">
            <button className="btn btn-outline-secondary" type="button" onClick={() => window.print()}>
              <Printer size={16} /> Print
            </button>
            <button className="btn btn-outline-secondary icon-button" type="button" onClick={onClose} aria-label="Close">
              <X size={16} />
            </button>
          </div>
        </div>
        {artifact.assessment && (
          <div className="gym-artifact-assessment">
            {artifact.verdict && <h5><Gavel size={16} /> {artifact.verdict}</h5>}
            <p>{artifact.assessment}</p>
          </div>
        )}
        {(artifact.summary || artifact.executiveSummary) && (
          <div className="gym-artifact-summary">{artifact.summary || artifact.executiveSummary}</div>
        )}
        {artifact.compliance?.checked && (
          <p className="muted">Filing format: {complianceSummary(artifact.compliance)}</p>
        )}
        {isPrepSheet ? (
          <div className="gym-table-scroll">
            <table className="table gym-prep-sheet">
              <thead>
                <tr>
                  <th>Likely opposition point</th>
                  <th>Strongest authority</th>
                  <th>Strongest adverse record</th>
                  <th>Current response</th>
                  <th>Suggested response</th>
                  <th>Remaining vulnerability</th>
                </tr>
              </thead>
              <tbody>
                {artifact.rows.map((row) => (
                  <tr key={row.challengeId}>
                    <td>
                      <strong>{row.category}</strong>
                      <p>{row.likelyOppositionPoint}</p>
                      <span className="muted">{targetLabel(row.target)}</span>
                    </td>
                    <td>{row.strongestAuthority?.citation || row.strongestAuthority?.title || "—"}</td>
                    <td>{row.strongestAdverseRecord?.title || "—"}</td>
                    <td>{row.currentResponse || "—"}</td>
                    <td>{row.suggestedResponse || "—"}</td>
                    <td>{row.remainingVulnerability || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="gym-report">
            <h5>Ranked vulnerabilities</h5>
            {artifact.vulnerabilities.length === 0 ? (
              <p className="muted">Nothing is still open.</p>
            ) : (
              <ol>
                {artifact.vulnerabilities.map((item) => (
                  <li key={item.challengeId}>
                    <strong>{item.category}</strong> ({item.severity}) — {item.argument}
                    {item.recommendation && <p className="muted">{item.recommendation}</p>}
                  </li>
                ))}
              </ol>
            )}
            <h5>Challenges already handled well</h5>
            {artifact.handledWell.length === 0 ? (
              <p className="muted">None yet.</p>
            ) : (
              <ul>
                {artifact.handledWell.map((item) => (
                  <li key={item.challengeId}>
                    <strong>{item.category}</strong> — {item.argument}
                  </li>
                ))}
              </ul>
            )}
            <h5>Unresolved research gaps</h5>
            {artifact.researchGaps.length === 0 && artifact.unresolvedNotes.length === 0 ? (
              <p className="muted">The adversarial research covered every challenge raised.</p>
            ) : (
              <ul>
                {artifact.researchGaps.map((gap) => (
                  <li key={gap}>{gap}</li>
                ))}
                {artifact.unresolvedNotes.map((note) => (
                  <li key={note.challengeId}>{note.note}</li>
                ))}
              </ul>
            )}
            <h5>Materials reviewed</h5>
            {artifact.materialsReviewed.length === 0 ? (
              <p className="muted">No case record was read.</p>
            ) : (
              <ul>
                {artifact.materialsReviewed.map((material) => (
                  <li key={material.id}>{material.title}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function GymRevisionModal({ plan, busy, onClose, onUpdateItem, onApply }) {
  const dialogRef = useRef(null);
  useModalDismiss(dialogRef, onClose, { active: Boolean(plan) });
  if (!plan) return null;
  const items = plan.plan || [];
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="editor-modal revision-plan-modal" ref={dialogRef} role="dialog" aria-modal="true" aria-label="Gym revision plan">
        <div className="modal-heading">
          <h4>
            <Swords size={16} /> Revision plan from challenges
          </h4>
          <button className="btn btn-outline-secondary icon-button" type="button" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>
        <p className="muted">
          Nothing is edited until you apply this. Each instruction regenerates one block and is recorded as a reviewable
          change on the document.
        </p>
        {items.length === 0 && <div className="empty-state compact"><p>No selected challenge targets a block of this document.</p></div>}
        <div className="revision-plan-list">
          {items.map((item) => (
            <div className={`revision-plan-item ${item.include ? "" : "excluded"}`} key={item.blockKey}>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={item.include}
                  onChange={(event) => onUpdateItem(item.blockKey, { include: event.target.checked })}
                />
                <strong>{item.sectionLabel}</strong>
                <span className="muted">
                  {item.challengeIds.length} challenge{item.challengeIds.length === 1 ? "" : "s"}
                </span>
              </label>
              <textarea
                className="form-control"
                rows={5}
                value={item.instruction}
                disabled={!item.include}
                onChange={(event) => onUpdateItem(item.blockKey, { instruction: event.target.value })}
              />
            </div>
          ))}
        </div>
        {plan.copyOnly?.length > 0 && (
          <div className="revision-plan-unscoped">
            <strong>Not tied to a block — copy these into the brief yourself:</strong>
            <ul>
              {plan.copyOnly.map((item) => (
                <li key={item.challengeId}>{item.instruction}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="button-row step-actions">
          <button className="btn btn-outline-secondary" type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" type="button" disabled={busy || items.length === 0} onClick={onApply}>
            {busy ? <Loader2 className="spin" size={16} /> : <Swords size={16} />} Apply to draft
          </button>
        </div>
      </div>
    </div>
  );
}

export function ArgumentGymPanel({ matter = null, cases = [], focusRun = null, onFocusRunHandled = () => {} }) {
  const [workspace, setWorkspace] = useState(null);
  const [brief, setBrief] = useState(null);
  const [caseContext, setCaseContext] = useState(matter ? "existing_case" : "none");
  const [caseMaterials, setCaseMaterials] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [selectedMatterId, setSelectedMatterId] = useState(matter?.id || "");
  const [run, setRun] = useState(null);
  const [filter, setFilter] = useState("open");
  const [queued, setQueued] = useState([]);
  const [plan, setPlan] = useState(null);
  const [artifact, setArtifact] = useState(null);
  const [busy, setBusy] = useState(false);
  const [busyChallengeId, setBusyChallengeId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [sessions, setSessions] = useState([]);
  const [sessionMatters, setSessionMatters] = useState([]);
  const [sessionMatterId, setSessionMatterId] = useState("");
  const [sessionQuery, setSessionQuery] = useState("");
  const [courts, setCourts] = useState([]);
  const [courtTypes, setCourtTypes] = useState([]);
  const [detection, setDetection] = useState(null);
  const [uploadNote, setUploadNote] = useState("");
  const [checkCatalog, setCheckCatalog] = useState([]);
  const [checkDefaults, setCheckDefaults] = useState([]);
  const [checklists, setChecklists] = useState([]);
  const [editingChecklistId, setEditingChecklistId] = useState("");

  const loadSessions = useCallback(async ({ matterId = sessionMatterId, query = sessionQuery } = {}) => {
    try {
      const response = await api.gymWorkspaces({ matterId, query });
      setSessions(response.workspaces || []);
      setSessionMatters(response.matters || []);
    } catch (err) {
      setError(err.message);
    }
  }, [sessionMatterId, sessionQuery]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const loadChecklists = useCallback(async () => {
    try {
      const response = await api.gymChecklists();
      setChecklists(response.checklists || []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    loadChecklists();
    api
      .gymChecks()
      .then((response) => {
        setCheckCatalog(response.checks || []);
        setCheckDefaults(response.defaults || []);
      })
      .catch((err) => setError(err.message));
  }, [loadChecklists]);

  useEffect(() => {
    api
      .gymCourts()
      .then((response) => {
        setCourts(response.courts || []);
        setCourtTypes(response.courtTypes || []);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!focusRun) return;
    setWorkspace(focusRun.workspace);
    setRun(focusRun.run);
    setBrief({ id: focusRun.run.briefId, title: focusRun.run.briefTitle });
    setCaseContext("existing_case");
    setFilter("open");
    loadSessions();
    onFocusRunHandled();
  }, [focusRun, onFocusRunHandled, loadSessions]);

  const loadMaterials = useCallback(async (workspaceId) => {
    if (!workspaceId) return;
    try {
      const response = await api.gymMaterials(workspaceId);
      setMaterials(response.materials || []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    if (workspace?.id) loadMaterials(workspace.id);
  }, [workspace?.id, loadMaterials]);

  const ensureWorkspace = useCallback(async () => {
    if (workspace) return workspace;
    const response = await api.createGymWorkspace({
      title: "Argument gym",
      matterId: caseContext === "existing_case" ? selectedMatterId : "",
      jurisdiction: matter?.jurisdiction || "",
    });
    setWorkspace(response.workspace);
    return response.workspace;
  }, [workspace, caseContext, selectedMatterId, matter]);

  const openSession = async (session) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await api.gymWorkspace(session.id);
      setWorkspace(response.workspace);
      setRun(response.latestRun);
      setDetection(null);
      setQueued([]);
      setFilter("open");
      const briefDocument = (response.workspace.documents || []).find((item) => item.role === "brief_under_test");
      setBrief(briefDocument || null);
      setCaseMaterials((response.workspace.documents || []).filter((item) => item.role === "case_record"));
      setCaseContext(response.workspace.matterId ? "existing_case" : "none");
      setSelectedMatterId(response.workspace.matterId || "");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const startNewSession = () => {
    setWorkspace(null);
    setRun(null);
    setBrief(null);
    setCaseMaterials([]);
    setMaterials([]);
    setDetection(null);
    setQueued([]);
    setUploadNote("");
    setError("");
    setNotice("");
    setCaseContext(matter ? "existing_case" : "none");
    setSelectedMatterId(matter?.id || "");
  };

  const patchWorkspace = async (payload) => {
    setBusy(true);
    setError("");
    try {
      const target = await ensureWorkspace();
      const response = await api.updateGymWorkspace(target.id, payload);
      setWorkspace(response.workspace);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const selectedChecks = effectiveSelection(workspace?.enabledChecks ?? null, checkCatalog, checkDefaults);

  const changeChecks = async (checkId) => {
    await patchWorkspace({ enabledChecks: toggleCheck(selectedChecks, checkId) });
  };

  const saveChecklist = async ({ id, title, items }) => {
    setBusy(true);
    setError("");
    try {
      const response = id
        ? await api.updateGymChecklist(id, { title, items })
        : await api.createGymChecklist({ title, items });
      await loadChecklists();
      setEditingChecklistId(String(response.checklist.id));
      setNotice(`Saved “${response.checklist.title}”.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const removeChecklist = async (id) => {
    setBusy(true);
    try {
      await api.deleteGymChecklist(id);
      setEditingChecklistId("");
      await loadChecklists();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const previewDetection = async () => {
    setBusy(true);
    try {
      const target = await ensureWorkspace();
      const response = await api.gymCourtDetection(target.id);
      setDetection(response.detection);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const uploadDocument = async (file, role) => {
    setError("");
    setBusy(true);
    try {
      const target = await ensureWorkspace();
      const formData = new FormData();
      formData.append("file", file);
      formData.append("role", role);
      const response = await api.uploadGymDocument(target.id, formData);
      if (role === "brief_under_test") {
        setBrief(response.document);
        setUploadNote(
          [exhibitSummary(response.document), truncationNotice(response.document)].filter(Boolean).join(" "),
        );
        if ((response.exhibits || []).length) {
          setCaseMaterials((current) => [...current, ...response.exhibits]);
        }
      } else {
        setCaseMaterials((current) => [...current, response.document]);
      }
      await loadMaterials(target.id);
      await loadSessions();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const startRun = async () => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      let target = await ensureWorkspace();
      const wantedMatterId = caseContext === "existing_case" ? selectedMatterId : "";
      if ((target.matterId || "") !== wantedMatterId) {
        const updated = await api.updateGymWorkspace(target.id, { matterId: wantedMatterId });
        target = updated.workspace;
        setWorkspace(target);
      }
      const response = await api.runArgumentGym(target.id, { briefId: brief?.id });
      setRun(response.run);
      setQueued([]);
      setFilter("open");
      await loadMaterials(target.id);
      await loadSessions();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const setDisposition = async (challenge, disposition) => {
    setBusyChallengeId(challenge.id);
    try {
      const response = await api.setChallengeDisposition(challenge.id, { disposition });
      setRun((current) => ({ ...current, challenges: replaceChallenge(current.challenges, response.challenge) }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyChallengeId(null);
    }
  };

  const researchChallenge = async (challenge) => {
    setBusyChallengeId(challenge.id);
    setNotice("");
    try {
      const response = await api.researchChallenge(challenge.id);
      setRun((current) => ({ ...current, challenges: replaceChallenge(current.challenges, response.challenge) }));
      setNotice(
        response.addedSourceCount
          ? `Added ${response.addedSourceCount} source${response.addedSourceCount === 1 ? "" : "s"} to this challenge.`
          : "That search found nothing this challenge does not already cite.",
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyChallengeId(null);
    }
  };

  const copyChallenge = async (challenge) => {
    const text = copyTextForChallenge(challenge);
    try {
      await navigator.clipboard.writeText(text);
      setNotice("Suggested response copied.");
    } catch {
      setNotice("Copying is blocked in this browser. Select the suggested response text instead.");
    }
  };

  const openRevisionPlan = async () => {
    setBusy(true);
    setError("");
    try {
      const response = await api.gymRevisionPlan(run.id, queued);
      setPlan(response.revisionPlan);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const applyPlan = async () => {
    setBusy(true);
    try {
      const response = await api.applyGymRevision(run.id, { plan: plan.plan });
      setRun(response.run);
      setPlan(null);
      setQueued([]);
      setNotice("The draft was revised. Review the changes in the editor's document history.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const openArtifact = async (kind) => {
    setBusy(true);
    try {
      const response = await api.gymArtifact(run.id, kind);
      setArtifact(response.artifact);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleMaterial = async (material, excluded) => {
    setBusy(true);
    try {
      const response = await api.setGymMaterialExcluded(workspace.id, { materialId: material.id, excluded });
      setMaterials(response.materials || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const challenges = run?.challenges || [];
  const visible = useMemo(() => rankedChallenges(challenges, { filter }), [challenges, filter]);
  const readiness = canStartRun({
    briefDocument: brief,
    caseContext,
    caseMaterials,
    matterId: selectedMatterId,
  });
  const { canRevise } = revisionTargets(challenges, queued);

  return (
    <section className="panel gym-panel">
      <div className="panel-heading">
        <h3>
          <Swords size={18} /> Argument gym
        </h3>
        <p className="muted">
          An opponent attacks the brief, a judge weighs the attacks, and a coach proposes answers. Nothing here edits
          your document.
        </p>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}
      {notice && <div className="alert alert-info">{notice}</div>}

      <div className="gym-layout">
        <SessionList
          sessions={sessions}
          matters={sessionMatters}
          matterId={sessionMatterId}
          onMatterChange={(value) => {
            setSessionMatterId(value);
            loadSessions({ matterId: value });
          }}
          query={sessionQuery}
          onQueryChange={(value) => {
            setSessionQuery(value);
            loadSessions({ query: value });
          }}
          activeId={workspace?.id ?? null}
          onOpen={openSession}
          onNew={startNewSession}
          busy={busy}
        />

        <div className="gym-main">

      {!run && (
        <div className="gym-setup">
          <section>
            <h4>1. Brief under test</h4>
            {brief ? (
              <>
                <p>
                  <FileText size={16} /> {brief.title}
                  {brief.unitCount ? <span className="muted"> · {brief.unitCount} addressable passages</span> : null}
                  {brief.pleadingType ? <span className="muted"> · read as a {brief.pleadingType.replace("_", " ")}</span> : null}
                </p>
                {uploadNote && <p className="muted gym-split-note">{uploadNote}</p>}
              </>
            ) : (
              <label className="btn btn-outline-secondary gym-upload">
                <Upload size={16} /> Upload a brief (PDF, DOCX, or text)
                <input
                  type="file"
                  accept=".pdf,.docx,.txt,.md"
                  hidden
                  onChange={(event) => event.target.files?.[0] && uploadDocument(event.target.files[0], "brief_under_test")}
                />
              </label>
            )}
          </section>

          <section>
            <h4>2. Case context</h4>
            <div className="gym-context-choices">
              {CASE_CONTEXT_CHOICES.map((choice) => (
                <label key={choice.id} className={`gym-context-choice ${caseContext === choice.id ? "active" : ""}`}>
                  <input
                    type="radio"
                    name="gym-case-context"
                    value={choice.id}
                    checked={caseContext === choice.id}
                    onChange={() => setCaseContext(choice.id)}
                  />
                  <strong>{choice.label}</strong>
                  <span className="muted">{choice.description}</span>
                </label>
              ))}
            </div>
            {caseContext === "existing_case" && (
              <label className="form-label">
                Case
                <select
                  className="form-select"
                  value={selectedMatterId}
                  onChange={(event) => setSelectedMatterId(event.target.value)}
                >
                  <option value="">Choose a case…</option>
                  {cases.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.clientName} — {item.id}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {caseContext === "uploaded" && (
              <>
                <ul className="gym-source-list">
                  {caseMaterials.map((document) => (
                    <li key={document.id}>{document.title}</li>
                  ))}
                </ul>
                <label className="btn btn-outline-secondary gym-upload">
                  <Upload size={16} /> Add a case document
                  <input
                    type="file"
                    accept=".pdf,.docx,.txt,.md"
                    hidden
                    onChange={(event) => event.target.files?.[0] && uploadDocument(event.target.files[0], "case_record")}
                  />
                </label>
              </>
            )}
          </section>

          <section>
            <h4>3. Checks to run</h4>
            <CheckSelector
              catalog={checkCatalog}
              defaults={checkDefaults}
              selected={selectedChecks}
              settings={workspace?.checkSettings}
              checklists={checklists}
              checklistId={workspace?.checklist?.id}
              busy={busy}
              onToggle={changeChecks}
              onSettings={(patch) => patchWorkspace({ checkSettings: patch })}
              onChecklist={(value) => patchWorkspace({ checklistId: value ? Number(value) : null })}
            />
            <ChecklistEditor
              checklists={checklists}
              activeId={editingChecklistId}
              busy={busy}
              onSelect={setEditingChecklistId}
              onSave={saveChecklist}
              onDelete={removeChecklist}
            />
          </section>

          <section>
            <h4>4. Jurisdiction and filing rules</h4>
            <JurisdictionControls
              workspace={workspace}
              courts={courts}
              courtTypes={courtTypes}
              detection={detection}
              busy={busy}
              onChange={patchWorkspace}
              onDetect={previewDetection}
            />
          </section>

          <div className="button-row step-actions">
            {!readiness.ready && <span className="muted">{readiness.reason}</span>}
            <button className="btn btn-primary" type="button" disabled={busy || !readiness.ready} onClick={startRun}>
              {busy ? <Loader2 className="spin" size={16} /> : <Swords size={16} />} Run the gym
            </button>
          </div>
        </div>
      )}

      {run && (
        <>
          {run.assessment && (
            <section className="gym-assessment">
              {run.verdict && <h4><Gavel size={16} /> {run.verdict}</h4>}
              <p>{run.assessment}</p>
            </section>
          )}

          <div className="gym-run-header">
            <div>
              <h4>{run.briefTitle}</h4>
              <p className="muted">{challengeSummary(challenges)}</p>
              <p className="muted">{coverageSummary(run.coverage)}</p>
              {rerunSummary(run.comparison) && <p className="muted">{rerunSummary(run.comparison)}</p>}
            </div>
            <div className="button-row compact">
              <button className="btn btn-outline-secondary" type="button" disabled={busy} onClick={() => openArtifact("prep_sheet")}>
                <BookOpen size={16} /> Opposition prep sheet
              </button>
              <button className="btn btn-outline-secondary" type="button" disabled={busy} onClick={() => openArtifact("report")}>
                <FileText size={16} /> Stress-test report
              </button>
              <button className="btn btn-outline-secondary" type="button" disabled={busy} onClick={startRun}>
                {busy ? <Loader2 className="spin" size={16} /> : <Swords size={16} />} Run again
              </button>
            </div>
          </div>

          <CheckFindings run={run} />

          <RuleAudit ruleAudit={run.ruleAudit} />

          <ChecklistResults results={run.checklistResults} />

          <CompliancePanel compliance={run.compliance} />

          <CheckSelector
            catalog={checkCatalog}
            defaults={checkDefaults}
            selected={selectedChecks}
            settings={workspace?.checkSettings}
            checklists={checklists}
            checklistId={workspace?.checklist?.id}
            busy={busy}
            onToggle={changeChecks}
            onSettings={(patch) => patchWorkspace({ checkSettings: patch })}
            onChecklist={(value) => patchWorkspace({ checklistId: value ? Number(value) : null })}
          />

          <JurisdictionControls
            workspace={workspace}
            courts={courts}
            courtTypes={courtTypes}
            detection={detection}
            busy={busy}
            onChange={patchWorkspace}
            onDetect={previewDetection}
          />

          <MaterialsConsidered run={run} materials={materials} onToggle={toggleMaterial} busy={busy} />

          <div className="gym-filter button-row compact">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`btn ${filter === item.id ? "btn-primary" : "btn-outline-secondary"}`}
                onClick={() => setFilter(item.id)}
              >
                {item.label}
              </button>
            ))}
            {queued.length > 0 && (
              <button className="btn btn-primary" type="button" disabled={busy || !canRevise} onClick={openRevisionPlan}>
                <FileText size={16} /> Open revision plan ({queued.length})
              </button>
            )}
          </div>

          {visible.length === 0 ? (
            <div className="empty-state compact">
              <p>Nothing to show under this filter.</p>
            </div>
          ) : (
            <div className="gym-challenge-list">
              {visible.map((challenge) => (
                <ChallengeCard
                  key={challenge.id}
                  challenge={challenge}
                  busy={busyChallengeId === challenge.id}
                  queued={queued.includes(challenge.id)}
                  onDisposition={setDisposition}
                  onResearch={researchChallenge}
                  onCopy={copyChallenge}
                  onQueueRevision={(item) =>
                    setQueued((current) =>
                      current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id],
                    )
                  }
                />
              ))}
            </div>
          )}
        </>
      )}

        </div>
      </div>

      <ArtifactModal artifact={artifact} onClose={() => setArtifact(null)} />
      <GymRevisionModal
        plan={plan}
        busy={busy}
        onClose={() => setPlan(null)}
        onUpdateItem={(blockKey, patch) => setPlan((current) => updatePlanItem(current, blockKey, patch))}
        onApply={applyPlan}
      />
    </section>
  );
}

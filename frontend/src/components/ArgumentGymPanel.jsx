import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
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
  Search,
  Swords,
  Upload,
  X,
} from "lucide-react";

import { api } from "../api/client.js";
import { useModalDismiss } from "../hooks/useModalDismiss.js";
import {
  COURT_RULE_MODES,
  JURISDICTION_MODES,
  RUN_POLL_MS,
  RUN_POLL_TIMEOUT_MS,
  auditBadges,
  availableFilters,
  canStartRun,
  caseOptions,
  challengeSummary,
  clamp,
  cleanJurisdictionDetail,
  complianceGroups,
  complianceSummary,
  copyTextForChallenge,
  courtSummary,
  coverageSummary,
  defaultFilter,
  effectiveSelection,
  elementState,
  emptyStateMessage,
  evidenceCount,
  exhibitSummary,
  findingsByCheck,
  isRunFinished,
  materialsByOrigin,
  matterFilterOptions,
  rankedChallenges,
  replaceChallenge,
  rerunSummary,
  responseBullets,
  revisionTargets,
  runActionsDisabled,
  runProgressFraction,
  runProgressLabel,
  runView,
  sessionStatus,
  sessionSubtitle,
  severityTone,
  shortTitle,
  skippedChecksSummary,
  sortSessions,
  targetLabel,
  toggleCheck,
  truncationNotice,
  updatePlanItem,
  usesMunicipality,
} from "./argumentGym.js";

function RunProgress({ run }) {
  return (
    <section className="gym-progress" role="status" aria-live="polite">
      <Loader2 className="spin" size={18} />
      <div>
        <strong>{runProgressLabel(run)}</strong>
        <p className="muted">
          A full pass takes a few minutes. You can leave this open, or come back to it from Open session — the run
          keeps going on the server.
        </p>
        <div className="gym-progress-track">
          <div className="gym-progress-bar" style={{ width: `${Math.round(runProgressFraction(run) * 100)}%` }} />
        </div>
      </div>
    </section>
  );
}

function RunFailed({ run, busy, onRetry, onBack }) {
  return (
    <section className="gym-run-failed">
      <h4>
        <AlertTriangle size={18} /> This run did not finish
      </h4>
      <p>{run.error || "The run failed before it produced any challenges."}</p>
      <p className="muted">Nothing was written to your document.</p>
      <div className="button-row compact">
        <button className="btn btn-primary" type="button" disabled={busy} onClick={onRetry}>
          {busy ? <Loader2 className="spin" size={16} /> : <Swords size={16} />} Try again
        </button>
        <button className="btn btn-outline-secondary" type="button" onClick={onBack}>
          Back to setup
        </button>
      </div>
    </section>
  );
}

function SessionBrowser({ open, sessions, matters, matterId, onMatterChange, query, onQueryChange, activeId, onOpen, onNew, onClose, busy }) {
  const dialogRef = useRef(null);
  useModalDismiss(dialogRef, onClose, { active: open });
  if (!open) return null;
  return (
    <div className="modal-backdrop" role="presentation">
      <aside className="editor-modal gym-sessions" ref={dialogRef} role="dialog" aria-modal="true" aria-label="Sessions">
      <div className="modal-heading">
        <h4>Open a session</h4>
        <div className="button-row compact">
          <button className="btn btn-primary" type="button" onClick={onNew} disabled={busy}>
            <Plus size={16} /> New session
          </button>
          <button className="btn btn-outline-secondary icon-button" type="button" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>
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
                <strong title={session.title}>{shortTitle(session.title, 60)}</strong>
                <span className="muted" title={sessionSubtitle(session)}>{shortTitle(sessionSubtitle(session), 70)}</span>
                <span className="muted">{sessionStatus(session)}</span>
                {session.verdict && <span className="gym-session-verdict">{session.verdict}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      </aside>
    </div>
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
    <div className="gym-jurisdiction">
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
    </div>
  );
}

function FindingLines({ findings }) {
  if (!findings.length) return <p className="muted">Nothing found.</p>;
  return (
    <ul className="gym-finding-lines">
      {findings.map((finding) => (
        <li key={finding.findingId} className={`tone-${finding.severity}`}>
          <span className="gym-finding-target">{finding.target}</span>
          {finding.message}
        </li>
      ))}
    </ul>
  );
}

function AuditSummary({ run, onOpenArtifact, actionsDisabled }) {
  const badges = auditBadges(run);
  const skipped = skippedChecksSummary(run.checksRun || []);
  const checkGroups = findingsByCheck(run.checkResults || {}, run.checksRun || []);
  const compliance = complianceGroups(run.compliance || {});
  const rules = run.ruleAudit || [];
  // Findings first; the rules that were satisfied are a list, not a report.
  const unmetRules = rules.filter((audit) => audit.unmetCount > 0);
  const metRules = rules.filter((audit) => !audit.unmetCount);
  const checklist = run.checklistResults?.results || [];

  return (
    <aside className="gym-audit">
      <h4>Audit</h4>
      {badges.length === 0 && <p className="muted">No technical checks ran.</p>}
      <ul className="gym-badges">
        {badges.map((badge) => (
          <li key={badge.id} className={`tone-${badge.tone}`}>
            <span className="gym-badge-count">{badge.count}</span>
            <span>
              {badge.label}
              {badge.note && <small>{badge.note}</small>}
            </span>
          </li>
        ))}
      </ul>

      {unmetRules.length > 0 && (
        <details className="gym-audit-detail">
          <summary>Unmet elements</summary>
          {unmetRules.map((audit) => (
            <div key={audit.slug} className="gym-audit-rule">
              <span className="gym-context-label">{audit.citation}</span>
              <ul className="gym-finding-lines">
                {audit.elements
                  .filter((element) => element.unmet)
                  .map((element) => (
                    <li key={element.id} className="tone-warning">
                      <span className="gym-finding-target">{element.label}</span>
                      {elementState(element)}
                    </li>
                  ))}
              </ul>
            </div>
          ))}
        </details>
      )}

      {metRules.length > 0 && (
        <details className="gym-audit-detail">
          <summary>Rules carried ({metRules.length})</summary>
          <ul className="gym-plain-list">
            {metRules.map((audit) => (
              <li key={audit.slug}>{audit.label}</li>
            ))}
          </ul>
        </details>
      )}

      {compliance.checked && compliance.total > 0 && (
        <details className="gym-audit-detail">
          <summary>Filing format</summary>
          <FindingLines findings={[...compliance.errors, ...compliance.warnings, ...compliance.unmeasured]} />
        </details>
      )}

      {checkGroups.some((group) => group.findings.length > 0) && (
        <details className="gym-audit-detail">
          <summary>Document checks</summary>
          {checkGroups
            .filter((group) => group.findings.length > 0)
            .map((group) => (
              <div key={group.id} className="gym-audit-rule">
                <span className="gym-context-label">{group.label}</span>
                <FindingLines findings={group.findings} />
              </div>
            ))}
        </details>
      )}

      {checklist.length > 0 && (
        <details className="gym-audit-detail">
          <summary>Your checklist</summary>
          <ul className="gym-finding-lines">
            {checklist.map((item) => (
              <li key={item.itemId} className={item.outcome === "fail" ? "tone-warning" : ""}>
                <span className="gym-finding-target">{item.item}</span>
                {item.finding}
              </li>
            ))}
          </ul>
        </details>
      )}

      {skipped && (
        <details className="gym-audit-detail gym-audit-skipped">
          <summary>
            Not run <span className="gym-badge-inline">{skipped.label}</span>
          </summary>
          <p className="muted">A check that did not run is not a pass.</p>
          <ul className="gym-plain-list">
            {skipped.unavailable.map((entry) => (
              <li key={entry.id}>
                {entry.label} — {entry.reason}
              </li>
            ))}
            {skipped.off.map((entry) => (
              <li key={entry.id} className="muted">
                {entry.label} — off
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="gym-audit-actions">
        <button className="btn-link" type="button" disabled={actionsDisabled} onClick={() => onOpenArtifact("prep_sheet")}>
          Opposition prep sheet
        </button>
        <button className="btn-link" type="button" disabled={actionsDisabled} onClick={() => onOpenArtifact("report")}>
          Stress-test report
        </button>
      </div>
    </aside>
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

function EvidenceModal({ challenge, onClose }) {
  const dialogRef = useRef(null);
  useModalDismiss(dialogRef, onClose, { active: Boolean(challenge) });
  if (!challenge) return null;
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="editor-modal gym-evidence-modal" ref={dialogRef} role="dialog" aria-modal="true" aria-label="Evidence">
        <div className="modal-heading">
          <h4>Evidence</h4>
          <button className="btn btn-outline-secondary icon-button" type="button" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>
        <section>
          <h5>Legal authority</h5>
          <SourceList sources={challenge.legalSources} emptyLabel="No retrieved authority backs this yet." />
        </section>
        <section>
          <h5>Case record</h5>
          <RecordList sources={challenge.recordSources} />
        </section>
        <section>
          <h5>Research coverage</h5>
          <p className="muted">{coverageSummary(challenge.researchCoverage)}</p>
        </section>
      </div>
    </div>
  );
}

function ChallengeCard({ challenge, busy, queued, onDisposition, onResearch, onQueueRevision, onCopy, onEvidence }) {
  const [expanded, setExpanded] = useState(false);
  const target = targetLabel(challenge.target);
  const evidence = evidenceCount(challenge);
  const bullets = responseBullets(challenge.suggestedResponse || challenge.recommendation);
  const verdict = clamp(challenge.judgeAssessment, 240);
  const remaining = challenge.researchCoverage?.remainingVulnerability;

  return (
    <article className={`gym-challenge tone-${severityTone(challenge)} gym-${challenge.disposition}`}>
      <header className="gym-challenge-header">
        <span className="gym-severity-dot" aria-hidden="true" />
        <span className="gym-category">{challenge.categoryLabel}</span>
        {target && <span className="gym-target">{target}</span>}
        <span className="gym-severity-word">{challenge.severity}</span>
        {challenge.disposition !== "open" && <span className="gym-disposition">{challenge.disposition}</span>}
        {challenge.recurring && <span className="gym-recurring">raised again</span>}
      </header>

      <p className="gym-claim">{challenge.opponentArgument}</p>

      {challenge.judgeAssessment && (
        <p className="gym-verdict-line">
          <span className="gym-verdict-label">{challenge.judgeVerdict || "assessment"}</span>
          {verdict.text}
        </p>
      )}

      {bullets.length > 0 && (
        <div className="gym-fix">
          <h5>Suggested fix</h5>
          {bullets.length === 1 ? (
            <p>{bullets[0]}</p>
          ) : (
            <ul>
              {bullets.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="gym-card-more">
        {evidence > 0 && (
          <button className="btn-link" type="button" onClick={() => onEvidence(challenge)}>
            Evidence ({evidence})
          </button>
        )}
        <button className="btn-link" type="button" onClick={() => setExpanded((open) => !open)}>
          {expanded ? "Less" : "Context"}
        </button>
        {remaining && <span className="gym-remaining">Still exposed: {remaining}</span>}
      </div>

      {expanded && (
        <div className="gym-card-context">
          {challenge.whyItMatters && (
            <p>
              <span className="gym-context-label">Why it matters</span>
              {challenge.whyItMatters}
            </p>
          )}
          {verdict.truncated && (
            <p>
              <span className="gym-context-label">Judge assessment</span>
              {challenge.judgeAssessment}
            </p>
          )}
          {challenge.briefCurrentlySays && (
            <blockquote className="gym-quote">{challenge.briefCurrentlySays}</blockquote>
          )}
          {challenge.suggestedResponse && challenge.recommendation && (
            <p>
              <span className="gym-context-label">Coaching</span>
              {challenge.recommendation}
            </p>
          )}
        </div>
      )}

      <div className="gym-card-actions">
        <button className="btn-quiet" type="button" disabled={busy} onClick={() => onResearch(challenge)}>
          {busy ? <Loader2 className="spin" size={14} /> : <Search size={14} />} Research
        </button>
        {challenge.target?.blockKey && (
          <button
            className={`btn-quiet${queued ? " active" : ""}`}
            type="button"
            onClick={() => onQueueRevision(challenge)}
          >
            {queued ? <Check size={14} /> : <FileText size={14} />} {queued ? "In plan" : "Add to plan"}
          </button>
        )}
        <button className="btn-quiet" type="button" onClick={() => onCopy(challenge)}>
          <ClipboardCopy size={14} /> Copy
        </button>
        <button
          className="btn-quiet"
          type="button"
          disabled={busy}
          onClick={() => onDisposition(challenge, challenge.disposition === "addressed" ? "open" : "addressed")}
        >
          <Check size={14} /> {challenge.disposition === "addressed" ? "Reopen" : "Addressed"}
        </button>
        <button
          className="btn-quiet"
          type="button"
          disabled={busy}
          onClick={() => onDisposition(challenge, challenge.disposition === "dismissed" ? "open" : "dismissed")}
        >
          <X size={14} /> {challenge.disposition === "dismissed" ? "Undismiss" : "Dismiss"}
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
  const [checklistModalOpen, setChecklistModalOpen] = useState(false);
  const [passiveModalOpen, setPassiveModalOpen] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [evidenceChallenge, setEvidenceChallenge] = useState(null);

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

  // The run is started, not awaited. It takes minutes -- longer than a worker
  // may hold a request -- so the server hands back a run to poll.
  const pollRun = useCallback(async (runId) => {
    const deadline = Date.now() + RUN_POLL_TIMEOUT_MS;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, RUN_POLL_MS));
      let latest;
      try {
        latest = (await api.gymRun(runId)).run;
      } catch (err) {
        // A single failed poll is a blip, not a failed run; keep waiting and let
        // the deadline decide.
        continue;
      }
      setRun(latest);
      if (isRunFinished(latest)) return latest;
    }
    setError("This run is taking longer than expected. It may still finish — reopen the session to check.");
    return null;
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
    // A stress test started from the editor is handed over still running, so it
    // has to be followed here just like one started in this panel.
    if (!isRunFinished(focusRun.run)) pollRun(focusRun.run.id);
  }, [focusRun, onFocusRunHandled, loadSessions, pollRun]);

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
    setSessionsOpen(false);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await api.gymWorkspace(session.id);
      setWorkspace(response.workspace);
      setRun(response.latestRun);
      setDetection(null);
      setQueued([]);
      setFilter(defaultFilter(response.latestRun?.challenges || []));
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
    setSessionsOpen(false);
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
      if (!isRunFinished(response.run)) {
        const finished = await pollRun(response.run.id);
        if (finished) setFilter(defaultFilter(finished.challenges || []));
      } else {
        setFilter(defaultFilter(response.run.challenges || []));
      }
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
  // A prep sheet built from half a run is worse than no prep sheet.
  const actionsDisabled = runActionsDisabled({ run, busy });
  const filters = availableFilters(challenges);
  // A run exists the moment it starts; results are a different thing.
  const view = runView(run);

  return (
    <section className="panel gym-panel">
      <div className="panel-heading gym-heading">
        <div>
          <h3>
            <Swords size={18} /> Argument gym
          </h3>
          <p className="muted">
            {workspace
              ? sessionSubtitle(workspace)
              : "An opponent attacks the brief, a judge weighs it, and a coach proposes answers. Nothing here edits your document."}
          </p>
        </div>
        <div className="button-row compact">
          <button className="btn btn-outline-secondary" type="button" onClick={() => setSessionsOpen(true)}>
            <FolderOpen size={16} /> Open session{sessions.length ? ` (${sessions.length})` : ""}
          </button>
          <button className="btn btn-outline-secondary" type="button" onClick={startNewSession} disabled={busy}>
            <Plus size={16} /> New
          </button>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}
      {notice && <div className="alert alert-info">{notice}</div>}

      <div className="gym-main">

      {view === "setup" && (
        <div className="gym-setup">
          <section>
            <h4>1. Brief under test</h4>
            {brief ? (
              <>
                <p className="gym-brief-name">
                  <FileText size={16} /> <span title={brief.title}>{shortTitle(brief.title)}</span>
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
                  {caseOptions(cases).map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
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

          <details className="gym-config">
            <summary>
              <ListChecks size={16} /> Checks to run
              <span className="muted">{selectedChecks.length} of {checkCatalog.length} selected</span>
            </summary>
            <CheckSelector
              catalog={checkCatalog}
              selected={selectedChecks}
              checklists={checklists}
              checklistId={workspace?.checklist?.id}
              busy={busy}
              onToggle={changeChecks}
              onChecklist={(value) => patchWorkspace({ checklistId: value ? Number(value) : null })}
              onManageChecklists={() => setChecklistModalOpen(true)}
              onManagePassive={() => setPassiveModalOpen(true)}
            />
          </details>

          <details className="gym-config">
            <summary>
              <Landmark size={16} /> Jurisdiction and filing rules
              <span className="muted">
                {workspace?.court?.label || (workspace?.courtRuleMode === "off" ? "off" : "detected from the brief")}
              </span>
            </summary>
            <JurisdictionControls
              workspace={workspace}
              courts={courts}
              courtTypes={courtTypes}
              detection={detection}
              busy={busy}
              onChange={patchWorkspace}
              onDetect={previewDetection}
            />
          </details>

          <div className="button-row step-actions">
            {!readiness.ready && <span className="muted">{readiness.reason}</span>}
            <button className="btn btn-primary" type="button" disabled={busy || !readiness.ready} onClick={startRun}>
              {busy ? <Loader2 className="spin" size={16} /> : <Swords size={16} />} Run the gym
            </button>
          </div>
        </div>
      )}

      {view === "running" && <RunProgress run={run} />}

      {view === "failed" && (
        <RunFailed
          run={run}
          busy={busy}
          onRetry={startRun}
          onBack={() => {
            setRun(null);
            setError("");
          }}
        />
      )}

      {view === "results" && (
        <>
          {/* One slim bar: what was tested, how it read, and the controls. */}
          <div className="gym-runbar">
            <div className="gym-runbar-text">
              <span className="gym-runbar-title" title={run.briefTitle}>{shortTitle(run.briefTitle, 40)}</span>
              <span className="muted">{challengeSummary(challenges)}</span>
              {rerunSummary(run.comparison) && <span className="muted">{rerunSummary(run.comparison)}</span>}
            </div>
            <button className="btn btn-outline-secondary" type="button" disabled={actionsDisabled} onClick={startRun}>
              {busy ? <Loader2 className="spin" size={16} /> : <Swords size={16} />} Run again
            </button>
          </div>

          {run.assessment && (
            <section className="gym-assessment">
              {run.verdict && <span className="gym-verdict-chip">{run.verdict}</span>}
              <p>{run.assessment}</p>
            </section>
          )}

          {(filters.length > 0 || queued.length > 0) && (
            <div className="gym-filter button-row compact">
              {filters.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`btn ${filter === item.id ? "btn-primary" : "btn-outline-secondary"}`}
                  onClick={() => setFilter(item.id)}
                >
                  {item.label} ({item.count})
                </button>
              ))}
              {queued.length > 0 && (
                <button
                  className="btn btn-primary gym-filter-action"
                  type="button"
                  disabled={actionsDisabled || !canRevise}
                  onClick={openRevisionPlan}
                >
                  <FileText size={16} /> Open revision plan ({queued.length})
                </button>
              )}
            </div>
          )}

          <div className="gym-results">
            <div className="gym-worklist">
              {visible.length === 0 ? (
                <div className="empty-state compact">
                  <p>{emptyStateMessage(challenges, filter)}</p>
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
                      onEvidence={setEvidenceChallenge}
                      onQueueRevision={(item) =>
                        setQueued((current) =>
                          current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id],
                        )
                      }
                    />
                  ))}
                </div>
              )}
            </div>
            <AuditSummary run={run} onOpenArtifact={openArtifact} actionsDisabled={actionsDisabled} />
          </div>

          <details className="gym-config">
            <summary>
              <ListChecks size={16} /> Checks and jurisdiction
              <span className="muted">change what the next run does</span>
            </summary>
            <CheckSelector
              catalog={checkCatalog}
              selected={selectedChecks}
              checklists={checklists}
              checklistId={workspace?.checklist?.id}
              busy={actionsDisabled}
              onToggle={changeChecks}
              onChecklist={(value) => patchWorkspace({ checklistId: value ? Number(value) : null })}
              onManageChecklists={() => setChecklistModalOpen(true)}
              onManagePassive={() => setPassiveModalOpen(true)}
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
          </details>

          <p className="muted gym-coverage-line">{coverageSummary(run.coverage)}</p>
          <MaterialsConsidered run={run} materials={materials} onToggle={toggleMaterial} busy={actionsDisabled} />
        </>
      )}

      </div>

      <SessionBrowser
        open={sessionsOpen}
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
        onClose={() => setSessionsOpen(false)}
        busy={busy}
      />
      <ChecklistModal
        open={checklistModalOpen}
        checklists={checklists}
        activeId={editingChecklistId}
        busy={busy}
        onClose={() => setChecklistModalOpen(false)}
        onSelect={setEditingChecklistId}
        onSave={saveChecklist}
        onDelete={removeChecklist}
      />
      <PassivePhraseModal
        open={passiveModalOpen}
        phrases={workspace?.checkSettings?.passive_voice?.acceptedPassivePhrases || []}
        busy={busy}
        onClose={() => setPassiveModalOpen(false)}
        onSave={async (phrases) => {
          await patchWorkspace({ checkSettings: { passive_voice: { acceptedPassivePhrases: phrases } } });
          setPassiveModalOpen(false);
        }}
      />
      <EvidenceModal challenge={evidenceChallenge} onClose={() => setEvidenceChallenge(null)} />
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

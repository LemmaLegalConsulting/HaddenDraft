import React from "react";
import { AlertOctagon, AlertTriangle, Info } from "lucide-react";

const SEVERITY_CONFIG = {
  error: { label: "Errors", Icon: AlertOctagon },
  warning: { label: "Warnings", Icon: AlertTriangle },
  info: { label: "Info", Icon: Info },
};

function sourceLabel(view) {
  if (view === "docx") return "Source: Word output";
  if (view === "both") return "Source: Draft JSON + Word output";
  return "Source: Draft JSON";
}

function FindingCard({ finding }) {
  const location = finding.location || {};
  const target = location.sectionLabel || location.blockKey || finding.target;
  return (
    <div className={`finding-card finding-${finding.severity}`}>
      <div className="finding-card-header">
        <span className="finding-rule-code">{finding.ruleCode}</span>
        {finding.category && <span className="finding-category">{finding.category}</span>}
        <span className="finding-source">{sourceLabel(location.view)}</span>
      </div>
      <p className="finding-message">{finding.message}</p>
      {target && <p className="finding-target">Target: {target}</p>}
      {location.excerpt && <pre className="finding-excerpt">{location.excerpt}</pre>}
      {finding.action?.label && <p className="finding-action">Recommended action: {finding.action.label}</p>}
    </div>
  );
}

export function ValidationPanel({ findings = [], summary = null }) {
  const errors = findings.filter((finding) => finding.severity === "error");
  const warnings = findings.filter((finding) => finding.severity === "warning");
  const infos = findings.filter((finding) => finding.severity === "info");

  if (!findings.length && !summary) return null;

  const repairedAttempts = summary?.attempts ? Math.max(summary.attempts.length - 1, 0) : 0;

  return (
    <div className="validation-panel">
      {summary?.autoRepaired && (
        <div className="validation-summary-banner">
          Validation regenerated {repairedAttempts} block{repairedAttempts === 1 ? "" : "s"}/document(s) and rechecked the
          Word output. Remaining: {summary.remainingErrorCount} error(s), {summary.warningCount} warning(s),{" "}
          {summary.infoCount} info.
        </div>
      )}
      {errors.length > 0 && (
        <div className="validation-blocking-warning">
          This draft still has blocking validation errors. Export is available for review, but this output should not be
          filed.
        </div>
      )}
      {[
        { key: "error", items: errors },
        { key: "warning", items: warnings },
        { key: "info", items: infos },
      ].map(({ key, items }) => {
        if (!items.length) return null;
        const { label, Icon } = SEVERITY_CONFIG[key];
        return (
          <div key={key} className={`finding-group finding-group-${key}`}>
            <h4>
              <Icon size={16} /> {label} ({items.length})
            </h4>
            <div className="finding-list">
              {items.map((finding) => (
                <FindingCard key={finding.findingId} finding={finding} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

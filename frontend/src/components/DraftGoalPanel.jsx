import React from "react";
import { FileText, Layers3, Loader2 } from "lucide-react";

export function DraftGoalPanel({
  goal,
  onGoalChange,
  planningMode,
  onPlanningModeChange,
  allowMultiple,
  onAllowMultipleChange,
  selectedTemplateId,
  onTemplateChange,
  templates,
  matter,
  busy,
  onMakePlan,
}) {
  const selectedTemplate = templates.find((template) => template.id === Number(selectedTemplateId));
  const canMakePlan = Boolean(matter) && (planningMode === "known" ? Boolean(selectedTemplateId) : Boolean(goal.trim()));

  return (
    <section className="panel">
      <div className="step-guidance">
        <span className="block-kicker">Drafting goal</span>
        <h3>What do you want to file or accomplish?</h3>
      </div>
      <label className="field">
        <span>{planningMode === "known" ? "Goal or extra instructions" : "Goal"}</span>
        <textarea
          className="form-control"
          value={goal}
          onChange={(event) => onGoalChange(event.target.value)}
          placeholder={planningMode === "known" && selectedTemplate ? `Optional. Default: make ${selectedTemplate.title}.` : "Example: Ask the court to continue the hearing so rental assistance can process."}
          rows={5}
        />
      </label>
      <div className="draft-mode-switch">
        <button className={planningMode === "suggest" ? "selected" : ""} type="button" onClick={() => onPlanningModeChange("suggest")}>
          <FileText size={16} /> Let AI suggest template(s)
        </button>
        <button className={planningMode === "known" ? "selected" : ""} type="button" onClick={() => onPlanningModeChange("known")}>
          <Layers3 size={16} /> I already know the template
        </button>
      </div>
      {planningMode === "known" && (
        <label className="field">
          <span>Template</span>
          <select value={selectedTemplateId || ""} onChange={(event) => onTemplateChange(event.target.value)}>
            {templates.filter((template) => template.kind !== "shell").map((template) => (
              <option key={template.id} value={template.id}>{template.title}</option>
            ))}
          </select>
        </label>
      )}
      <label className="checkbox-row">
        <input type="checkbox" checked={allowMultiple} onChange={(event) => onAllowMultipleChange(event.target.checked)} />
        <span>Create multiple simple documents if useful</span>
      </label>
      <div className="button-row step-actions">
        <button className="btn btn-primary" type="button" disabled={busy || !canMakePlan} onClick={onMakePlan}>
          {busy ? <Loader2 className="spin" size={16} /> : <FileText size={16} />} Make plan
        </button>
      </div>
    </section>
  );
}

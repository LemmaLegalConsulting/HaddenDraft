import React, { useMemo, useState } from "react";
import { CheckCircle2, ClipboardList, FileText, Loader2, Sparkles, UserRound } from "lucide-react";

import { AuthorFields } from "./AuthorFields.jsx";
import { CaseMaterialsPanel } from "./CaseMaterialsPanel.jsx";
import { DraftSupportReview } from "./DraftSupportReview.jsx";
import { FactReview } from "./FactReview.jsx";
import { LawReview } from "./LawReview.jsx";

function updateDocument(plan, documentId, patch) {
  return {
    ...plan,
    document_items: (plan.document_items || []).map((item) => (
      item.id === documentId ? { ...item, ...patch } : item
    )),
  };
}

export function DraftPlanReview({
  plan,
  templates,
  matter,
  session,
  busy,
  authorProfile,
  onAuthorProfileChange,
  selectedFactIds,
  selectedCuratedFacts,
  onFactChange,
  onCuratedChange,
  onMatterChange,
  selectedResults,
  onSelectedResultsChange,
  onSessionChange,
  candidateIssues,
  onIssuesChange,
  onFactIdsAdded,
  clarifyMissingFactsBeforeDraft,
  onClarifyMissingFactsBeforeDraftChange,
  onPlanChange,
  onRegeneratePlan,
  onGenerateDraft,
}) {
  const [openPanel, setOpenPanel] = useState("documents");
  const [guidance, setGuidance] = useState("");
  const templateBySlug = useMemo(() => new Map(templates.map((template) => [template.slug, template])), [templates]);
  const documentItems = plan?.document_items || [];
  const unansweredQuestions = documentItems.flatMap((item) => (
    (item.missing_information || [])
      .filter((missing) => !missing.answer && !missing.not_needed)
      .map((missing) => ({ ...missing, documentTitle: item.title }))
  ));
  const shouldPauseForQuestions = clarifyMissingFactsBeforeDraft && unansweredQuestions.length > 0;

  if (!plan) {
    return (
      <section className="panel">
        <div className="empty-state compact">
          <strong className="empty-state-title">No draft plan yet</strong>
          <p>Start with a goal to create a reviewable plan.</p>
        </div>
      </section>
    );
  }

  function updateMissing(documentItem, index, patch) {
    const missing = [...(documentItem.missing_information || [])];
    missing[index] = { ...missing[index], ...patch };
    onPlanChange(updateDocument(plan, documentItem.id, { missing_information: missing }));
  }

  return (
    <section className="step-screen">
      <div className="panel">
        <div className="step-guidance">
          <span className="block-kicker">Draft plan</span>
          <h3>{plan.summary || "Review the plan"}</h3>
        </div>
        <label className="field">
          <span>Overall goal</span>
          <textarea value={plan.summary || ""} onChange={(event) => onPlanChange({ ...plan, summary: event.target.value })} rows={3} />
        </label>
        <div className="plan-document-list">
          {documentItems.map((item) => {
            const template = templateBySlug.get(item.template_slug);
            const blocks = template?.blocks || [];
            const selected = new Set(item.selected_block_keys || []);
            return (
              <article className="result-card plan-document-card" key={item.id}>
                <label className="field compact-field">
                  <span>Document title</span>
                  <input value={item.title || ""} onChange={(event) => onPlanChange(updateDocument(plan, item.id, { title: event.target.value }))} />
                </label>
                <label className="field compact-field">
                  <span>Recommended template</span>
                  <select value={item.template_slug || ""} onChange={(event) => {
                    const nextTemplate = templateBySlug.get(event.target.value);
                    onPlanChange(updateDocument(plan, item.id, {
                      template_slug: event.target.value,
                      template_id: nextTemplate?.id,
                      title: item.title || nextTemplate?.title || "",
                      selected_block_keys: nextTemplate?.blocks?.filter((block) => block.required).map((block) => block.key) || [],
                    }));
                  }}>
                    {templates.filter((templateOption) => templateOption.kind !== "shell").map((templateOption) => (
                      <option key={templateOption.slug} value={templateOption.slug}>{templateOption.title}</option>
                    ))}
                  </select>
                </label>
                <p>{item.reason}</p>
                <label className="field compact-field">
                  <span>Drafting instructions</span>
                  <textarea value={item.drafting_instructions || ""} onChange={(event) => onPlanChange(updateDocument(plan, item.id, { drafting_instructions: event.target.value }))} rows={3} />
                </label>
                <div className="block-picker-list">
                  {blocks.map((block) => (
                    <label className="checkbox-row" key={block.key}>
                      <input
                        type="checkbox"
                        checked={selected.has(block.key)}
                        disabled={block.required}
                        onChange={(event) => {
                          const keys = event.target.checked
                            ? [...selected, block.key]
                            : [...selected].filter((key) => key !== block.key);
                          onPlanChange(updateDocument(plan, item.id, { selected_block_keys: keys }));
                        }}
                      />
                      <span>{block.label}</span>
                    </label>
                  ))}
                </div>
                {(item.missing_information || []).some((missing) => !missing.not_needed) && (
                  <div className="missing-info-list">
                    {(item.missing_information || []).map((missing, index) => !missing.not_needed && (
                      <div className="missing-info-item" key={`${missing.field}-${index}`}>
                        <strong>{missing.question}</strong>
                        <input
                          placeholder="Add answer"
                          value={missing.answer || ""}
                          onChange={(event) => updateMissing(item, index, { answer: event.target.value, not_needed: false })}
                        />
                        <div className="button-row compact">
                          <button className="secondary" type="button" onClick={() => updateMissing(item, index, { not_needed: true, required_for_generation: false })}>Skip question</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            );
          })}
        </div>
        <div className={shouldPauseForQuestions ? "question-gate active" : "question-gate"}>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={clarifyMissingFactsBeforeDraft}
              onChange={(event) => onClarifyMissingFactsBeforeDraftChange(event.target.checked)}
            />
            <span>Pause for unanswered drafting questions before generating</span>
          </label>
          {shouldPauseForQuestions && (
            <div className="question-gate-summary">
              <strong>{unansweredQuestions.length} question{unansweredQuestions.length === 1 ? "" : "s"} need an answer or skip decision.</strong>
              <span>Answer them above, mark them not needed, or turn off this pause to generate with placeholders.</span>
            </div>
          )}
        </div>
        {(!authorProfile.displayName && !authorProfile.email) && (
          <div className="warning-panel"><UserRound size={16} /> Author info is missing; caption/signature will use placeholders.</div>
        )}
        <label className="field">
          <span>Regenerate plan with guidance</span>
          <textarea value={guidance} onChange={(event) => setGuidance(event.target.value)} rows={2} />
        </label>
        <div className="button-row step-actions">
          <button className="btn btn-outline-secondary" type="button" disabled={busy} onClick={() => onRegeneratePlan(guidance)}>
            {busy ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />} Regenerate plan
          </button>
          <button className="btn btn-primary" type="button" disabled={busy || !documentItems.length || shouldPauseForQuestions} onClick={onGenerateDraft}>
            {busy ? <Loader2 className="spin" size={16} /> : <CheckCircle2 size={16} />} {shouldPauseForQuestions ? "Answer questions to generate" : "Generate draft"}
          </button>
        </div>
      </div>

      <div className="support-panel-stack">
        <div className="support-tabs">
          {[
            ["documents", FileText, "Documents"],
            ["materials", ClipboardList, "Materials"],
            ["facts", ClipboardList, "Facts"],
            ["sources", Sparkles, "Sources"],
            ["law", CheckCircle2, "Law"],
            ["author", UserRound, "Author"],
          ].map(([id, Icon, label]) => (
            <button key={id} className={openPanel === id ? "selected" : ""} type="button" onClick={() => setOpenPanel(id)}>
              <Icon size={15} /> {label}
            </button>
          ))}
        </div>
        {openPanel === "facts" && <FactReview matter={matter} facts={matter?.facts || []} selectedFactIds={selectedFactIds} selectedCuratedFacts={selectedCuratedFacts} onFactChange={onFactChange} onCuratedChange={onCuratedChange} onMatterChange={onMatterChange} />}
        {openPanel === "materials" && <CaseMaterialsPanel matter={matter} selectedFactIds={selectedFactIds} onFactIdsAdded={onFactIdsAdded} onMatterChange={onMatterChange} />}
        {openPanel === "sources" && <DraftSupportReview session={session} selectedResults={selectedResults} onSelectedResultsChange={onSelectedResultsChange} onSessionChange={onSessionChange} />}
        {openPanel === "law" && <LawReview matter={matter} session={session} onIssuesChange={onIssuesChange} />}
        {openPanel === "author" && <div className="panel"><AuthorFields profile={authorProfile} onChange={onAuthorProfileChange} /></div>}
        {openPanel === "documents" && (
          <div className="panel compact-panel">
            <strong>{documentItems.length} document{documentItems.length === 1 ? "" : "s"} planned</strong>
            <p>{candidateIssues?.length ? `${candidateIssues.length} legal issue candidates reviewed.` : "Supporting panels are available when needed."}</p>
          </div>
        )}
      </div>
    </section>
  );
}

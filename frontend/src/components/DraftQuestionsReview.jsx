import React from "react";
import { CheckCircle2, HelpCircle, Loader2 } from "lucide-react";

function updateDocument(plan, documentId, patch) {
  return {
    ...plan,
    document_items: (plan.document_items || []).map((item) => (
      item.id === documentId ? { ...item, ...patch } : item
    )),
  };
}

export function unansweredPlanQuestions(plan) {
  return (plan?.document_items || []).flatMap((item) => (
    (item.missing_information || [])
      .filter((missing) => !missing.answer && !missing.not_needed)
      .map((missing, index) => ({ ...missing, documentId: item.id, documentTitle: item.title, index: (item.missing_information || []).indexOf(missing) }))
  ));
}

export function DraftQuestionsReview({ plan, busy, onPlanChange, onBack, onContinue }) {
  const questions = unansweredPlanQuestions(plan);

  function updateMissing(documentId, index, patch) {
    const item = (plan.document_items || []).find((entry) => entry.id === documentId);
    if (!item) return;
    const missing = [...(item.missing_information || [])];
    missing[index] = { ...missing[index], ...patch };
    onPlanChange(updateDocument(plan, documentId, { missing_information: missing }));
  }

  return (
    <section className="step-screen">
      <div className="panel">
        <div className="step-guidance">
          <span className="block-kicker">Drafting questions</span>
          <h3>Answer these before the draft is generated</h3>
          <p className="muted">
            These fields would otherwise appear as placeholder text (like <code>[Plaintiff Name]</code>) in the draft.
            Answer each question or explicitly skip it.
          </p>
        </div>
        {questions.length === 0 ? (
          <div className="empty-state compact">
            <CheckCircle2 size={20} />
            <strong className="empty-state-title">All questions answered</strong>
            <p>You're ready to generate the draft.</p>
          </div>
        ) : (
          <div className="missing-info-list">
            {questions.map((question) => (
              <div className="missing-info-item" key={`${question.documentId}-${question.index}`}>
                <div className="missing-info-item-heading">
                  <HelpCircle size={15} />
                  <strong>{question.question}</strong>
                </div>
                {question.documentTitle && <small className="muted">{question.documentTitle}</small>}
                <input
                  placeholder="Add answer"
                  value={question.answer || ""}
                  onChange={(event) => updateMissing(question.documentId, question.index, { answer: event.target.value, not_needed: false })}
                />
                <div className="button-row compact">
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => updateMissing(question.documentId, question.index, { not_needed: true, required_for_generation: false })}
                  >
                    Skip — leave as placeholder
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="button-row step-actions">
          <button className="btn btn-outline-secondary" type="button" onClick={onBack}>Back to plan</button>
          <button className="btn btn-primary" type="button" disabled={busy || questions.length > 0} onClick={onContinue}>
            {busy ? <Loader2 className="spin" size={16} /> : <CheckCircle2 size={16} />} Continue to draft
          </button>
        </div>
      </div>
    </section>
  );
}

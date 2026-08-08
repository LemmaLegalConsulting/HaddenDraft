/** Which of a draft plan's open blanks a reviewer sees, and which hold up the draft. */

export function planQuestions(plan) {
  return (plan?.document_items || []).flatMap((item) => (
    (item.missing_information || [])
      .map((missing, index) => ({ ...missing, documentId: item.id, documentTitle: item.title, index }))
  ));
}

/**
 * Questions the draft cannot answer for itself, so generation waits on them.
 *
 * A drafting direction the template author left behind ("[describe occupants]")
 * is the model's to carry out, so leaving it blank is a choice rather than an
 * omission and it never blocks the draft.
 */
export function unansweredPlanQuestions(plan) {
  return planQuestions(plan).filter((missing) => (
    !missing.answer?.trim() && !missing.not_needed && !missing.ai_completable
  ));
}

/** Every blank still worth a reviewer's eye, including the drafted suggestions. */
export function planQuestionsForReview(plan) {
  return planQuestions(plan).filter((missing) => !missing.not_needed);
}

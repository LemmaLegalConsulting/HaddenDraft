import assert from "node:assert/strict";
import test from "node:test";

import { planQuestionsForReview, unansweredPlanQuestions } from "../src/components/planQuestions.js";

function plan(missing) {
  return { document_items: [{ id: "motion", title: "Motion", missing_information: missing }] };
}

test("a skipped question stops holding up the draft", () => {
  const skipped = plan([
    { field: "fields.hearing_date", question: "When is the hearing?", not_needed: true },
    { field: "fields.time", question: "What time?", not_needed: true },
  ]);

  assert.deepEqual(unansweredPlanQuestions(skipped), []);
  assert.deepEqual(planQuestionsForReview(skipped), []);
});

test("a drafting direction never blocks the draft, but is still reviewed", () => {
  const mixed = plan([
    { field: "fields.describe_occupants", question: "Describe occupants.", ai_completable: true },
    { field: "fields.hearing_date", question: "When is the hearing?" },
  ]);

  assert.deepEqual(unansweredPlanQuestions(mixed).map((item) => item.field), ["fields.hearing_date"]);
  assert.equal(planQuestionsForReview(mixed).length, 2);
});

test("an answer from the case record satisfies a question without hiding it", () => {
  const answered = plan([
    {
      field: "fields.premises_address",
      question: "What is the address of the rental unit?",
      answer: "1234 Euclid Ave.",
      answer_source: "case_record",
    },
  ]);

  assert.deepEqual(unansweredPlanQuestions(answered), []);
  assert.equal(planQuestionsForReview(answered).length, 1);
});

test("whitespace is not an answer", () => {
  assert.equal(unansweredPlanQuestions(plan([{ field: "fields.time", answer: "   " }])).length, 1);
});

test("a plan without documents has nothing to ask", () => {
  assert.deepEqual(unansweredPlanQuestions(null), []);
  assert.deepEqual(planQuestionsForReview({}), []);
});

import assert from "node:assert/strict";
import test from "node:test";

import { factRecommendationState, mergeFactIds } from "../src/components/factReviewState.js";

test("maps the recommendation API contract into refreshed Fact Review state", () => {
  const response = {
    factIds: [11],
    facts: [{ id: 11, text: "A sourced fact" }],
    case: { id: "CASE-1", facts: [{ id: 11, text: "A sourced fact" }] },
    session: { id: 7, selectedFactIds: [11] },
  };

  assert.deepEqual(factRecommendationState(response), {
    session: response.session,
    matter: response.case,
    factIds: [11],
    facts: response.facts,
  });
});

test("falls back to session data and merges selected ids without duplicates", () => {
  const session = { id: 7, selectedFactIds: [3, 4], matter: { id: "CASE-1" } };

  assert.deepEqual(factRecommendationState({}, session).factIds, [3, 4]);
  assert.deepEqual(mergeFactIds([3, 4], [4, 5]), [3, 4, 5]);
});

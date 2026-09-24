import assert from "node:assert/strict";
import test from "node:test";

import { initialActiveCase, rememberCase, rememberedCase } from "../src/state/activeCase.js";

function memoryStore() {
  const values = new Map();
  return {
    getItem: (key) => (values.has(key) ? values.get(key) : null),
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

test("with nothing remembered, no case is activated -- never the first in the list", () => {
  assert.equal(initialActiveCase({ username: "advocate", store: memoryStore() }), null);
});

test("the case a user chose is restored after a reload", () => {
  const store = memoryStore();
  rememberCase("advocate", "26-0000085", store);
  assert.equal(initialActiveCase({ username: "advocate", store }), "26-0000085");
});

test("one user's case is never restored for another on the same browser", () => {
  const store = memoryStore();
  rememberCase("advocate", "26-0000085", store);
  assert.equal(initialActiveCase({ username: "colleague", store }), null);
});

test("a case already active wins over the remembered one", () => {
  const store = memoryStore();
  rememberCase("advocate", "26-0000085", store);
  assert.equal(initialActiveCase({ current: "26-0000084", username: "advocate", store }), "26-0000084");
});

test("clearing the choice forgets it", () => {
  const store = memoryStore();
  rememberCase("advocate", "26-0000085", store);
  rememberCase("advocate", null, store);
  assert.equal(rememberedCase("advocate", store), null);
});

test("storage that throws reads as nothing remembered", () => {
  const broken = {
    getItem() { throw new Error("blocked"); },
    setItem() { throw new Error("blocked"); },
    removeItem() { throw new Error("blocked"); },
  };
  rememberCase("advocate", "26-0000085", broken);
  assert.equal(initialActiveCase({ username: "advocate", store: broken }), null);
});

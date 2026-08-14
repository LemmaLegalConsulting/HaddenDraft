import assert from "node:assert/strict";
import test from "node:test";

import { adminUrlFrom } from "../src/api/urls.js";

test("same-origin deployment keeps the admin on the page's own host", () => {
  assert.equal(
    adminUrlFrom("/api", "https://cle-draft.lemmalegal.com"),
    "https://cle-draft.lemmalegal.com/admin/",
  );
});

test("split deployment puts the admin on the API host, not the app host", () => {
  // The whole point: the app host is a static site with no Django on it, so a
  // relative /admin/ would 404 against the app rather than reach the admin.
  assert.equal(
    adminUrlFrom("https://api.cle-draft.lemmalegal.com/api", "https://cle-draft.lemmalegal.com"),
    "https://api.cle-draft.lemmalegal.com/admin/",
  );
});

test("a trailing slash on the API base does not move the admin", () => {
  assert.equal(
    adminUrlFrom("https://api.cle-draft.lemmalegal.com/api/", "https://cle-draft.lemmalegal.com"),
    "https://api.cle-draft.lemmalegal.com/admin/",
  );
});

test("the dev server reaches the admin on the Django port", () => {
  assert.equal(
    adminUrlFrom("http://127.0.0.1:8000/api", "http://127.0.0.1:5173"),
    "http://127.0.0.1:8000/admin/",
  );
});

import assert from "node:assert/strict";
import test from "node:test";

import { apiIsCrossOrigin, clearStaleCsrfCookie } from "../src/api/csrf.js";

/** Records what gets written to document.cookie without needing a browser. */
function fakeCookieStore() {
  const writes = [];
  return {
    writes,
    set cookie(value) {
      writes.push(value);
    },
    get cookie() {
      return "";
    },
  };
}

test("a relative API base is same-origin", () => {
  assert.equal(apiIsCrossOrigin("/api", "https://cle-draft.lemmalegal.com"), false);
});

test("a sibling subdomain is a different origin", () => {
  assert.equal(
    apiIsCrossOrigin("https://api.cle-draft.lemmalegal.com/api", "https://cle-draft.lemmalegal.com"),
    true,
  );
});

test("the same host on another port is also a different origin", () => {
  assert.equal(apiIsCrossOrigin("http://127.0.0.1:8000/api", "http://127.0.0.1:5174"), true);
});

test("same-origin deployments keep their cookie", () => {
  // The live token lives on this host. Deleting it would break every write on
  // exactly the deployments that never had the problem.
  const store = fakeCookieStore();
  const acted = clearStaleCsrfCookie({
    apiBase: "/api",
    pageOrigin: "https://cle-draft.lemmalegal.com",
    cookieStore: store,
  });

  assert.equal(acted, false);
  assert.deepEqual(store.writes, []);
});

test("a split deployment expires the host-only cookie", () => {
  const store = fakeCookieStore();
  const acted = clearStaleCsrfCookie({
    apiBase: "https://api.cle-draft.lemmalegal.com/api",
    pageOrigin: "https://cle-draft.lemmalegal.com",
    cookieStore: store,
  });

  assert.equal(acted, true);
  assert.equal(store.writes.length, 1);
  const written = store.writes[0];
  assert.match(written, /^csrftoken=;/);
  assert.match(written, /Max-Age=0/);
  assert.match(written, /Path=\//);
  // No Domain attribute: that is what makes this target the host-only cookie
  // and leave the parent-domain one, which is the live one, in place.
  assert.doesNotMatch(written, /Domain=/i);
});

test("no cookie store means nothing to do", () => {
  assert.equal(
    clearStaleCsrfCookie({
      apiBase: "https://api.cle-draft.lemmalegal.com/api",
      pageOrigin: "https://cle-draft.lemmalegal.com",
      cookieStore: null,
    }),
    false,
  );
});

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// A component that is used but never defined or imported does not fail the
// build -- Vite happily serves it, and the page dies at render time with
// "Uncaught ReferenceError: X is not defined". That is exactly what happened
// to ArgumentGymPanel when a rewrite deleted CheckSelector, ChecklistModal and
// PassivePhraseModal while leaving the JSX that renders them. This scans the
// source for the mistake so a refactor cannot land it again.

const componentsDir = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "components");

function boundNames(source) {
  const names = new Set(["React", "Fragment"]);
  const add = (name) => name && names.add(name);

  // import Default, { named as alias } from "..."; import * as ns from "...";
  for (const [, clause] of source.matchAll(/^import\s+([\s\S]*?)\s+from\s+["']/gm)) {
    for (const [, name] of clause.matchAll(/\b([A-Za-z_$][\w$]*)\s*(?:,|\}|$)/g)) add(name);
    for (const [, , alias] of clause.matchAll(/\b([A-Za-z_$][\w$]*)\s+as\s+([A-Za-z_$][\w$]*)/g)) add(alias);
  }
  // function declarations, at any nesting
  for (const [, name] of source.matchAll(/\bfunction\s+([A-Za-z_$][\w$]*)/g)) add(name);
  // const/let/var bindings, including the names inside a destructuring pattern
  for (const [, pattern] of source.matchAll(/\b(?:const|let|var)\s+([\s\S]*?)=/g)) {
    for (const [, name] of pattern.matchAll(/\b([A-Za-z_$][\w$]*)\b/g)) add(name);
  }
  // parameters, so ([id, Icon, label]) => <Icon /> counts as bound
  for (const [, params] of source.matchAll(/(?:\(([^()]*)\)|([A-Za-z_$][\w$]*))\s*=>/g)) {
    for (const [, name] of (params || "").matchAll(/\b([A-Za-z_$][\w$]*)\b/g)) add(name);
  }
  for (const [, params] of source.matchAll(/\bfunction\s*[A-Za-z_$][\w$]*\s*\(([^()]*)\)/g)) {
    for (const [, name] of params.matchAll(/\b([A-Za-z_$][\w$]*)\b/g)) add(name);
  }
  return names;
}

function usedComponents(source) {
  const used = new Map();
  // Whole-source, not line by line: a tag whose props start on the next line
  // (`<CheckSelector\n  catalog={...}`) is still a use of that component.
  for (const match of source.matchAll(/<([A-Z][\w$]*)(?![\w$])/g)) {
    const tag = match[1];
    if (used.has(tag)) continue;
    used.set(tag, source.slice(0, match.index).split("\n").length);
  }
  return used;
}

const files = readdirSync(componentsDir).filter((name) => name.endsWith(".jsx"));

test("every component rendered in a .jsx file is defined or imported there", () => {
  assert.ok(files.length > 0, "no .jsx components found to check");
  const missing = [];
  for (const file of files) {
    const source = readFileSync(join(componentsDir, file), "utf8");
    const bound = boundNames(source);
    for (const [tag, line] of usedComponents(source)) {
      if (!bound.has(tag)) missing.push(`${file}:${line} <${tag}>`);
    }
  }
  assert.deepEqual(missing, [], `components used but never defined:\n${missing.join("\n")}`);
});

test("ArgumentGymPanel still defines the check and checklist controls it renders", () => {
  // The three that went missing, named so a re-deletion says which one.
  const source = readFileSync(join(componentsDir, "ArgumentGymPanel.jsx"), "utf8");
  for (const name of ["CheckSelector", "ChecklistModal", "PassivePhraseModal"]) {
    assert.match(source, new RegExp(`function ${name}\\(`), `${name} is rendered but no longer defined`);
    assert.match(source, new RegExp(`<${name}\\b`), `${name} is defined but no longer rendered`);
  }
});

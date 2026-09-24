import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// React clears a synthetic event's currentTarget as soon as the handler yields,
// so `event.currentTarget` read after an `await` is null. Four upload forms did
// exactly that to reset themselves after a successful save. Where the call sat
// inside a try block, the advocate saw "Cannot read properties of null
// (reading 'reset')" as the upload's error message -- after the upload had
// worked -- and the dialog stayed open for a second, duplicate upload. Found by
// driving the deployed app; the build and every unit test were green.

const srcDir = join(dirname(fileURLToPath(import.meta.url)), "..", "src");

function sourceFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.(jsx?|mjs)$/.test(entry.name) ? [path] : [];
  });
}

// The body of the async function enclosing `index`, found by walking back to
// the nearest `async` and matching braces forward from its opening one.
function enclosingAsyncBody(source, index) {
  let asyncAt = source.lastIndexOf("async", index);
  while (asyncAt !== -1) {
    const open = source.indexOf("{", asyncAt);
    if (open === -1 || open > index) return null;
    let depth = 0;
    for (let cursor = open; cursor < source.length; cursor += 1) {
      if (source[cursor] === "{") depth += 1;
      else if (source[cursor] === "}") {
        depth -= 1;
        if (depth === 0) {
          if (cursor > index) return { start: open, end: cursor };
          break;
        }
      }
    }
    asyncAt = source.lastIndexOf("async", asyncAt - 1);
  }
  return null;
}

test("no handler reads event.currentTarget after it has awaited", () => {
  const offenders = [];
  for (const file of sourceFiles(srcDir)) {
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(/\bevent\.currentTarget\b/g)) {
      const body = enclosingAsyncBody(source, match.index);
      if (!body) continue;
      const before = source.slice(body.start, match.index).replace(/\/\/[^\n]*|\/\*[\s\S]*?\*\//g, "");
      if (/\bawait\b/.test(before)) {
        const line = source.slice(0, match.index).split("\n").length;
        offenders.push(`${file.slice(srcDir.length + 1)}:${line}`);
      }
    }
  }
  assert.deepEqual(offenders, [], "read event.currentTarget into a variable before the first await");
});

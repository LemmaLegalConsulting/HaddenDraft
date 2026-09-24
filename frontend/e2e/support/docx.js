import { readFileSync } from "node:fs";
import { inflateRawSync } from "node:zlib";

// Just enough of the ZIP format to read a generated Office file's parts, so a
// download can be checked for what it says rather than for its extension. An
// exported "document" that is an empty shell or an error page renamed .docx
// passes every check that stops at the file name.

export function zipEntries(path) {
  const buffer = readFileSync(path);
  const eocd = buffer.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  if (eocd < 0) throw new Error(`${path} is not a ZIP file`);
  const count = buffer.readUInt16LE(eocd + 10);
  let offset = buffer.readUInt32LE(eocd + 16);
  const entries = new Map();
  for (let index = 0; index < count; index += 1) {
    const method = buffer.readUInt16LE(offset + 10);
    const compressed = buffer.readUInt32LE(offset + 20);
    const nameLength = buffer.readUInt16LE(offset + 28);
    const extraLength = buffer.readUInt16LE(offset + 30);
    const commentLength = buffer.readUInt16LE(offset + 32);
    const local = buffer.readUInt32LE(offset + 42);
    const name = buffer.toString("utf8", offset + 46, offset + 46 + nameLength);
    const localName = buffer.readUInt16LE(local + 26);
    const localExtra = buffer.readUInt16LE(local + 28);
    const start = local + 30 + localName + localExtra;
    const raw = buffer.subarray(start, start + compressed);
    entries.set(name, method === 8 ? inflateRawSync(raw) : raw);
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return entries;
}

// The visible text of a Word document's body, headers and footers.
export function docxText(path) {
  const entries = zipEntries(path);
  const parts = [...entries.keys()].filter((name) => /^word\/(document|header\d*|footer\d*)\.xml$/.test(name));
  if (!parts.includes("word/document.xml")) throw new Error(`${path} has no word/document.xml`);
  return parts
    .map((name) =>
      entries
        .get(name)
        .toString("utf8")
        .replace(/<w:tab\/>/g, "\t")
        .replace(/<\/w:p>/g, "\n")
        .replace(/<[^>]+>/g, "")
        .replace(/&amp;/g, "&")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&quot;/g, '"')
        .replace(/&apos;/g, "'"),
    )
    .join("\n");
}

// The parts of a document's package, for checks on what it carries besides text.
export function docxPartNames(path) {
  return [...zipEntries(path).keys()];
}

export function docxPart(path, name) {
  return zipEntries(path).get(name)?.toString("utf8") ?? null;
}

// Turning an export response into a file on disk. Kept separate from the
// panels because two of them do the same thing, and because the filename rule
// is worth testing without a DOM.

export function filenameFromDisposition(disposition, fallback = "document.docx") {
  const quoted = /filename="([^"]+)"/.exec(disposition || "");
  if (quoted) return quoted[1];
  const bare = /filename=([^;]+)/.exec(disposition || "");
  return bare ? bare[1].trim() : fallback;
}

export async function saveResponseAsFile(response, fallback = "document.docx") {
  const blob = await response.blob();
  const filename = filenameFromDisposition(response.headers.get("content-disposition"), fallback);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
  return filename;
}

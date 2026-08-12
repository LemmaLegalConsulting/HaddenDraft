// Turning a case-chat thread into a case note.
//
// The note has to stand on its own for whoever opens the file next, so it
// carries both sides of the exchange and says plainly that a machine wrote the
// answers. The scope key names the thread rather than the moment, so saving
// again after a few more questions replaces the note instead of adding another.

const REVIEW_FOOTER =
  "Written by the AI drafting tool as a working aid. It has not been reviewed by an attorney " +
  "and is not a substitute for checking current law.";

export function chatScopeKey({ matterId, threadId = "" } = {}) {
  return `case-chat:${matterId || "unknown"}:${threadId || "current"}`;
}

export function chatTranscriptTitle(messages) {
  const first = (messages || []).find((message) => message.role === "user");
  const question = (first?.content || "").trim().replace(/\s+/g, " ");
  if (!question) return "Case chat";
  return `Case chat: ${question.length > 120 ? `${question.slice(0, 117)}…` : question}`;
}

export function chatTranscriptBody(messages) {
  const lines = (messages || [])
    .filter((message) => (message.content || "").trim())
    .map((message) => `${message.role === "assistant" ? "AI" : "Advocate"}: ${message.content.trim()}`);
  return [...lines, REVIEW_FOOTER].join("\n\n");
}

export function chatTranscriptNote(messages, { matterId, threadId = "" } = {}) {
  return {
    title: chatTranscriptTitle(messages),
    body: chatTranscriptBody(messages),
    scopeKey: chatScopeKey({ matterId, threadId }),
  };
}

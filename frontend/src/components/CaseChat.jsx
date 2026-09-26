import React, { useEffect, useState } from "react";
import { History, Loader2, Plus, Send, Trash2 } from "lucide-react";

import { api } from "../api/client.js";
import { isConflict } from "../api/errors.js";
import { chatThreadView } from "../state/chatThreads.js";
import LegalServerSaveButton from "./LegalServerSaveButton.jsx";
import { chatTranscriptNote } from "./chatTranscript.js";
import { MarkdownResponse } from "./MarkdownResponse.jsx";
import { PanelHeading } from "./PanelHeading.jsx";

const starterPrompts = [
  { id: "about", label: "What's the case about?", prompt: "What's this case about?" },
  { id: "next", label: "Best next steps", prompt: "What's the next step I should take?" },
  { id: "timeline", label: "What happened so far?", prompt: "What's happened in this case so far?" },
];

function cleanMessage(text = "") {
  return text.replace(/<br\s*\/?>/gi, "\n");
}

// `threadId` is the thread the URL names (null for the current chat), and
// `onThreadChange(id | null)` moves the URL. The screen never substitutes one
// conversation for another: a thread that does not open says so.
export function CaseChat({ matter, onAction, legalserverSave = null, threadId = null, onThreadChange }) {
  const [messages, setMessages] = useState([]);
  const [currentThreadId, setCurrentThreadId] = useState(null);
  const [threadMissing, setThreadMissing] = useState(false);
  const [staleThread, setStaleThread] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [showHistory, setShowHistory] = useState(true);
  const [threads, setThreads] = useState([]);
  const [delivery, setDelivery] = useState(null);
  const [savingToLegalServer, setSavingToLegalServer] = useState(false);

  const view = chatThreadView({ routeThreadId: threadId, currentThreadId });
  const selectedThreadId = view.readOnly ? String(threadId) : "";

  useEffect(() => {
    setInput("");
    setError("");
    setThreadMissing(false);
    setStaleThread(false);
    setDelivery(null);
    if (!matter) {
      setMessages([]);
      setHistoryLoading(false);
      return undefined;
    }
    setHistoryLoading(true);
    const controller = new AbortController();
    // Reading only: opening the chat never starts a conversation.
    api.caseChatHistory(matter.id, threadId, { signal: controller.signal })
      .then((response) => {
        setMessages(response.messages || []);
        setThreads(response.threads || []);
        setCurrentThreadId(response.currentThreadId ?? null);
      })
      .catch((err) => {
        if (controller.signal.aborted || err?.name === "AbortError") return;
        if (err.status === 404) {
          setMessages([]);
          setThreadMissing(true);
          return;
        }
        setError(err.message || "Could not load case chat history.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setHistoryLoading(false);
      });
    return () => controller.abort();
  }, [matter?.id, threadId]);

  async function submitMessage(content) {
    if (!content || !matter) return;
    const nextMessages = [...messages, { role: "user", content }];
    setMessages(nextMessages);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const response = await api.caseChat(matter.id, { content, threadId: view.writeThreadId ?? undefined });
      setCurrentThreadId(response.threadId ?? null);
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: response.message,
          toolsUsed: response.toolsUsed || [],
          actions: response.actions || [],
        },
      ]);
    } catch (err) {
      if (isConflict(err)) {
        // Another window started a new chat; this one was about to write
        // into a conversation that is no longer current.
        setMessages(messages);
        setInput(content);
        setStaleThread(true);
        return;
      }
      setError(err.message || "Case chat failed.");
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    await submitMessage(input.trim());
  }

  async function clearHistory() {
    if (!matter) return;
    // Clear deletes, unlike New chat, which keeps the old thread; ask first.
    if (!window.confirm("Delete this conversation? It cannot be recovered. New chat keeps it instead.")) return;
    setBusy(true);
    try { await api.clearCaseChatHistory(matter.id, view.writeThreadId); setMessages([]); setShowHistory(false); }
    catch (err) {
      if (isConflict(err)) setStaleThread(true);
      else setError(err.message || "Could not clear case chat history.");
    }
    finally { setBusy(false); }
  }

  async function newChat() {
    if (!matter) return;
    setBusy(true);
    try {
      const response = await api.newCaseChat(matter.id);
      setMessages([]);
      setThreads(response.threads || []);
      setCurrentThreadId(null);
      setShowHistory(true);
      if (threadId != null) onThreadChange?.(null);
    }
    catch (err) { setError(err.message || "Could not start a new case chat."); }
    finally { setBusy(false); }
  }

  async function saveToLegalServer() {
    if (!matter || !messages.length) return;
    setSavingToLegalServer(true);
    setError("");
    try {
      // One note per thread. Saving the same conversation again after a few
      // more questions replaces it, so the case file holds the whole exchange
      // once rather than a note per round trip.
      const response = await api.saveCaseNoteToLegalServer(matter.id, {
        ...chatTranscriptNote(messages, { matterId: matter.id, threadId: selectedThreadId }),
        origin: "case_chat",
      });
      setDelivery(response.delivery);
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingToLegalServer(false);
    }
  }

  function selectThread(event) {
    const next = event.target.value;
    onThreadChange?.(next ? Number(next) : null);
  }

  return (
    <div className="panel chat-panel">
      <PanelHeading
        title="Case chat"
        description="Ask questions about this case file. Answers cite the documents and notes they came from."
      />
      {!matter && (
        <div className="empty-state compact-empty">
          <strong className="empty-state-title">Select a case</strong>
          <p>Choose a LegalServer matter to ask case-specific questions.</p>
        </div>
      )}
      {matter && threadMissing && (
        <div className="empty-state compact-empty" role="status">
          <strong className="empty-state-title">This conversation is not available</strong>
          <p>No chat thread with this number belongs to you on this case. No other conversation is shown in its place.</p>
          <button className="btn btn-primary" type="button" onClick={() => onThreadChange?.(null)}>Open the current chat</button>
        </div>
      )}
      {matter && !threadMissing && (
        <>
          <div className="chat-history-actions">
            <select className="form-select" aria-label="Case chat threads" value={selectedThreadId} onChange={selectThread}>
              <option value="">Current chat</option>
              {threads.filter((thread) => !thread.active).map((thread) => <option key={thread.id} value={thread.id}>{thread.preview}</option>)}
            </select>
            <button className="text-link-button" type="button" onClick={() => setShowHistory((value) => !value)}><History size={15} /> {showHistory ? "Hide history" : "View history"}</button>
            <button className="text-link-button" type="button" disabled={busy} onClick={newChat}><Plus size={15} /> New chat</button>
            <button className="text-link-button danger" type="button" disabled={busy || !!selectedThreadId || !messages.length} onClick={clearHistory}><Trash2 size={15} /> Clear</button>
          </div>
          <LegalServerSaveButton
            onSave={saveToLegalServer}
            busy={savingToLegalServer}
            delivery={delivery}
            bootstrapSave={legalserverSave}
            disabled={busy || historyLoading || !messages.length}
          />
          <div className="chat-transcript">
            {(!messages.length || !showHistory) && (
              <div className="empty-state compact-empty">
                <p>Ask about case status, assignments, documents, facts, or next drafting steps.</p>
                <div className="starter-card-list">
                  {starterPrompts.map((starter) => (
                    <button key={starter.id} className="starter-card" type="button" onClick={() => submitMessage(starter.prompt)}>
                      {starter.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {showHistory && messages.map((message, index) => (
              <article key={`${message.role}-${index}`} className={`chat-message ${message.role}`}>
                {message.role === "assistant" ? <MarkdownResponse content={cleanMessage(message.content)} /> : <p>{cleanMessage(message.content)}</p>}
                {message.toolsUsed?.length > 0 && <small>Used {message.toolsUsed.join(", ")}</small>}
                {message.actions?.length > 0 && (
                  <div className="action-card-list">
                    {message.actions.map((action) => (
                      <button key={action.id} className="action-card" type="button" onClick={() => onAction?.(action)}>
                        <strong>{action.title}</strong>
                        <span>{action.summary}</span>
                        {action.effect && <small>{action.effect}</small>}
                        {action.destination && <small>Goes to: {action.destination}</small>}
                      </button>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
          {error && <div className="inline-error">{error}</div>}
          {staleThread && (
            <div className="inline-error" role="alert">
              A new chat was started in another window, so this conversation is no longer the current one. Your message was not sent and is still in the box.
              <button className="btn btn-light" type="button" onClick={() => { setStaleThread(false); onThreadChange?.(null); }}>Open the current chat</button>
            </div>
          )}
          {view.readOnly && <p className="muted">This is an earlier conversation. It is kept as a record; start or open the current chat to ask more.</p>}
          <form className="chat-compose" onSubmit={sendMessage}>
            <label className="visually-hidden" htmlFor="case-chat-input">Message</label>
            <input className="form-control"
              id="case-chat-input"
              aria-describedby="case-chat-input-help"
              value={input}
              onChange={(event) => setInput(event.target.value)}
            />
            <button className="btn btn-primary" disabled={busy || historyLoading || view.readOnly || !input.trim()}>
              {busy ? <Loader2 className="spin" size={16} /> : <Send size={16} />} Send
            </button>
          </form>
          <p className="muted chat-compose-help" id="case-chat-input-help">Ask about documents, case posture, parties, or drafting strategy.</p>
        </>
      )}
    </div>
  );
}

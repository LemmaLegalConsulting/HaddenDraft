import React, { useEffect, useState } from "react";
import { History, Loader2, Plus, Send, Trash2 } from "lucide-react";

import { api } from "../api/client.js";
import { MarkdownResponse } from "./MarkdownResponse.jsx";

const starterPrompts = [
  { id: "about", label: "What's the case about?", prompt: "What's this case about?" },
  { id: "next", label: "Best next steps", prompt: "What's the next step I should take?" },
  { id: "timeline", label: "What happened so far?", prompt: "What's happened in this case so far?" },
];

function cleanMessage(text = "") {
  return text.replace(/<br\s*\/?>/gi, "\n");
}

export function CaseChat({ matter, onAction }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [showHistory, setShowHistory] = useState(true);
  const [threads, setThreads] = useState([]);
  const [selectedThreadId, setSelectedThreadId] = useState("");

  useEffect(() => {
    setInput("");
    setError("");
    if (!matter) {
      setMessages([]);
      setHistoryLoading(false);
      return undefined;
    }
    setHistoryLoading(true);
    let cancelled = false;
    api.caseChatHistory(matter.id)
      .then((response) => {
        if (!cancelled) { setMessages(response.messages || []); setThreads(response.threads || []); }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Could not load case chat history.");
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => { cancelled = true; };
  }, [matter?.id]);

  async function submitMessage(content) {
    if (!content || !matter) return;
    const nextMessages = [...messages, { role: "user", content }];
    setMessages(nextMessages);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const response = await api.caseChat(matter.id, { content });
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
    setBusy(true);
    try { await api.clearCaseChatHistory(matter.id); setMessages([]); setShowHistory(false); }
    catch (err) { setError(err.message || "Could not clear case chat history."); }
    finally { setBusy(false); }
  }

  async function newChat() {
    if (!matter) return;
    setBusy(true);
    try { const response = await api.newCaseChat(matter.id); setMessages([]); setThreads(response.threads || []); setSelectedThreadId(""); setShowHistory(true); }
    catch (err) { setError(err.message || "Could not start a new case chat."); }
    finally { setBusy(false); }
  }

  async function selectThread(event) {
    const threadId = event.target.value;
    setSelectedThreadId(threadId);
    const response = await api.caseChatHistory(matter.id, threadId);
    setMessages(response.messages || []);
  }

  return (
    <div className="panel chat-panel">
      {!matter && (
        <div className="empty-state compact-empty">
          <strong className="empty-state-title">Select a case</strong>
          <p>Choose a LegalServer matter to ask case-specific questions.</p>
        </div>
      )}
      {matter && (
        <>
          <div className="chat-history-actions">
            <select aria-label="Case chat threads" value={selectedThreadId} onChange={selectThread}>
              <option value="">Current chat</option>
              {threads.filter((thread) => !thread.active).map((thread) => <option key={thread.id} value={thread.id}>{thread.preview}</option>)}
            </select>
            <button className="text-link-button" type="button" onClick={() => setShowHistory((value) => !value)}><History size={15} /> {showHistory ? "Hide history" : "View history"}</button>
            <button className="text-link-button" type="button" disabled={busy} onClick={newChat}><Plus size={15} /> New chat</button>
            <button className="text-link-button danger" type="button" disabled={busy || !!selectedThreadId || !messages.length} onClick={clearHistory}><Trash2 size={15} /> Clear</button>
          </div>
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
                      </button>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
          {error && <div className="inline-error">{error}</div>}
          <form className="chat-compose" onSubmit={sendMessage}>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about documents, case posture, parties, or drafting strategy"
            />
            <button className="primary" disabled={busy || historyLoading || !!selectedThreadId || !input.trim()}>
              {busy ? <Loader2 className="spin" size={16} /> : <Send size={16} />} Send
            </button>
          </form>
        </>
      )}
    </div>
  );
}

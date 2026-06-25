import React, { useEffect, useState } from "react";
import { Bot, Loader2, Send } from "lucide-react";

import { api } from "../api/client.js";

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
  const [error, setError] = useState("");

  useEffect(() => {
    setMessages([]);
    setInput("");
    setError("");
  }, [matter?.id]);

  async function submitMessage(content) {
    if (!content || !matter) return;
    const nextMessages = [...messages, { role: "user", content }];
    setMessages(nextMessages);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const response = await api.caseChat(matter.id, { messages: nextMessages });
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

  return (
    <div className="panel chat-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Case primary</p>
          <h3>Chat with this case</h3>
        </div>
        <Bot size={18} />
      </div>
      {!matter && (
        <div className="empty-state compact-empty">
          <h3>Select a case</h3>
          <p>Choose a LegalServer matter to ask case-specific questions.</p>
        </div>
      )}
      {matter && (
        <>
          <div className="chat-transcript">
            {!messages.length && (
              <div className="empty-state compact-empty">
                <h3>{matter.client}</h3>
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
            {messages.map((message, index) => (
              <article key={`${message.role}-${index}`} className={`chat-message ${message.role}`}>
                <p>{cleanMessage(message.content)}</p>
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
            <button className="primary" disabled={busy || !input.trim()}>
              {busy ? <Loader2 className="spin" size={16} /> : <Send size={16} />} Send
            </button>
          </form>
        </>
      )}
    </div>
  );
}

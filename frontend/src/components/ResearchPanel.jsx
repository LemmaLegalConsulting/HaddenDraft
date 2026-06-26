import React, { useState } from "react";
import {
  Bot,
  BookOpen,
  Briefcase,
  Database,
  FileArchive,
  FileSearch,
  FileText,
  FolderOpen,
  Gavel,
  Landmark,
  Library,
  Loader2,
  Search,
  Send,
  Upload,
} from "lucide-react";

import { api } from "../api/client.js";

const SOURCE_GROUPS = [
  {
    title: "Case",
    options: [
      { id: "case-file", label: "Case", kind: "legalserver", icon: Briefcase },
    ],
  },
  {
    title: "Example pleadings",
    options: [
      { id: "sharepoint", label: "SharePoint", kind: "sharepoint", icon: FolderOpen },
    ],
  },
  {
    title: "Case law",
    options: [
      { id: "ohio-cases", label: "Ohio Cases", kind: "local_cases", icon: Landmark },
      { id: "freelaw-project", label: "FreeLaw Project", kind: "local_cases", icon: Gavel },
    ],
  },
  {
    title: "Statutes",
    options: [
      { id: "ohio-statutes", label: "Ohio Statutes", kind: "rag", icon: FileText },
    ],
  },
  {
    title: "User resources",
    options: [
      { id: "user-resources", label: "User Resources", kind: "user_resources", icon: FileArchive },
    ],
  },
  {
    title: "Handbooks and treatises",
    options: [
      { id: "treatise", label: "Treatise", kind: "rag", icon: BookOpen },
      { id: "hud-handbook", label: "HUD Handbook", kind: "rag", icon: Library },
    ],
  },
];

function availableSourceGroups(sources) {
  const availableKinds = new Set(sources.map((source) => source.kind));
  return SOURCE_GROUPS
    .map((group) => ({
      ...group,
      options: group.options.filter((option) => availableKinds.has(option.kind)),
    }))
    .filter((group) => group.options.length);
}

export function ResearchPanel({ matter, sources, onResults }) {
  const [query, setQuery] = useState("");
  const [selectedSourceIds, setSelectedSourceIds] = useState([]);
  const [results, setResults] = useState([]);
  const [selectedResultIds, setSelectedResultIds] = useState([]);
  const [messages, setMessages] = useState([]);
  const [useAi, setUseAi] = useState(true);
  const [resources, setResources] = useState([]);
  const [resourceTitle, setResourceTitle] = useState("");
  const [resourceType, setResourceType] = useState("case");
  const [resourceFile, setResourceFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [error, setError] = useState("");

  React.useEffect(() => {
    let cancelled = false;
    api.userResources()
      .then((response) => {
        if (!cancelled) setResources(response.resources || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const sourceGroups = availableSourceGroups(sources);
  const sourceOptions = sourceGroups.flatMap((group) => group.options);
  const selectedKinds = [...new Set(
    selectedSourceIds
      .map((sourceId) => sourceOptions.find((option) => option.id === sourceId)?.kind)
      .filter(Boolean)
  )];

  function toggleSource(sourceId) {
    setSelectedSourceIds((current) => current.includes(sourceId) ? current.filter((item) => item !== sourceId) : [...current, sourceId]);
  }

  async function runSearch(event) {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;
    setBusy(true);
    setError("");
    const nextMessages = [...messages, { role: "user", content: trimmedQuery }];
    if (useAi) {
      setMessages(nextMessages);
    }
    try {
      const response = await api.research({
        query: trimmedQuery,
        matterId: matter?.id,
        jurisdiction: matter?.jurisdiction,
        sourceKinds: selectedKinds.length ? selectedKinds : undefined,
        useAi,
        messages: nextMessages,
      });
      setResults(response.results);
      setSelectedResultIds(response.results.map((result) => result.id));
      onResults(response.results);
      if (useAi && response.answer) {
        setMessages([...nextMessages, { role: "assistant", content: response.answer }]);
      }
      setQuery("");
    } catch (err) {
      setError(err.message || "Source search failed.");
      if (useAi) {
        setMessages(messages);
      }
    } finally {
      setBusy(false);
    }
  }

  function toggleResult(result) {
    setSelectedResultIds((current) => {
      const nextIds = current.includes(result.id) ? current.filter((id) => id !== result.id) : [...current, result.id];
      onResults(results.filter((item) => nextIds.includes(item.id)));
      return nextIds;
    });
  }

  async function uploadResource(event) {
    event.preventDefault();
    if (!resourceFile) return;
    setUploadBusy(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("title", resourceTitle || resourceFile.name);
      formData.append("resourceType", resourceType);
      formData.append("file", resourceFile);
      const response = await api.createUserResource(formData);
      setResources((current) => [response.resource, ...current.filter((item) => item.id !== response.resource.id)]);
      setResourceTitle("");
      setResourceFile(null);
      setShowUploadForm(false);
      event.currentTarget.reset();
    } catch (err) {
      setError(err.message || "Reference upload failed.");
    } finally {
      setUploadBusy(false);
    }
  }

  return (
    <div className="panel">
      <div className="private-reference-panel">
        {resources.length > 0 && (
          <div className="reference-list">
            {resources.slice(0, 4).map((resource) => (
              <small key={resource.id}>{resource.title} · {resource.resourceType}</small>
            ))}
          </div>
        )}
        <button
          className="text-link-button"
          type="button"
          aria-expanded={showUploadForm}
          onClick={() => setShowUploadForm((current) => !current)}
        >
          Upload a reference...
        </button>
        {showUploadForm && (
          <form className="reference-upload-form" onSubmit={uploadResource}>
            <div className="reference-upload-grid">
              <label className="field">
                <span>Private reference</span>
                <input value={resourceTitle} onChange={(event) => setResourceTitle(event.target.value)} />
                <small className="field-help">Optional. If blank, the file name will be used.</small>
              </label>
              <label className="field">
                <span>Type</span>
                <select value={resourceType} onChange={(event) => setResourceType(event.target.value)}>
                  <option value="case">Case</option>
                  <option value="brief">Example brief</option>
                  <option value="example">Example filing</option>
                  <option value="other">Other</option>
                </select>
              </label>
            </div>
            <label className="field">
              <span>Reference file</span>
              <input
                type="file"
                accept=".txt,.md,.csv,.json,.html,.htm,.docx,.pdf,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) => setResourceFile(event.target.files?.[0] || null)}
              />
            </label>
            <button className="secondary full" type="submit" disabled={uploadBusy || !resourceFile}>
              {uploadBusy ? <Loader2 className="spin" size={16} /> : <Upload size={16} />} Upload private reference
            </button>
          </form>
        )}
      </div>
      <form className="research-chat-form" onSubmit={runSearch}>
        {useAi && messages.length > 0 && (
          <div className="research-transcript" aria-label="Research conversation">
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`research-message ${message.role}`}>
                <strong>{message.role === "assistant" ? "AI" : "You"}</strong>
                <p>{message.content}</p>
              </div>
            ))}
          </div>
        )}
        <div className="research-mode-row">
          <label className="research-ai-toggle">
            <input
              type="checkbox"
              checked={useAi}
              onChange={(event) => setUseAi(event.target.checked)}
            />
            <span>{useAi ? <Bot size={16} /> : <Database size={16} />} AI answer</span>
          </label>
          <small>{useAi ? "Ask connected sources and get a cited answer." : "Retrieve matching results only."}</small>
        </div>
        <div className="research-question">
          <label className="field">
            <span>Research question</span>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <p className="field-example">Example: Can a tenant raise habitability conditions as a defense when rent is disputed and rental assistance is pending?</p>
        </div>
        {sourceGroups.length > 0 && (
          <div className="source-picker" aria-label="Research sources">
            <div className="source-toggles">
              {sourceGroups.map((group) => (
                <React.Fragment key={group.title}>
                  {group.options.map((source) => {
                    const Icon = source.icon || FileSearch;
                    const selected = selectedSourceIds.includes(source.id);
                    return (
                      <button
                        key={source.id}
                        className={selected ? "selected" : ""}
                        type="button"
                        aria-pressed={selected}
                        title={source.label}
                        onClick={() => toggleSource(source.id)}
                      >
                        <Icon size={18} aria-hidden="true" />
                        <span>{source.label}</span>
                        <small>{group.title}</small>
                      </button>
                    );
                  })}
                </React.Fragment>
              ))}
            </div>
          </div>
        )}
        <button className="primary full" type="submit" disabled={busy || !query.trim()}>
          {busy ? <Loader2 className="spin" size={16} /> : useAi ? <Send size={16} /> : <Search size={16} />}
          {useAi ? "Ask sources" : "Search sources"}
        </button>
      </form>
      {error && <div className="inline-error">{error}</div>}
      <div className="result-list">
        {results.map((result) => (
          <article key={result.id} className="result-card">
            <label className="result-select">
              <input
                type="checkbox"
                checked={selectedResultIds.includes(result.id)}
                onChange={() => toggleResult(result)}
              />
              <span>
                <strong>{result.title}</strong>
                <p>{result.snippet}</p>
                <small>{result.sourceLabel}{result.citation ? ` · ${result.citation}` : ""}</small>
              </span>
            </label>
          </article>
        ))}
      </div>
    </div>
  );
}

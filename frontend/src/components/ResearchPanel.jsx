import React, { useState } from "react";
import { Loader2, Search, Upload } from "lucide-react";

import { api } from "../api/client.js";

export function ResearchPanel({ matter, sources, onResults }) {
  const [query, setQuery] = useState("habitability disputed rent rental assistance");
  const [selectedKinds, setSelectedKinds] = useState([]);
  const [results, setResults] = useState([]);
  const [selectedResultIds, setSelectedResultIds] = useState([]);
  const [resources, setResources] = useState([]);
  const [resourceTitle, setResourceTitle] = useState("");
  const [resourceType, setResourceType] = useState("case");
  const [resourceFile, setResourceFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
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

  function toggleKind(kind) {
    setSelectedKinds((current) => current.includes(kind) ? current.filter((item) => item !== kind) : [...current, kind]);
  }

  async function runSearch() {
    setBusy(true);
    setError("");
    try {
      const response = await api.research({
        query,
        matterId: matter?.id,
        jurisdiction: matter?.jurisdiction,
        sourceKinds: selectedKinds.length ? selectedKinds : undefined,
      });
      setResults(response.results);
      setSelectedResultIds(response.results.map((result) => result.id));
      onResults(response.results);
    } catch (err) {
      setError(err.message || "Source search failed.");
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
      event.currentTarget.reset();
    } catch (err) {
      setError(err.message || "Reference upload failed.");
    } finally {
      setUploadBusy(false);
    }
  }

  return (
    <div className="panel">
      <form className="reference-upload-form" onSubmit={uploadResource}>
        <div className="reference-upload-grid">
          <label className="field">
            <span>Private reference</span>
            <input value={resourceTitle} onChange={(event) => setResourceTitle(event.target.value)} placeholder="Title, optional" />
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
        {resources.length > 0 && (
          <div className="reference-list">
            {resources.slice(0, 4).map((resource) => (
              <small key={resource.id}>{resource.title} · {resource.resourceType}</small>
            ))}
          </div>
        )}
      </form>
      <label className="field">
        <span>Query</span>
        <input value={query} onChange={(event) => setQuery(event.target.value)} />
      </label>
      <div className="source-toggles">
        {sources.map((source) => (
          <button
            key={source.kind}
            className={selectedKinds.includes(source.kind) ? "selected" : ""}
            onClick={() => toggleKind(source.kind)}
          >
            {source.label}
          </button>
        ))}
      </div>
      <button className="primary full" disabled={busy} onClick={runSearch}>
        {busy ? <Loader2 className="spin" size={16} /> : <Search size={16} />}
        Search sources
      </button>
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

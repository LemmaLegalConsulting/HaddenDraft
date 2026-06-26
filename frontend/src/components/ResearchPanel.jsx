import React, { useState } from "react";
import { Loader2, Search } from "lucide-react";

import { api } from "../api/client.js";

export function ResearchPanel({ matter, sources, onResults }) {
  const [query, setQuery] = useState("habitability disputed rent rental assistance");
  const [selectedKinds, setSelectedKinds] = useState([]);
  const [results, setResults] = useState([]);
  const [selectedResultIds, setSelectedResultIds] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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

  return (
    <div className="panel">
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

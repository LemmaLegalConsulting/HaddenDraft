import React, { useEffect, useMemo, useState } from "react";
import { Check, FileSearch, FileText, Loader2, Plus, Search, TextSelect, X } from "lucide-react";

import { api } from "../api/client.js";

function citationForFact(fact) {
  return fact.source || fact.citation || "Case record";
}

function curatedId(prefix, value) {
  return `${prefix}:${value}`.replace(/\s+/g, "-").toLowerCase();
}

export function FactReview({ matter, facts, selectedFactIds, selectedCuratedFacts, onFactChange, onCuratedChange }) {
  const [documents, setDocuments] = useState([]);
  const [documentState, setDocumentState] = useState({});
  const [searchTerms, setSearchTerms] = useState({});
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!matter?.id) {
      setDocuments([]);
      return;
    }
    setLoadingDocuments(true);
    setError("");
    api.caseDocuments(matter.id)
      .then((response) => setDocuments(response.documents || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoadingDocuments(false));
  }, [matter?.id]);

  const selectedCuratedIds = useMemo(
    () => new Set((selectedCuratedFacts || []).map((fact) => fact.id)),
    [selectedCuratedFacts],
  );

  function toggleMatterFact(fact) {
    if (selectedFactIds.includes(fact.id)) {
      onFactChange(selectedFactIds.filter((factId) => factId !== fact.id));
      return;
    }
    onFactChange([...selectedFactIds, fact.id]);
  }

  function toggleCuratedFact(fact) {
    if (selectedCuratedIds.has(fact.id)) {
      onCuratedChange(selectedCuratedFacts.filter((item) => item.id !== fact.id));
      return;
    }
    onCuratedChange([...selectedCuratedFacts, fact]);
  }

  async function loadContext(document, level, extra = {}) {
    setDocumentState((current) => ({
      ...current,
      [document.id]: { ...(current[document.id] || {}), loading: level, error: "" },
    }));
    try {
      const response = await api.caseDocumentContext(matter.id, document.id, { level, ...extra });
      setDocumentState((current) => ({
        ...current,
        [document.id]: { ...(current[document.id] || {}), ...response, activeLevel: level, loading: "" },
      }));
    } catch (err) {
      setDocumentState((current) => ({
        ...current,
        [document.id]: { ...(current[document.id] || {}), error: err.message, loading: "" },
      }));
    }
  }

  function addDocumentSummary(document, state) {
    const text = state.summary || document.snippet;
    if (!text) return;
    toggleCuratedFact({
      id: curatedId("summary", document.id),
      category: document.kind === "case_note" ? "case_note" : "document_summary",
      title: document.title,
      text,
      source: document.source,
      citation: document.citation,
      sourceDocumentId: document.id,
      sourceExcerpt: text,
    });
  }

  function addChunkFact(document, chunk) {
    toggleCuratedFact({
      id: curatedId("chunk", `${document.id}-${chunk.id}`),
      category: document.kind === "case_note" ? "case_note" : "document_excerpt",
      title: `${document.title}, excerpt ${chunk.index}`,
      text: chunk.text,
      source: document.source,
      citation: `${document.citation || document.title}, excerpt ${chunk.index}`,
      sourceDocumentId: document.id,
      sourceExcerpt: chunk.text,
    });
  }

  return (
    <div className="facts-workflow">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Facts</p>
            <h3>Candidate facts</h3>
          </div>
        </div>
        <div className="check-list">
          {facts.map((fact) => (
            <label key={fact.id} className="check-row fact-with-citation" title={citationForFact(fact)}>
              <input type="checkbox" checked={selectedFactIds.includes(fact.id)} onChange={() => toggleMatterFact(fact)} />
              <span>
                <strong>{fact.title}</strong>
                <em>{fact.text}</em>
                <small>{fact.source} · {fact.confidence}</small>
              </span>
            </label>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Documents</p>
            <h3>Context curation</h3>
          </div>
          {loadingDocuments ? <Loader2 className="spin" size={18} /> : <FileSearch size={18} />}
        </div>
        {error && <div className="inline-error">{error}</div>}
        <div className="document-list">
          {documents.map((document) => {
            const state = documentState[document.id] || {};
            const summarySelected = selectedCuratedIds.has(curatedId("summary", document.id));
            return (
              <article className="document-card" key={document.id}>
                <div className="document-card-heading">
                  <div>
                    <strong>{document.title}</strong>
                    <small>{document.kind === "case_note" ? "Case note" : document.source} · {document.citation}</small>
                  </div>
                  {document.kind === "case_note" ? <TextSelect size={18} /> : <FileText size={18} />}
                </div>
                {(document.snippet || state.summary) && (
                  <p className="document-snippet">{state.summary || document.snippet}</p>
                )}
                <div className="button-row compact document-actions">
                  <button className="secondary" type="button" onClick={() => loadContext(document, "summary")} disabled={state.loading}>
                    {state.loading === "summary" ? <Loader2 className="spin" size={16} /> : <FileText size={16} />} Summary
                  </button>
                  <button className="secondary" type="button" onClick={() => loadContext(document, "chunks")} disabled={state.loading}>
                    {state.loading === "chunks" ? <Loader2 className="spin" size={16} /> : <TextSelect size={16} />} Chunks
                  </button>
                  <button className="secondary" type="button" onClick={() => loadContext(document, "full")} disabled={state.loading}>
                    {state.loading === "full" ? <Loader2 className="spin" size={16} /> : <FileSearch size={16} />} Full
                  </button>
                  <button className={summarySelected ? "primary" : "secondary"} type="button" onClick={() => addDocumentSummary(document, state)} disabled={!(state.summary || document.snippet)}>
                    {summarySelected ? <Check size={16} /> : <Plus size={16} />} Use summary
                  </button>
                </div>
                <form
                  className="document-search"
                  onSubmit={(event) => {
                    event.preventDefault();
                    loadContext(document, "search", { query: searchTerms[document.id] || "" });
                  }}
                >
                  <input
                    value={searchTerms[document.id] || ""}
                    onChange={(event) => setSearchTerms((current) => ({ ...current, [document.id]: event.target.value }))}
                    placeholder="Search for disability, repairs, notice, payments..."
                  />
                  <button className="secondary icon-button" aria-label="Search document" disabled={state.loading}>
                    <Search size={16} />
                  </button>
                </form>
                {state.error && <div className="inline-error">{state.error}</div>}
                {state.text && <pre className="document-full-text">{state.text}</pre>}
                {state.chunks?.length > 0 && (
                  <div className="chunk-list">
                    {state.chunks.map((chunk) => {
                      const chunkSelected = selectedCuratedIds.has(curatedId("chunk", `${document.id}-${chunk.id}`));
                      return (
                        <div className="chunk-row fact-with-citation" key={chunk.id} title={`${document.citation || document.title}, excerpt ${chunk.index}`}>
                          <p>{chunk.text}</p>
                          <button className={chunkSelected ? "primary" : "secondary"} type="button" onClick={() => addChunkFact(document, chunk)}>
                            {chunkSelected ? <X size={16} /> : <Plus size={16} />} {chunkSelected ? "Remove" : "Use"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <section className="panel curated-facts-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Selected context</p>
            <h3>Facts allowed for drafting</h3>
          </div>
        </div>
        <div className="curated-fact-list">
          {selectedCuratedFacts.length === 0 && <p className="muted">No document-derived facts selected.</p>}
          {selectedCuratedFacts.map((fact) => (
            <div className="curated-fact fact-with-citation" key={fact.id} title={fact.sourceExcerpt || fact.citation || fact.source}>
              <span>
                <strong>{fact.title}</strong>
                <em>{fact.text}</em>
                <small>{fact.citation || fact.source}</small>
              </span>
              <button className="secondary icon-button" aria-label="Remove fact" onClick={() => toggleCuratedFact(fact)}>
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

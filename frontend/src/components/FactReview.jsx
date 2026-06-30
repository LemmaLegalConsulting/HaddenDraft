import React, { useEffect, useMemo, useState } from "react";
import { Check, FileText, Loader2, Plus, Search, TextSelect, Upload, X } from "lucide-react";

import { api } from "../api/client.js";

function citationForFact(fact) {
  return fact.source || fact.citation || "Case record";
}

function curatedId(prefix, value) {
  return `${prefix}:${value}`.replace(/\s+/g, "-").toLowerCase();
}

export function FactReview({ matter, facts, selectedFactIds, selectedCuratedFacts, onFactChange, onCuratedChange, onMatterChange }) {
  const [documents, setDocuments] = useState([]);
  const [documentState, setDocumentState] = useState({});
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [addingFact, setAddingFact] = useState(false);
  const [uploadingFact, setUploadingFact] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState("fact");
  const [newFact, setNewFact] = useState({ title: "", text: "", source: "" });
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!matter?.id) {
      setDocuments([]);
      return;
    }
    setLoadingDocuments(true);
    setError("");
    Promise.all([api.caseDocuments(matter.id), api.caseDetail(matter.id)])
      .then(([documentResponse, caseResponse]) => {
        setDocuments(documentResponse.documents || []);
        onMatterChange?.(caseResponse.case);
      })
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

  function mergeSelectedFactIds(ids) {
    onFactChange([...new Set([...(selectedFactIds || []), ...(ids || [])])]);
  }

  async function submitTypedFact(event) {
    event.preventDefault();
    if (!matter?.id || !newFact.text.trim()) return;
    setAddingFact(true);
    setError("");
    try {
      const response = await api.createCaseFact(matter.id, newFact);
      onMatterChange?.(response.case);
      mergeSelectedFactIds((response.created || []).map((fact) => fact.id));
      setNewFact({ title: "", text: "", source: "" });
      setModalOpen(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setAddingFact(false);
    }
  }

  async function submitUploadedFact(event) {
    event.preventDefault();
    if (!matter?.id || !uploadFile) return;
    setUploadingFact(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      if (uploadTitle.trim()) formData.append("title", uploadTitle.trim());
      const response = await api.uploadCaseFactDocument(matter.id, formData);
      onMatterChange?.(response.case);
      mergeSelectedFactIds((response.created || []).map((fact) => fact.id));
      setUploadTitle("");
      setUploadFile(null);
      event.currentTarget.reset();
      setModalOpen(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploadingFact(false);
    }
  }

  async function inspectDocument(document) {
    setDocumentState((current) => ({
      ...current,
      [document.id]: { ...(current[document.id] || {}), loading: true, error: "" },
    }));
    try {
      const response = await api.caseDocumentContext(matter.id, document.id, {
        level: "search",
        query: "notice rent payment repair disability assistance hearing deadline bankruptcy debtor relief",
        limit: 5,
      });
      setDocumentState((current) => ({
        ...current,
        [document.id]: { ...(current[document.id] || {}), ...response, loading: false },
      }));
    } catch (err) {
      setDocumentState((current) => ({
        ...current,
        [document.id]: { ...(current[document.id] || {}), error: err.message, loading: false },
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
    <div className="facts-review-stack">
      <section className="panel">
        <div className="step-guidance">
          <span className="block-kicker">Fact selection</span>
          <h3>Confirm the facts the draft may use</h3>
          <p>
            Suggested facts are selected by the AI from case facts and document text. Add facts manually only when the case file is missing something important.
          </p>
        </div>
        <div className="button-row panel-actions">
          <button className="secondary" type="button" onClick={() => setModalOpen(true)}>
            <Plus size={16} /> Add fact or document
          </button>
          <span className="muted-inline">{selectedFactIds.length + selectedCuratedFacts.length} selected</span>
        </div>
        {error && <div className="inline-error">{error}</div>}
        <div className="check-list">
          {facts.length === 0 && <p className="muted">No saved case facts yet. Use the page-level “Refresh AI fact suggestions” action to search documents, or add a fact manually.</p>}
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
        <div className="document-card-heading">
          <div>
            <strong>Case documents and notes</strong>
            <small>The AI searches these automatically during fact review. Inspect a document only if you want to manually select a specific excerpt.</small>
          </div>
          {loadingDocuments && <Loader2 className="spin" size={18} />}
        </div>
        <div className="document-list">
          {documents.length === 0 && <p className="muted">No source documents available for this case.</p>}
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
                {(document.snippet || state.summary) && <p className="document-snippet">{state.summary || document.snippet}</p>}
                <div className="button-row compact document-actions">
                  <button className="secondary" type="button" onClick={() => inspectDocument(document)} disabled={state.loading}>
                    {state.loading ? <Loader2 className="spin" size={16} /> : <Search size={16} />} Inspect candidate excerpts
                  </button>
                  <button className={summarySelected ? "primary" : "secondary"} type="button" onClick={() => addDocumentSummary(document, state)} disabled={!(state.summary || document.snippet)}>
                    {summarySelected ? <Check size={16} /> : <Plus size={16} />} {summarySelected ? "Selected summary" : "Use summary"}
                  </button>
                </div>
                {state.error && <div className="inline-error">{state.error}</div>}
                {state.chunks?.length > 0 && (
                  <div className="chunk-list">
                    {state.chunks.map((chunk) => {
                      const chunkSelected = selectedCuratedIds.has(curatedId("chunk", `${document.id}-${chunk.id}`));
                      return (
                        <div className="chunk-row fact-with-citation" key={chunk.id} title={`${document.citation || document.title}, excerpt ${chunk.index}`}>
                          <p>{chunk.text}</p>
                          <button className={chunkSelected ? "primary" : "secondary"} type="button" onClick={() => addChunkFact(document, chunk)}>
                            {chunkSelected ? <X size={16} /> : <Plus size={16} />} {chunkSelected ? "Remove" : "Use excerpt"}
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
        <div className="curated-fact-list">
          {selectedCuratedFacts.length === 0 && <p className="muted">No document excerpts selected manually.</p>}
          {selectedCuratedFacts.map((fact) => (
            <div className="curated-fact-row" key={fact.id}>
              <div>
                <strong>{fact.title}</strong>
                <p>{fact.text}</p>
                <small>{fact.citation || fact.source}</small>
              </div>
              <button className="secondary icon-button" type="button" aria-label="Remove selected document fact" onClick={() => toggleCuratedFact(fact)}>
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      </section>

      {modalOpen && (
        <div className="modal-backdrop" role="presentation">
          <div className="profile-modal" role="dialog" aria-modal="true" aria-label="Add fact or source document">
            <div className="modal-heading">
              <div>
                <h4>Add a fact or document</h4>
                <p className="modal-subtitle">Use this only when the case file is missing a fact the draft needs.</p>
              </div>
              <button className="btn btn-outline-secondary icon-button" type="button" onClick={() => setModalOpen(false)} title="Close">
                <X size={16} />
              </button>
            </div>
            <div className="draft-mode-switch">
              <button className={modalMode === "fact" ? "selected" : ""} type="button" onClick={() => setModalMode("fact")}>Type fact</button>
              <button className={modalMode === "upload" ? "selected" : ""} type="button" onClick={() => setModalMode("upload")}>Upload document</button>
            </div>
            {modalMode === "fact" ? (
              <form className="fact-entry-form" onSubmit={submitTypedFact}>
                <label className="field"><span>Title</span><input value={newFact.title} onChange={(event) => setNewFact((current) => ({ ...current, title: event.target.value }))} placeholder="Repair request, payment, notice problem..." /></label>
                <label className="field"><span>Fact text</span><textarea value={newFact.text} onChange={(event) => setNewFact((current) => ({ ...current, text: event.target.value }))} placeholder="Type a fact that should be available for drafting." rows={4} /></label>
                <label className="field"><span>Source</span><input value={newFact.source} onChange={(event) => setNewFact((current) => ({ ...current, source: event.target.value }))} placeholder="Client update, intake call, advocate note..." /></label>
                <button className="primary" type="submit" disabled={!newFact.text.trim() || addingFact}>{addingFact ? <Loader2 className="spin" size={16} /> : <Plus size={16} />} Add and select</button>
              </form>
            ) : (
              <form className="fact-upload-form" onSubmit={submitUploadedFact}>
                <label className="field"><span>Upload source document</span><input type="file" accept=".txt,.md,.csv,.json,.html,.htm,.docx,.pdf,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setUploadFile(event.target.files?.[0] || null)} /></label>
                <label className="field"><span>Fact title</span><input value={uploadTitle} onChange={(event) => setUploadTitle(event.target.value)} placeholder="Optional title for the extracted text" /></label>
                <button className="secondary" type="submit" disabled={!uploadFile || uploadingFact}>{uploadingFact ? <Loader2 className="spin" size={16} /> : <Upload size={16} />} Extract and select</button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

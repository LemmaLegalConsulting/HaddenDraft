import React, { useEffect, useMemo, useState } from "react";
import { Check, Eye, FileText, Loader2, Plus, Search, TextSelect } from "lucide-react";

import { api } from "../api/client.js";
import { CaseDocumentPreviewModal } from "./CaseDocumentPreviewModal.jsx";
import { caseDocumentPreviewKind } from "./casePresentation.js";

function sourceLabel(item) {
  return item.citation || item.source || item.title || "Case material";
}

export function CaseMaterialsPanel({ matter, selectedFactIds = [], onFactIdsAdded, onMatterChange, readOnly = false, embedded = false }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [materials, setMaterials] = useState(null);
  const [contextById, setContextById] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [previewDocument, setPreviewDocument] = useState(null);

  useEffect(() => {
    if (!matter?.id) {
      setMaterials(null);
      return;
    }
    setActiveTab("overview");
    setContextById({});
    setPreviewDocument(null);
    setMaterials(null);
    setBusy(true);
    setError("");
    let cancelled = false;
    api.caseMaterials(matter.id)
      .then((response) => { if (!cancelled) setMaterials(response); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [matter?.id]);

  const selected = useMemo(() => new Set(selectedFactIds), [selectedFactIds]);

  async function refreshMatter(created = []) {
    const response = await api.caseDetail(matter.id);
    onMatterChange?.(response.case);
    onFactIdsAdded?.(created.map((fact) => fact.id));
    const materialResponse = await api.caseMaterials(matter.id);
    setMaterials(materialResponse);
  }

  async function addDraftingFact({ title, text, source }) {
    if (!text?.trim()) return;
    setBusy(true);
    setError("");
    try {
      const response = await api.createCaseFact(matter.id, { title, text, source });
      await refreshMatter(response.created || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function loadContext(item, level = "search") {
    setContextById((current) => ({ ...current, [item.id]: { ...(current[item.id] || {}), loading: true, error: "" } }));
    try {
      const response = await api.caseDocumentContext(matter.id, item.id, {
        level,
        query: "notice rent payment repair disability assistance hearing deadline subsidy voucher conditions relief",
        limit: 5,
      });
      setContextById((current) => ({
        ...current,
        [item.id]: {
          ...(current[item.id] || {}),
          ...response,
          loading: false,
          expanded: level === "full" ? true : current[item.id]?.expanded,
        },
      }));
    } catch (err) {
      setContextById((current) => ({ ...current, [item.id]: { ...(current[item.id] || {}), loading: false, error: err.message } }));
    }
  }

  if (!matter) return null;
  const summary = materials?.summary || {};
  const notes = materials?.notes || [];
  const documents = materials?.documents || [];
  const customFields = materials?.customFields || [];
  const draftingFacts = materials?.draftingFacts || matter.facts || [];
  const materialTabs = [
    ["overview", "Overview"],
    ["notes", `Case notes (${summary.noteCount || 0})`],
    ["documents", `Documents (${summary.documentCount || 0})`],
    ["fields", `Custom fields (${summary.customFieldCount || 0})`],
    ["facts", `Drafting facts (${summary.draftingFactCount || 0})`],
  ];

  function toggleDocumentText(item) {
    const state = contextById[item.id] || {};
    if (!state.text) {
      loadContext(item, "full");
      return;
    }
    setContextById((current) => ({
      ...current,
      [item.id]: { ...current[item.id], expanded: !current[item.id]?.expanded },
    }));
  }

  function MaterialCard({ item, type }) {
    const state = contextById[item.id] || {};
    const isNote = type === "note";
    const attachments = item.attachedDocuments || [];
    const previewKind = caseDocumentPreviewKind(item);
    return (
      <article className="document-card">
        <div className="document-card-heading">
          <div>
            <strong>{item.title}</strong>
            <small>{isNote ? `Case note · ${item.date || item.citation || matter.id}` : `${item.source || "Document"} · ${item.filename || item.citation || ""}`}</small>
          </div>
          {isNote ? <TextSelect size={18} /> : <FileText size={18} />}
        </div>
        {isNote && item.text && <p className="case-note-text">{item.text}</p>}
        {!isNote && item.snippet && <p className="document-snippet">{item.snippet}</p>}
        {attachments.length > 0 && (
          <div className="chunk-list">
            <strong>Attached documents</strong>
            {attachments.map((attachment) => <p key={attachment.id}>{attachment.filename || attachment.title}</p>)}
          </div>
        )}
        {item.isWebhookDocumentNotice && !attachments.length && (
          <p className="muted">This note says documents were received, but no attached document metadata was returned by LegalServer. Try refreshing case documents.</p>
        )}
        {(!isNote || !readOnly) && <div className="button-row compact document-actions">
          {!isNote && previewKind && item.hasFile && <button className="btn btn-outline-secondary" type="button" onClick={() => setPreviewDocument(item)}>
              <Eye size={16} /> Preview {previewKind === "pdf" ? "PDF" : "image"}
            </button>}
          {!isNote && (!previewKind || !item.hasFile) && <button className="btn btn-outline-secondary" type="button" onClick={() => toggleDocumentText(item)} disabled={state.loading}>
            {state.loading ? <Loader2 className="spin" size={16} /> : <FileText size={16} />}
            {state.loading ? "Loading document text" : state.text && state.expanded ? "Hide document text" : state.text ? "Show document text" : "Load document text"}
          </button>}
          {!readOnly && <button className="btn btn-outline-secondary" type="button" onClick={() => loadContext(item, "search")} disabled={state.loading}>
              {state.loading ? <Loader2 className="spin" size={16} /> : <Search size={16} />} Find useful excerpts
            </button>}
          {!readOnly && <button className="btn btn-outline-secondary" type="button" disabled={busy || !(state.summary || item.snippet)} onClick={() => addDraftingFact({ title: item.title, text: state.summary || item.snippet, source: sourceLabel(item) })}>
              <Plus size={16} /> Add summary to drafting facts
            </button>}
        </div>}
        {!isNote && state.text && state.expanded && <div className="document-full-text"><strong>Document text</strong><p>{state.text}</p></div>}
        {state.error && <div className="inline-error">{state.error}</div>}
        {!readOnly && state.chunks?.length > 0 && (
          <div className="chunk-list">
            {state.chunks.map((chunk) => (
              <div className="chunk-row" key={chunk.id}>
                <p>{chunk.text}</p>
                {!readOnly && <button className="btn btn-outline-secondary" type="button" disabled={busy} onClick={() => addDraftingFact({ title: `${item.title}, excerpt ${chunk.index}`, text: chunk.text, source: `${sourceLabel(item)}, excerpt ${chunk.index}` })}>
                    <Plus size={16} /> Add excerpt to drafting facts
                  </button>}
              </div>
            ))}
          </div>
        )}
      </article>
    );
  }

  return (
    <section className={`${embedded ? "case-materials-embedded" : "panel"} case-materials-panel`}>
      <div className="document-card-heading">
        <div>
          <strong>Case materials</strong>
          <small>{readOnly ? "Review the notes, documents, and case data available to the drafting tool." : "Drafting facts are statements selected from the case record that the AI can rely on when drafting."}</small>
        </div>
        {busy && <Loader2 className="spin" size={18} />}
      </div>
      {error && <div className="inline-error">{error}</div>}
      <div className="support-tabs">
        {materialTabs.map(([id, label]) => (
          <button key={id} className={activeTab === id ? "selected" : ""} type="button" onClick={() => setActiveTab(id)}>{label}</button>
        ))}
      </div>

      {busy && !materials && <p className="muted">Loading case notes and documents…</p>}
      {activeTab === "overview" && (
        <div className="case-materials-overview">
          <div className="selected-support-summary">
            <strong>{summary.noteCount || 0} case notes</strong>
            <strong>{summary.documentCount || 0} documents</strong>
            <strong>{summary.customFieldCount || 0} custom fields with values</strong>
            <strong>{summary.draftingFactCount || 0} drafting facts selected</strong>
            {!readOnly && <p>Notes, documents, and custom fields are source materials. Add useful summaries, excerpts, or field values to drafting facts when they should be used in a draft.</p>}
          </div>
          {materials && (
            <div className="case-material-index">
              <section>
                <div className="case-material-index-heading"><h4>Case notes</h4><button className="text-link-button" type="button" onClick={() => setActiveTab("notes")}>Explore notes</button></div>
                {notes.length ? <ul>{notes.map((item) => <li key={item.id}><TextSelect size={15} /><span><strong>{item.title}</strong>{item.date && <small>{item.date}</small>}</span></li>)}</ul> : <p className="muted">No case notes were returned.</p>}
              </section>
              <section>
                <div className="case-material-index-heading"><h4>Documents</h4><button className="text-link-button" type="button" onClick={() => setActiveTab("documents")}>Explore documents</button></div>
                {documents.length ? <ul>{documents.map((item) => <li key={item.id}><FileText size={15} /><span><strong>{item.title}</strong>{(item.filename || item.source) && <small>{item.filename || item.source}</small>}</span></li>)}</ul> : <p className="muted">No case documents were returned.</p>}
              </section>
            </div>
          )}
        </div>
      )}
      {activeTab === "notes" && <div className="document-list">{notes.length ? notes.map((item) => <MaterialCard key={item.id} item={item} type="note" />) : <p className="muted">No case notes were returned.</p>}</div>}
      {activeTab === "documents" && <div className="document-list">{documents.length ? documents.map((item) => <MaterialCard key={item.id} item={item} type="document" />) : <p className="muted">No case documents were returned.</p>}</div>}
      {activeTab === "fields" && (
        customFields.length ? <dl className="custom-field-list">{customFields.map((field) => (
          <div key={field.key}>
            <dt>{field.label}</dt>
            <dd>
              <span className="custom-field-value">{field.value}</span>
              {!readOnly && <button className="text-link-button" type="button" disabled={busy || !field.value} onClick={() => addDraftingFact({ title: field.label, text: field.value, source: `Custom field: ${field.label}` })}>
                  <Plus size={14} /> Add to drafting facts
                </button>}
            </dd>
          </div>
        ))}</dl> : <p className="muted">No custom fields with values were found.</p>
      )}
      {activeTab === "facts" && (
        <div className="check-list">
          {!draftingFacts.length && <p className="muted">No drafting facts selected yet. Review case notes, documents, or custom fields and add useful summaries or excerpts.</p>}
          {draftingFacts.map((fact) => (
            <div key={fact.id} className="check-row fact-with-citation">
              {selected.has(fact.id) ? <Check size={16} /> : <Plus size={16} />}
              <span><strong>{fact.title}</strong><em>{fact.text}</em><small>{fact.source}</small></span>
            </div>
          ))}
        </div>
      )}
      <CaseDocumentPreviewModal matterId={matter.id} document={previewDocument} onClose={() => setPreviewDocument(null)} />
    </section>
  );
}

import React, { useEffect, useMemo, useState } from "react";
import { Check, ClipboardList, FileText, Loader2, Plus, Search, TextSelect } from "lucide-react";

import { api } from "../api/client.js";

const tabs = [
  ["overview", "Overview"],
  ["notes", "Notes"],
  ["documents", "Documents"],
  ["fields", "Custom Fields"],
  ["facts", "Drafting Facts"],
];

function sourceLabel(item) {
  return item.citation || item.source || item.title || "Case material";
}

export function CaseMaterialsPanel({ matter, selectedFactIds = [], onFactIdsAdded, onMatterChange }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [materials, setMaterials] = useState(null);
  const [contextById, setContextById] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!matter?.id) {
      setMaterials(null);
      return;
    }
    setBusy(true);
    setError("");
    api.caseMaterials(matter.id)
      .then(setMaterials)
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false));
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
      setContextById((current) => ({ ...current, [item.id]: { ...(current[item.id] || {}), ...response, loading: false } }));
    } catch (err) {
      setContextById((current) => ({ ...current, [item.id]: { ...(current[item.id] || {}), loading: false, error: err.message } }));
    }
  }

  async function fetchField(field) {
    setBusy(true);
    setError("");
    try {
      const response = await api.fetchCustomFields(matter.id, {
        fieldKeys: [field.key],
        reason: "Need full custom field value for drafting facts.",
      });
      setMaterials((current) => current ? { ...current, customFields: response.fields?.length ? response.fields : current.customFields } : current);
      if (response.errors?.length) setError(response.errors.join(" "));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!matter) return null;
  const summary = materials?.summary || {};
  const notes = materials?.notes || [];
  const documents = materials?.documents || [];
  const customFields = materials?.customFields || [];
  const draftingFacts = materials?.draftingFacts || matter.facts || [];

  function MaterialCard({ item, type }) {
    const state = contextById[item.id] || {};
    const isNote = type === "note";
    const attachments = item.attachedDocuments || [];
    return (
      <article className="document-card">
        <div className="document-card-heading">
          <div>
            <strong>{item.title}</strong>
            <small>{isNote ? `Case note · ${item.date || item.citation || matter.id}` : `${item.source || "Document"} · ${item.filename || item.citation || ""}`}</small>
          </div>
          {isNote ? <TextSelect size={18} /> : <FileText size={18} />}
        </div>
        {item.isWebhookDocumentNotice ? (
          <p className="document-snippet">This note was created by a document webhook. It may not contain useful narrative text, but it may have attached documents.</p>
        ) : (
          item.snippet && <p className="document-snippet">{item.snippet}</p>
        )}
        {attachments.length > 0 && (
          <div className="chunk-list">
            <strong>Attached documents</strong>
            {attachments.map((attachment) => <p key={attachment.id}>{attachment.filename || attachment.title}</p>)}
          </div>
        )}
        {item.isWebhookDocumentNotice && !attachments.length && (
          <p className="muted">This note says documents were received, but no attached document metadata was returned by LegalServer. Try refreshing case documents.</p>
        )}
        <div className="button-row compact document-actions">
          <button className="secondary" type="button" onClick={() => loadContext(item, "full")} disabled={state.loading}>
            {state.loading ? <Loader2 className="spin" size={16} /> : <FileText size={16} />} View full text
          </button>
          <button className="secondary" type="button" onClick={() => loadContext(item, "search")} disabled={state.loading}>
            {state.loading ? <Loader2 className="spin" size={16} /> : <Search size={16} />} Find useful excerpts
          </button>
          <button className="secondary" type="button" disabled={busy || !(state.summary || item.snippet)} onClick={() => addDraftingFact({ title: item.title, text: state.summary || item.snippet, source: sourceLabel(item) })}>
            <Plus size={16} /> Add summary to drafting facts
          </button>
        </div>
        {state.text && <p className="document-snippet">{state.text}</p>}
        {state.error && <div className="inline-error">{state.error}</div>}
        {state.chunks?.length > 0 && (
          <div className="chunk-list">
            {state.chunks.map((chunk) => (
              <div className="chunk-row" key={chunk.id}>
                <p>{chunk.text}</p>
                <button className="secondary" type="button" disabled={busy} onClick={() => addDraftingFact({ title: `${item.title}, excerpt ${chunk.index}`, text: chunk.text, source: `${sourceLabel(item)}, excerpt ${chunk.index}` })}>
                  <Plus size={16} /> Add excerpt to drafting facts
                </button>
              </div>
            ))}
          </div>
        )}
      </article>
    );
  }

  return (
    <section className="panel case-materials-panel">
      <div className="document-card-heading">
        <div>
          <strong>Case materials</strong>
          <small>Drafting facts are statements selected from the case record that the AI can rely on when drafting.</small>
        </div>
        {busy && <Loader2 className="spin" size={18} />}
      </div>
      {error && <div className="inline-error">{error}</div>}
      <div className="support-tabs">
        {tabs.map(([id, label]) => (
          <button key={id} className={activeTab === id ? "selected" : ""} type="button" onClick={() => setActiveTab(id)}>{label}</button>
        ))}
      </div>

      {activeTab === "overview" && (
        <div className="selected-support-summary">
          <strong>{summary.noteCount || 0} case notes</strong>
          <strong>{summary.documentCount || 0} documents</strong>
          <strong>{summary.customFieldCount || 0} custom fields with values</strong>
          <strong>{summary.draftingFactCount || 0} drafting facts selected</strong>
          <p>Notes, documents, and custom fields are source materials. Add useful summaries, excerpts, or field values to drafting facts when they should be used in a draft.</p>
        </div>
      )}
      {activeTab === "notes" && <div className="document-list">{notes.length ? notes.map((item) => <MaterialCard key={item.id} item={item} type="note" />) : <p className="muted">No case notes were returned.</p>}</div>}
      {activeTab === "documents" && <div className="document-list">{documents.length ? documents.map((item) => <MaterialCard key={item.id} item={item} type="document" />) : <p className="muted">No case documents were returned.</p>}</div>}
      {activeTab === "fields" && (
        <div className="document-list">
          {customFields.length ? customFields.map((field) => (
            <article className="document-card" key={field.key}>
              <div className="document-card-heading"><div><strong>{field.label}</strong><small>{field.category} · {field.confidence}</small></div><ClipboardList size={18} /></div>
              <p className="document-snippet">{field.valuePreview || field.value}</p>
              <small>{field.reason}</small>
              <div className="button-row compact document-actions">
                <button className="secondary" type="button" onClick={() => fetchField(field)}>Fetch full value</button>
                <button className="secondary" type="button" disabled={busy || !field.value} onClick={() => addDraftingFact({ title: field.label, text: field.value, source: `Custom field: ${field.label}` })}>
                  <Plus size={16} /> Add value to drafting facts
                </button>
              </div>
            </article>
          )) : <p className="muted">No custom fields with values were found.</p>}
        </div>
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
    </section>
  );
}

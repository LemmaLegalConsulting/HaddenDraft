import React, { useEffect, useRef, useState } from "react";
import { useTemplateFill } from "../hooks/useTemplateFill.js";
import { canShowInline, contextPieces, fieldLabel, fieldStatus, fieldText, fillSummary, groupFields, nextBlankKey } from "./templateFill.js";
import LegalServerSaveToggle from "./LegalServerSaveToggle.jsx";
import FillPreview from "./FillPreview.jsx";
import { useFillPreview } from "../hooks/useFillPreview.js";

function FieldControl({ field, id, value, onChange, describedBy, singleLine = false }) {
  if (field.kind === "boolean") {
    return <select id={id} className="form-select" value={value} onChange={onChange} aria-describedby={describedBy}>
      <option value="false">Do not include</option>
      <option value="true">Include</option>
    </select>;
  }
  if (field.choices?.length) {
    return <select id={id} className="form-select" value={value} onChange={onChange} aria-describedby={describedBy}>
      {field.choices.map((choice) => <option value={choice} key={choice}>{choice.replaceAll("_", " ")}</option>)}
    </select>;
  }
  if (singleLine && field.kind === "text" && !value.includes("\n")) {
    return <input id={id} className="form-control" value={value} onChange={onChange} aria-describedby={describedBy} />;
  }
  const rows = ["json", "multiline"].includes(field.kind) ? 4 : 1;
  return <textarea id={id} className="form-control" rows={rows} value={value} onChange={onChange} aria-describedby={describedBy} />;
}

function helpFor(field) {
  return field.kind === "json" ? "Enter a JSON list or object. Use [] for no entries."
    : field.kind === "control" ? "Enter a JSON value: true, false, a number, or text in double quotes." : "";
}

// Editing one blank from the preview. The answer goes into the same unsaved
// edits as the field list, so both views and the save button agree.
function FieldDialog({ field, fields, edits, nextKey, onApply, onClose }) {
  const dialog = useRef(null);
  const [draft, setDraft] = useState(() => Object.hasOwn(edits, field.key) ? edits[field.key] : fieldText(field));
  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal?.();
    return () => element?.open && element.close();
  }, []);
  const id = `fill-dialog-${field.key}`;
  const apply = (next) => { onApply(field.key, draft, next); };
  const help = helpFor(field);
  return <dialog ref={dialog} className="fill-dialog" aria-labelledby={`${id}-title`} onCancel={(event) => { event.preventDefault(); onClose(); }}>
    <form method="dialog" onSubmit={(event) => { event.preventDefault(); apply(nextKey); }}>
      <label className="fill-dialog-title" id={`${id}-title`} htmlFor={id}>{fieldLabel(field)}</label>
      <FieldContext pieces={contextPieces(field, fields, { ...edits, [field.key]: draft })} />
      <FieldControl field={field} id={id} value={draft} onChange={(event) => setDraft(event.target.value)} describedBy={help ? `${id}-help` : undefined} singleLine />
      {help && <p className="fill-field-meta" id={`${id}-help`}>{help}</p>}
      {field.reason && <p className="fill-field-meta">{field.reason}</p>}
      <p className="fill-field-meta">{draft === "" ? (field.required || ["json", "control"].includes(field.kind) ? "Leaving this blank stops the DOCX from being prepared." : "Left blank, this becomes a highlighted prompt in Word.") : "Not saved until you select Save progress or Prepare DOCX."}</p>
      <div className="button-row">
        <button type="button" className="btn btn-light" onClick={onClose}>Cancel</button>
        <button type="button" className={nextKey ? "btn btn-light" : "btn btn-primary"} onClick={() => apply(null)}>Done</button>
        {nextKey && <button type="submit" className="btn btn-primary">Next blank</button>}
      </div>
    </form>
  </dialog>;
}

function FieldContext({ pieces }) {
  if (!pieces.length) return null;
  return <p className="fill-field-context">
    {pieces.map((piece, index) => piece.kind === "break" ? <br key={index} />
      : piece.kind === "text" ? <React.Fragment key={index}>{piece.text}</React.Fragment>
      : <span key={index} className={`fill-slot fill-slot-${piece.kind}`}>{piece.text}</span>)}
  </p>;
}

const INLINE_KEY = "templateFill.inline";

function readInline() {
  try { return globalThis.localStorage?.getItem(INLINE_KEY) !== "off"; } catch { return true; }
}

function writeInline(on) {
  try { globalThis.localStorage?.setItem(INLINE_KEY, on ? "on" : "off"); } catch { /* the choice just is not remembered */ }
}

function FieldMeta({ id, status, source, field, help }) {
  return <p className="fill-field-meta" id={id}>
    <span className={`fill-status fill-status-${status.tone}`}>{status.label}</span>
    {source && <span>{source}</span>}
    {field.reason && <span>{field.reason}</span>}
    {help && <span>{help}</span>}
  </p>;
}

// The sentence itself, with the text box where the blank is. A field used twice
// in one sentence gets one box; the other use mirrors what is typed.
function InlineSentence({ pieces, id, value, onChange, describedBy }) {
  let boxed = false;
  return <p className="fill-inline-sentence">
    {pieces.map((piece, index) => {
      if (piece.kind === "break") return <br key={index} />;
      if (piece.kind === "text") return <React.Fragment key={index}>{piece.text}</React.Fragment>;
      if (piece.kind === "this" && !boxed) {
        boxed = true;
        return <input key={index} id={id} className="form-control fill-inline-input" value={value} onChange={onChange} aria-describedby={describedBy} style={{ width: `${Math.max(12, value.length + 3)}ch` }} />;
      }
      return <span key={index} className={`fill-slot fill-slot-${piece.kind}`}>{piece.text}</span>;
    })}
  </p>;
}

function FillField({ field, fields, edits, setEdits, inline }) {
  const id = `fill-field-${field.key}`;
  const value = Object.hasOwn(edits, field.key) ? edits[field.key] : fieldText(field);
  const status = fieldStatus(field, edits);
  const change = (event) => setEdits((current) => ({ ...current, [field.key]: event.target.value }));
  const help = helpFor(field);
  const source = field.state === "manual" || status.tone === "edited" ? "Your entry" : field.source;
  if (inline && canShowInline(field)) {
    return <div className={`fill-field fill-field-inline fill-field-${status.tone}`}>
      <label htmlFor={id}>{fieldLabel(field)}</label>
      <InlineSentence pieces={contextPieces(field, fields, edits)} id={id} value={value} onChange={change} describedBy={`${id}-meta`} />
      <FieldMeta id={`${id}-meta`} status={status} source={source} field={field} help={help} />
    </div>;
  }
  return <div className={`fill-field fill-field-${status.tone}`}>
    <div className="fill-field-label">
      <label htmlFor={id}>{fieldLabel(field)}</label>
      <FieldContext pieces={contextPieces(field, fields, edits)} />
    </div>
    <div className="fill-field-input">
      <FieldControl field={field} id={id} value={value} onChange={change} describedBy={`${id}-meta`} />
      <FieldMeta id={`${id}-meta`} status={status} source={source} field={field} help={help} />
    </div>
  </div>;
}

// `route` is what the URL names ({ sessionId, jobId, view }); `onNavigate`
// moves the URL. The fields/preview tab is part of the address.
export default function TemplateFillPanel({ matter, authorProfile, legalserverSave, account = "", route = {}, onNavigate }) {
  const matterId = matter?.externalId || matter?.id || "";
  const caseKey = matter?.routeCaseKey || matterId;
  const fill = useTemplateFill(matterId, authorProfile, legalserverSave, { account, caseKey, route, navigate: onNavigate });
  const [selected, setSelected] = useState("");
  const [inline, setInline] = useState(readInline);
  const view = route.view === "preview" ? "preview" : "fields";
  const setView = (next) => fill.session && onNavigate?.({ sessionId: fill.session.id, view: next });
  const preview = useFillPreview(fill.session, fill.edits, view === "preview");
  if (!matterId) return <section className="panel"><h2>Fill template — no AI</h2><p>Select a case first.</p></section>;
  const selectedTemplate = fill.catalog.templates.find((template) => `${template.type}:${template.id}` === selected);
  const summary = fill.session ? fillSummary(fill.session.fields, fill.edits) : null;
  const [editing, setEditing] = useState(null);
  const editingField = fill.session?.fields.find((field) => field.key === editing);
  const applyDialog = (key, value, next) => {
    fill.setEdits((current) => {
      const saved = fieldText(fill.session.fields.find((field) => field.key === key));
      if (value === saved) { const { [key]: _discard, ...rest } = current; return rest; }
      return { ...current, [key]: value };
    });
    setEditing(next);
  };
  return <section className="panel template-fill-panel">
    <h2>Fill template — no AI</h2>
    <p className="muted">Review values from LegalServer, fill in anything else you know, and finish in Word or another editor.</p>
    {fill.error && <p role="alert" className="inline-error">{fill.error}</p>}
    {fill.busy && <p role="status" className="muted">{fill.busy}</p>}
    {fill.notice && <p role="status" className="fill-notice">{fill.notice}</p>}
    {fill.sessionMissing && <div className="empty-state compact-empty" role="status">
      <strong className="empty-state-title">This saved work is not available</strong>
      <p>No fill-template session with this number belongs to this case. Nothing else is opened in its place.</p>
      <button type="button" className="btn btn-primary" onClick={() => onNavigate?.({})}>Choose a template</button>
    </div>}

    <fieldset className="fill-card" disabled={Boolean(fill.busy)}>
      <legend>Choose a template</legend>
      <label className="fill-label" htmlFor="fill-template-select">Library and case templates</label>
      <div className="fill-inline">
        <select id="fill-template-select" className="form-select" value={selected} onChange={(event) => setSelected(event.target.value)}>
          <option value="">Select a template</option>
          {fill.catalog.templates.map((template) => <option key={`${template.type}:${template.id}`} value={`${template.type}:${template.id}`}>{template.title}{template.type === "upload" && !template.shared ? " (this case)" : ""}</option>)}
        </select>
        <button type="button" className="btn btn-primary" disabled={!selectedTemplate} onClick={() => fill.start(selectedTemplate)}>Use template</button>
      </div>
      <label className="field"><span>Or upload a DOCX template (up to 15 MB)</span>
        <input className="form-control" type="file" accept=".docx" onChange={(event) => { fill.upload(event.target.files?.[0]); event.target.value = ""; }} />
      </label>
      <details className="disclosure">
        <summary>What an uploaded template can contain</summary>
        <div className="disclosure-body">
          <p>Mark the blanks with bracketed prompts, underscores, highlighting, or supported Jinja fields. Uploads stay with this case until an administrator reviews and shares them.</p>
        </div>
      </details>
      {fill.catalog.sessions.length > 0 && <label className="field"><span>Resume saved work</span>
        <select className="form-select" value={fill.session?.id || ""} onChange={(event) => event.target.value && fill.resume(event.target.value)}>
          <option value="">Select saved work</option>
          {fill.catalog.sessions.map((session) => <option key={session.id} value={session.id}>{session.title} — {new Date(session.updatedAt).toLocaleString()}</option>)}
        </select>
      </label>}
    </fieldset>

    {fill.session && <fieldset className="fill-card" disabled={Boolean(fill.busy)}>
      <legend>{fill.session.title}</legend>
      <ul className="fill-summary" aria-label="Field summary">
        <li className="fill-status fill-status-filled">{summary.filled} filled</li>
        <li className="fill-status fill-status-blank">{summary.blank} blank — prompts in Word</li>
        {summary.needed > 0 && <li className="fill-status fill-status-needed">{summary.needed} needed before download</li>}
      </ul>
      <div className="fill-view-tabs" role="tablist" aria-label="Fill template view">
        <button type="button" role="tab" aria-selected={view === "fields"} className={view === "fields" ? "selected" : ""} onClick={() => setView("fields")}>Fill in blanks</button>
        <button type="button" role="tab" aria-selected={view === "preview"} className={view === "preview" ? "selected" : ""} onClick={() => setView("preview")}>Preview</button>
      </div>
      {view === "preview" && <FillPreview {...preview} onEdit={setEditing} fields={fill.session.fields} />}
      {editingField && <FieldDialog key={editingField.key} field={editingField} fields={fill.session.fields} edits={fill.edits}
        nextKey={nextBlankKey(preview.preview, editingField.key)} onApply={applyDialog} onClose={() => setEditing(null)} />}
      {view === "fields" && <>
      <label className="fill-inline-toggle">
        <input type="checkbox" className="form-check-input" checked={inline} onChange={(event) => { setInline(event.target.checked); writeInline(event.target.checked); }} />
        Type short blanks inside their sentence
      </label>
      {groupFields(fill.session.fields).map((group) => <section className="fill-group" key={group.id} aria-labelledby={`fill-group-${group.id}`}>
        <h3 id={`fill-group-${group.id}`}>{group.title} <span className="fill-group-count">{group.fields.length}</span></h3>
        <p className="muted">{group.note}</p>
        {group.fields.map((field) => <FillField key={field.key} field={field} fields={fill.session.fields} edits={fill.edits} setEdits={fill.setEdits} inline={inline} />)}
      </section>)}
      </>}
      <div className="fill-export">
        <LegalServerSaveToggle kind="documents" checked={fill.saveToLegalServer} onChange={fill.setSaveToLegalServer} bootstrapSave={legalserverSave} delivery={fill.completed?.result?.delivery} />
        {fill.completed && <p className="muted">The download has the values from when you last prepared it. After editing, prepare it again.</p>}
      </div>
      <div className="fill-actions">
        <p role="status" className={summary.edited ? "fill-unsaved" : "muted"}>{summary.edited ? `${summary.edited} unsaved ${summary.edited === 1 ? "change" : "changes"} — save before leaving this workspace.` : "All changes saved."}</p>
        <div className="button-row">
          <button type="button" className="btn btn-light" onClick={() => fill.save(false)}>Save progress</button>
          <button type="button" className="btn btn-light" onClick={() => fill.resume(fill.session.id, { discardEdits: true })}>Reload saved values</button>
          <button type="button" className="btn btn-primary" onClick={() => fill.save(true)}>Prepare DOCX</button>
          {fill.completed && <button type="button" className="btn btn-success" onClick={fill.download}>Download prepared DOCX</button>}
        </div>
      </div>
    </fieldset>}
  </section>;
}

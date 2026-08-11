import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ArrowDown, ArrowUp, Download, Sparkles } from "lucide-react";

import { api } from "../api/client";
import { DraftEditor } from "../editor/DraftEditor.jsx";
import { DocumentHistoryPanel } from "./DocumentHistoryPanel.jsx";
import {
  applyRecommendations,
  estimatePages,
  groupByTopic,
  moveSection,
  readingGradeLabel,
  reviewWarnings,
  selectedSections,
  toggleSection,
} from "./adviceLetter";

const CONDITIONS = [
  { key: "hearing_scheduled", label: "Hearing is scheduled" },
  { key: "has_3_day_notice", label: "Has a 3-day notice" },
  { key: "has_complaint", label: "Has the complaint" },
  { key: "is_subsidized", label: "Subsidized housing" },
  { key: "has_voucher", label: "Has a voucher" },
  { key: "is_month_to_month", label: "Month-to-month tenancy" },
  { key: "judgment_entered", label: "Judgment already entered" },
  { key: "magistrate_decision", label: "Magistrate decided the case" },
  { key: "has_conditions_issues", label: "Conditions/repairs problem" },
  { key: "client_not_named", label: "Client is not a named defendant" },
  { key: "rent_paid_after_notice", label: "Rent accepted after the notice" },
  { key: "voucher_terminated", label: "Voucher terminated" },
  { key: "admission_denied", label: "Denied for subsidized housing" },
];

export function AdviceLetterPanel({ matter, authorProfile }) {
  const [catalog, setCatalog] = useState(null);
  const [region, setRegion] = useState("CLE");
  const [selected, setSelected] = useState([]);
  const [conditions, setConditions] = useState({});
  const [goal, setGoal] = useState("");
  const [recommendations, setRecommendations] = useState([]);
  const [preview, setPreview] = useState(null);
  const [draft, setDraft] = useState(null);
  const [draftDirty, setDraftDirty] = useState(false);
  const [letterFields, setLetterFields] = useState({
    recipientName: "",
    recipientAddress: "",
    subject: "",
    filename: "",
    letterDate: new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }),
  });
  // Once the advocate types a name, stop overwriting it with a suggestion.
  const [filenameEdited, setFilenameEdited] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const draftRef = useRef(null);
  const letterFieldsRef = useRef(letterFields);
  const filenameEditedRef = useRef(filenameEdited);
  const goalRef = useRef(goal);
  const conditionsRef = useRef(conditions);
  const draftDirtyRef = useRef(false);

  letterFieldsRef.current = letterFields;
  filenameEditedRef.current = filenameEdited;
  goalRef.current = goal;
  conditionsRef.current = conditions;
  draftDirtyRef.current = draftDirty;

  const sections = catalog?.sections || [];
  const matterId = matter?.externalId || matter?.id || "";

  function setActiveDraft(nextDraft) {
    draftRef.current = nextDraft;
    setDraft(nextDraft);
    if (nextDraft) {
      setPreview((current) => {
        if (!current) return current;
        const paragraphs = (nextDraft.sections || []).flatMap((section) =>
          (section.body || "").split("\n").map((line) => line.trim()).filter(Boolean),
        );
        return { ...current, paragraphs, body: paragraphs.join("\n") };
      });
    }
  }

  useEffect(() => {
    draftRef.current = null;
    setDraft(null);
    setDraftDirty(false);
    setPreview(null);
    setSelected([]);
  }, [matterId]);

  useEffect(() => {
    let cancelled = false;
    api
      .adviceLetterSections({ region })
      .then((data) => {
        if (!cancelled) setCatalog(data);
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [region]);

  // The case already knows who the letter goes to; making the advocate retype
  // it is how a letter ends up addressed to "[Client]".
  useEffect(() => {
    if (!matterId) return undefined;
    let cancelled = false;
    api
      .adviceLetterAddressing(matterId)
      .then(({ addressing }) => {
        if (cancelled) return;
        setLetterFields((current) => ({
          ...current,
          recipientName: current.recipientName || addressing.recipientName || "",
          recipientAddress: current.recipientAddress || addressing.recipientAddress || "",
          subject: current.subject || addressing.caseReference || "",
        }));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [matterId]);

  const runPreview = useCallback(
    async (slugs) => {
      if (!slugs.length) {
        setPreview(null);
        setDraft(null);
        return;
      }
      try {
        const data = await api.adviceLetterDraft({
          matterId,
          sectionSlugs: slugs,
          authorProfile,
          goal: goalRef.current,
          conditions: conditionsRef.current,
          includeWrapper: true,
          letterFields: letterFieldsRef.current,
          draftId: draftRef.current?.id,
          currentSections: draftRef.current?.sections,
          currentEditorState: draftRef.current?.editorState,
        });
        setActiveDraft(data.draft);
        setDraftDirty(false);
        setPreview(data.letter);
        // Keep the suggestion in step with the sections chosen so far, unless
        // the advocate has renamed it themselves.
        if (!filenameEditedRef.current) {
          setLetterFields((current) => ({
            ...current,
            ...(data.letterFields || {}),
            filename: data.letter.suggestedFilename || current.filename,
          }));
        }
      } catch (err) {
        setError(err.message);
      }
    },
    [matterId, authorProfile],
  );

  useEffect(() => {
    runPreview(selected);
  }, [selected, runPreview]);

  async function suggest() {
    if (!matter) {
      setError("Select a case first.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const data = await api.adviceLetterRecommendations({
        matterId: matter.externalId || matter.id,
        goal,
        conditions,
        region,
      });
      setRecommendations(data.recommendations);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    setBusy(true);
    setError("");
    try {
      let currentDraft = draftRef.current;
      if (!currentDraft) throw new Error("Choose at least one section first.");
      if (draftDirtyRef.current) {
        const saved = await api.updateDraft(currentDraft.id, {
          sections: currentDraft.sections,
          plainText: currentDraft.plainText,
          editorState: currentDraft.editorState,
        });
        currentDraft = saved.draft;
        setActiveDraft(currentDraft);
        setDraftDirty(false);
      }
      const response = await api.adviceLetterDraftExport(currentDraft.id, {
        authorProfile,
        letterFields: letterFieldsRef.current,
      });
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") || "";
      const named = /filename="([^"]+)"/.exec(disposition);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = named ? named[1] : letterFields.filename || "advice-letter.docx";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function persistDraft() {
    const currentDraft = draftRef.current;
    if (!currentDraft || !draftDirtyRef.current) return currentDraft;
    setBusy(true);
    setError("");
    try {
      const response = await api.updateDraft(currentDraft.id, {
        sections: currentDraft.sections,
        plainText: currentDraft.plainText,
        editorState: currentDraft.editorState,
      });
      setActiveDraft(response.draft);
      setDraftDirty(false);
      return response.draft;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function redraftBlock(blockKey, instruction = "") {
    if (!draftRef.current) return;
    setBusy(true);
    setError("");
    try {
      const response = await api.regenerateDraftBlock(draftRef.current.id, blockKey, { instruction });
      setActiveDraft(response.draft);
      setDraftDirty(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function fillMissingField(_fieldKey, _value, sections, plainText, editorState) {
    const currentDraft = draftRef.current;
    if (!currentDraft) return;
    setBusy(true);
    setError("");
    try {
      const response = await api.updateDraft(currentDraft.id, {
        sections,
        plainText,
        editorState,
      });
      setActiveDraft(response.draft);
      setDraftDirty(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function handleDraftChange(sections, plainText, editorState) {
    const current = draftRef.current;
    if (!current) return;
    setActiveDraft({ ...current, sections, plainText, editorState });
    setDraftDirty(true);
  }

  const grouped = useMemo(() => groupByTopic(sections), [sections]);
  const chosen = useMemo(() => selectedSections(selected, sections), [selected, sections]);
  const warnings = useMemo(() => reviewWarnings(selected, sections), [selected, sections]);
  const pages = estimatePages(preview?.readability);

  return (
    <div className="advice-letter-panel">
      <header className="panel-header">
        <h3>Client advice letter</h3>
        <p className="muted">
          Pick the sections that fit this tenant. They appear in the letter in the order you
          choose them, on your organization&rsquo;s letterhead.
        </p>
      </header>

      {error && <p className="error-text">{error}</p>}

      <div className="field-row">
        <label className="field">
          <span>Region</span>
          <select className="form-select" value={region} onChange={(event) => setRegion(event.target.value)}>
            <option value="">Anywhere</option>
            <option value="CLE">Cleveland</option>
            <option value="NEO">Northeast Ohio</option>
          </select>
        </label>
        <label className="field grow">
          <span>What is this letter about?</span>
          <input className="form-control"
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            placeholder="e.g. the 3-day notice names a different landlord than the complaint"
          />
        </label>
      </div>

      <details className="advice-conditions">
        <summary>What is true about this case? ({Object.values(conditions).filter(Boolean).length} set)</summary>
        <div className="condition-grid">
          {CONDITIONS.map((condition) => (
            <label key={condition.key} className="checkbox">
              <input
                type="checkbox"
                checked={Boolean(conditions[condition.key])}
                onChange={(event) =>
                  setConditions({ ...conditions, [condition.key]: event.target.checked })
                }
              />
              <span>{condition.label}</span>
            </label>
          ))}
        </div>
      </details>

      <div className="panel-actions">
        <button type="button" className="btn btn-outline-secondary" onClick={suggest} disabled={busy}>
          <Sparkles size={14} /> Suggest sections
        </button>
        {recommendations.length > 0 && (
          <button
            type="button"
            onClick={() => setSelected(applyRecommendations(selected, recommendations))}
          >
            Add all {recommendations.filter((entry) => entry.score > 0).length} suggestions
          </button>
        )}
      </div>
      {!draft && selected.length === 0 && (
        <p className="muted advice-editor-hint">
          Choose a section under <strong>All sections</strong>, or use <strong>Suggest sections</strong>,
          to open the rich-text editor.
        </p>
      )}

      {recommendations.length > 0 && (
        <section className="advice-recommendations">
          <h4>Suggested for this case</h4>
          {recommendations.map((entry) => (
            <div key={entry.section.slug} className="recommendation">
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={selected.includes(entry.section.slug)}
                  onChange={() => setSelected(toggleSection(selected, entry.section.slug))}
                />
                <span>
                  <strong>{entry.section.title}</strong>{" "}
                  <em className="muted">score {entry.score}</em>
                  {entry.needsReview && (
                    <span className="review-badge" title={entry.reviewReason}>
                      <AlertTriangle size={12} /> needs review
                    </span>
                  )}
                </span>
              </label>
              <ul className="reasons">
                {entry.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}

      <section className="advice-catalog">
        <h4>All sections</h4>
        {grouped.map((group) => (
          <div key={group.topic} className="advice-topic">
            <h5>{group.topic}</h5>
            {group.sections.map((section) => (
              <label key={section.slug} className="checkbox">
                <input
                  type="checkbox"
                  checked={selected.includes(section.slug)}
                  onChange={() => setSelected(toggleSection(selected, section.slug))}
                />
                <span>
                  {section.title}
                  {section.summary && <small className="muted"> &mdash; {section.summary}</small>}
                  {section.needsReview && (
                    <span className="review-badge" title={section.reviewReason}>
                      <AlertTriangle size={12} /> needs review
                    </span>
                  )}
                </span>
              </label>
            ))}
          </div>
        ))}
      </section>

      {chosen.length > 0 && (
        <section className="advice-order">
          <h4>Letter order</h4>
          <ol>
            {chosen.map((section, index) => (
              <li key={section.slug}>
                <span>{section.title}</span>
                <span className="order-buttons">
                  <button
                    type="button"
                    className="icon-button"
                    disabled={index === 0}
                    onClick={() => setSelected(moveSection(selected, section.slug, -1))}
                    title="Move up"
                  >
                    <ArrowUp size={14} />
                  </button>
                  <button
                    type="button"
                    className="icon-button"
                    disabled={index === chosen.length - 1}
                    onClick={() => setSelected(moveSection(selected, section.slug, 1))}
                    title="Move down"
                  >
                    <ArrowDown size={14} />
                  </button>
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {warnings.length > 0 && (
        <section className="advice-warnings">
          <h4>
            <AlertTriangle size={14} /> Read these before sending
          </h4>
          <ul>
            {warnings.map((warning) => (
              <li key={warning.slug}>
                <strong>{warning.title}:</strong> {warning.reason}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="advice-send">
        <h4>Addressing</h4>
        <div className="field-row">
          <label className="field">
            <span>Recipient</span>
            <input className="form-control"
              value={letterFields.recipientName}
              onChange={(event) =>
                setLetterFields({ ...letterFields, recipientName: event.target.value })
              }
            />
          </label>
          <label className="field">
            <span>Date</span>
            <input className="form-control"
              value={letterFields.letterDate}
              onChange={(event) =>
                setLetterFields({ ...letterFields, letterDate: event.target.value })
              }
            />
          </label>
        </div>
        <label className="field">
          <span>Address</span>
          <textarea className="form-control"
            rows={2}
            value={letterFields.recipientAddress}
            onChange={(event) =>
              setLetterFields({ ...letterFields, recipientAddress: event.target.value })
            }
          />
        </label>
        <label className="field">
          <span>File name</span>
          <input className="form-control"
            value={letterFields.filename}
            onChange={(event) => {
              setFilenameEdited(true);
              setLetterFields({ ...letterFields, filename: event.target.value });
            }}
            placeholder="2026-08-02-garcia-robert-advice-letter-security-deposit"
          />
        </label>
        <label className="field">
          <span>Re:</span>
          <input className="form-control"
            value={letterFields.subject}
            onChange={(event) => setLetterFields({ ...letterFields, subject: event.target.value })}
          />
        </label>
        <button type="button" onClick={download} disabled={busy || !draft}>
          <Download size={14} /> Download letter
        </button>
      </section>

      {draft && (
        <section className="advice-editor-section">
          <h4>Edit the letter</h4>
          <p className="muted">
            {readingGradeLabel(preview?.readability)}
            {pages !== null && ` · about ${pages} page(s)`}
          </p>
          <DraftEditor
            draft={draft}
            busy={busy}
            onChange={handleDraftChange}
            onPersist={persistDraft}
            onRegenerateBlock={redraftBlock}
            onFillMissingField={fillMissingField}
          />
          <DocumentHistoryPanel
            draft={draft}
            busy={busy}
            onDraftRestored={(restored) => {
              setActiveDraft(restored);
              setDraftDirty(false);
            }}
          />
        </section>
      )}
    </div>
  );
}

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bot, Database, ExternalLink, Filter, Loader2, Search, X } from "lucide-react";

import { api } from "../api/client.js";
import {
  EMPTY_SEARCH,
  EXPANSION_MODES,
  activeFilterChips,
  aiStatus,
  buildSearchRequest,
  clearFilters,
  expansionStatus,
  indexStatusLine,
  pageOffsets,
  resultMetaLine,
  resultWarnings,
  snippetSegments,
  toggleFilterValue,
} from "./researchSearch.js";
import { CitationPreviewModal, MarkdownResponse, SourceBrowserModal } from "./MarkdownResponse.jsx";

const PAGE_SIZE = 20;

/** A result carries everything the source viewer needs; this is the same shape. */
function citationFor(result) {
  return {
    id: result.id,
    title: result.title,
    snippet: result.snippet,
    sourceKind: result.open?.kind === "caselaw" ? "local_cases" : "rag",
    sourceLabel: result.corpusLabel,
    citation: result.citation,
    url: result.url,
    metadata: result.metadata,
  };
}

function Snippet({ result }) {
  const segments = useMemo(
    () => snippetSegments(result.snippet, result.snippetMatches || []),
    [result.snippet, result.snippetMatches],
  );
  return (
    <p className="research-snippet">
      {segments.map((segment, index) =>
        segment.kind ? (
          <mark key={index} className={`research-match research-match-${segment.kind}`}>{segment.text}</mark>
        ) : (
          <React.Fragment key={index}>{segment.text}</React.Fragment>
        ),
      )}
    </p>
  );
}

export function ResearchSearch({ matter, onOpenSource }) {
  const [state, setState] = useState(EMPTY_SEARCH);
  const [draft, setDraft] = useState("");
  const [payload, setPayload] = useState(null);
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [previewCitation, setPreviewCitation] = useState(null);
  const [openSource, setOpenSource] = useState(null);
  const run = useRef(0);

  useEffect(() => {
    let cancelled = false;
    api.researchSearchStatus()
      .then((response) => { if (!cancelled) setStatus(response); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const search = useCallback(async (next) => {
    if (!next.query.trim()) return;
    const ticket = ++run.current;
    setBusy(true);
    setError("");
    try {
      const response = await api.researchSearch(
        buildSearchRequest(next, { matterId: matter?.id, limit: PAGE_SIZE }),
      );
      // A slower earlier search must not overwrite a faster later one.
      if (ticket !== run.current) return;
      setPayload(response);
    } catch (err) {
      if (ticket === run.current) setError(err.message || "The search could not be run.");
    } finally {
      if (ticket === run.current) setBusy(false);
    }
  }, [matter?.id]);

  function apply(next) {
    setState(next);
    search(next);
  }

  function submit(event) {
    event.preventDefault();
    apply({ ...state, query: draft, filters: {}, corpora: [], offset: 0 });
  }

  const ai = aiStatus(payload?.ai);
  const expansion = expansionStatus(payload?.expansion);
  const chips = activeFilterChips(state, payload?.facets || [], payload?.filters);
  const paging = pageOffsets(payload?.total || 0, payload?.limit || PAGE_SIZE, payload?.offset || 0);
  const learnedReady = status?.expansion?.distributional?.available;
  const aiAvailable = status?.ai?.available;

  return (
    <div className="research-search">
      <form className="research-search-form" onSubmit={submit}>
        <label className="field">
          <span>Search the corpus</span>
          <div className="research-search-input">
            <input
              className="form-control"
              value={draft}
              placeholder='"notice to leave the premises", R.C. 5321.04, court:cleveland'
              onChange={(event) => setDraft(event.target.value)}
            />
            <button className="btn btn-primary" type="submit" disabled={busy || !draft.trim()}>
              {busy ? <Loader2 className="spin" size={16} /> : <Search size={16} />} Search
            </button>
          </div>
        </label>
        <ul className="research-syntax-help">
          {(status?.querySyntax || []).map((item) => (
            <li key={item.example}><code>{item.example}</code> {item.description}</li>
          ))}
          {!status?.querySyntax?.length && (
            <li>Quote a phrase to require it. Type a citation to find the authority itself.</li>
          )}
        </ul>

        <details className="disclosure">
          <summary>
            Search options
            <span className="disclosure-summary">
              {EXPANSION_MODES.find((mode) => mode.id === state.expansion)?.label}
              {state.aiRerank || state.aiSynthesis ? " · AI on" : " · no AI"}
            </span>
          </summary>
          <div className="disclosure-body">
            <fieldset className="research-option-group">
              <legend>Which words are searched for</legend>
              {EXPANSION_MODES.map((mode) => (
                <label key={mode.id} className="research-option">
                  <input
                    type="radio"
                    name="research-expansion"
                    checked={state.expansion === mode.id}
                    disabled={mode.id !== "none" && mode.id !== "thesaurus" && !learnedReady}
                    onChange={() => apply({ ...state, expansion: mode.id, offset: 0 })}
                  />
                  <span>
                    {mode.label}
                    <small>
                      {mode.description}
                      {(mode.id === "distributional" || mode.id === "all") && !learnedReady
                        ? ` ${status?.expansion?.distributional?.reason || ""}`
                        : ""}
                    </small>
                  </span>
                </label>
              ))}
            </fieldset>
            <fieldset className="research-option-group">
              <legend>Generative AI</legend>
              <p className="field-help">
                Searching never calls a model. These add a model on top of the results, and every search says
                whether one ran.
              </p>
              <label className="research-option">
                <input
                  type="checkbox"
                  checked={state.aiRerank}
                  disabled={!aiAvailable}
                  onChange={(event) => apply({ ...state, aiRerank: event.target.checked, offset: 0 })}
                />
                <span>Let a model reorder the first page<small>Ranking below the first page stays deterministic. Nothing is removed.</small></span>
              </label>
              <label className="research-option">
                <input
                  type="checkbox"
                  checked={state.aiSynthesis}
                  disabled={!aiAvailable}
                  onChange={(event) => apply({ ...state, aiSynthesis: event.target.checked, offset: 0 })}
                />
                <span>Write a cited summary of the results<small>The summary is written by a model and is not part of the corpus.</small></span>
              </label>
              {!aiAvailable && status?.ai?.reason && <p className="field-help">{status.ai.reason}</p>}
            </fieldset>
          </div>
        </details>
      </form>

      {error && <div className="inline-error">{error}</div>}

      {payload && (
        <>
          <div className={`research-ai-banner research-ai-${ai.tone}`} role="status">
            {ai.tone === "deterministic" ? <Database size={16} aria-hidden="true" /> : <Bot size={16} aria-hidden="true" />}
            <span>
              <strong>{ai.headline}</strong>
              {ai.detail && <small>{ai.detail}</small>}
            </span>
          </div>

          <p className="research-result-count">
            {payload.total.toLocaleString()} result{payload.total === 1 ? "" : "s"}
            {payload.total ? ` · showing ${paging.from}–${paging.to}` : ""}
            {` · ${payload.tookMs} ms`}
          </p>

          {payload.query?.warnings?.map((warning) => (
            <p key={warning} className="research-note research-note-warn">{warning}</p>
          ))}
          {payload.unmatched?.map((item) => (
            <p key={`${item.kind}-${item.value}`} className="research-note research-note-warn">
              No source in this corpus contains the {item.kind} “{item.value}”.
            </p>
          ))}
          {expansion.unavailable && <p className="research-note research-note-warn">{expansion.unavailable}</p>}

          <details className="disclosure">
            <summary>
              How this search was run
              <span className="disclosure-summary">{expansion.summary}</span>
            </summary>
            <div className="disclosure-body">
              <p>{indexStatusLine(payload.index)}</p>
              {payload.coverage?.note && <p>{payload.coverage.note}</p>}
              {expansion.terms.length > 0 && (
                <ul className="research-expansion-list">
                  {expansion.terms.map((item) => (
                    <li key={`${item.from}-${item.term}-${item.basis}`}>
                      <b>{item.from}</b> → {item.term}
                      <small>
                        {item.basis === "thesaurus"
                          ? `Reviewed thesaurus${item.note ? `: ${item.note}` : ""} (${item.verification})`
                          : "Learned from this corpus, not reviewed"}
                      </small>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </details>

          {payload.ai?.synthesis?.applied && payload.ai.synthesis.answer && (
            <section className="research-synthesis" aria-label="AI summary">
              <p className="research-synthesis-label"><Bot size={14} aria-hidden="true" /> Written by a model from the results below</p>
              <MarkdownResponse content={payload.ai.synthesis.answer} citations={payload.results} />
            </section>
          )}

          {chips.length > 0 && (
            <div className="research-active-filters">
              <span className="jurisdiction-narrowing-label"><Filter size={13} aria-hidden="true" /> Narrowed to</span>
              {chips.map((chip) =>
                chip.removable ? (
                  <button
                    key={`${chip.field}-${chip.value}`}
                    type="button"
                    className="jurisdiction-chip active"
                    onClick={() => apply(toggleFilterValue(state, chip.field, chip.value))}
                  >
                    {chip.label} <X size={12} aria-hidden="true" />
                  </button>
                ) : (
                  <span
                    key={`${chip.field}-${chip.value}`}
                    className="jurisdiction-chip active research-chip-typed"
                    title="Typed into the query. Edit the query to remove it."
                  >
                    {chip.label}
                  </span>
                ),
              )}
              {chips.some((chip) => chip.removable) && (
                <button type="button" className="text-link-button" onClick={() => apply(clearFilters(state))}>
                  Clear all
                </button>
              )}
            </div>
          )}

          <div className="research-results-layout">
            <aside className="research-facets" aria-label="Narrow these results">
              {(payload.facets || [])
                .filter((facet) => facet.values.length > 1 || facet.selected.length)
                .map((facet) => (
                  <details key={facet.field} className="disclosure" open={facet.selected.length > 0}>
                    <summary>
                      {facet.label}
                      <span className="disclosure-summary">
                        {facet.selected.length
                          ? `${facet.selected.length} selected`
                          : `${facet.values.length} option${facet.values.length === 1 ? "" : "s"}`}
                      </span>
                    </summary>
                    <div className="disclosure-body research-facet-values">
                      {facet.values.slice(0, 20).map((value) => (
                        <button
                          key={value.value}
                          type="button"
                          className={`jurisdiction-chip ${facet.selected.includes(value.value) ? "active" : ""}`}
                          aria-pressed={facet.selected.includes(value.value)}
                          onClick={() => apply(toggleFilterValue(state, facet.field, value.value))}
                        >
                          {value.label} <span className="jurisdiction-chip-count">{value.count}</span>
                        </button>
                      ))}
                      {facet.unattributed > 0 && (
                        <small className="research-facet-unattributed">
                          {facet.unattributed} result{facet.unattributed === 1 ? "" : "s"} record no {facet.label.toLowerCase()}.
                        </small>
                      )}
                    </div>
                  </details>
                ))}
            </aside>

            <div className="result-list">
              {payload.results.map((result) => {
                const warnings = resultWarnings(result);
                return (
                  <article key={result.id} className="result-card">
                    <h4 className="research-result-title">{result.title}</h4>
                    <p className="research-result-meta">{resultMetaLine(result)}</p>
                    {result.citation && <p className="research-result-citation">{result.citation}</p>}
                    <Snippet result={result} />
                    {result.passages?.length > 0 && (
                      <p className="research-result-passages">
                        Also matched in {result.passages.map((passage) => passage.label).join(", ")}.
                      </p>
                    )}
                    {warnings.map((warning) => (
                      <p key={warning} className="research-note research-note-warn">{warning}</p>
                    ))}
                    <div className="result-source-actions">
                      <button className="text-link-button" type="button" onClick={() => setPreviewCitation(citationFor(result))}>
                        Preview
                      </button>
                      <button
                        className="text-link-button"
                        type="button"
                        onClick={() => (onOpenSource || setOpenSource)(citationFor(result))}
                      >
                        <ExternalLink size={14} aria-hidden="true" /> Open the source
                      </button>
                    </div>
                  </article>
                );
              })}
              {!payload.results.length && !busy && (
                <p className="research-note">
                  Nothing in the corpus matched. Try fewer words, or turn off the exact phrase.
                </p>
              )}
              {(paging.hasPrevious || paging.hasNext) && (
                <div className="research-paging">
                  <button
                    className="btn btn-light"
                    type="button"
                    disabled={!paging.hasPrevious || busy}
                    onClick={() => apply({ ...state, offset: paging.previous })}
                  >
                    Previous
                  </button>
                  <button
                    className="btn btn-light"
                    type="button"
                    disabled={!paging.hasNext || busy}
                    onClick={() => apply({ ...state, offset: paging.next })}
                  >
                    Next
                  </button>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {!payload && status && <p className="research-note">{indexStatusLine(status.index)}</p>}

      <CitationPreviewModal citation={previewCitation} onClose={() => setPreviewCitation(null)} />
      {!onOpenSource && <SourceBrowserModal citation={openSource} onClose={() => setOpenSource(null)} />}
    </div>
  );
}

import React, { useEffect, useMemo, useState } from "react";
import { Database, Loader2, RefreshCw } from "lucide-react";

const PURPOSE_ORDER = ["legal_authority", "example_language", "background_reference"];

function groupCandidates(candidates) {
  return candidates.reduce((groups, candidate) => {
    const key = candidate.purpose || "background_reference";
    groups[key] = groups[key] || [];
    groups[key].push(candidate);
    return groups;
  }, {});
}

export function DraftSupportReview({ session, selectedResults, onSelectedResultsChange, onSessionChange }) {
  const [candidates, setCandidates] = useState([]);
  const [guidance, setGuidance] = useState("");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function loadRecommendations() {
    if (!session?.id) return;
    setBusy(true);
    setError("");
    try {
      const { api } = await import("../api/client.js");
      const response = await api.recommendSessionSupport(session.id, { apply: true });
      setCandidates(response.candidates || []);
      setGuidance(response.guidance || "");
      setQuery(response.query || "");
      onSelectedResultsChange(response.selectedResults || []);
      if (response.session) onSessionChange?.(response.session);
    } catch (err) {
      setError(err.message || "Could not recommend drafting support.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadRecommendations();
    // Recommendations are session-specific; manual reload is available after first load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  const selectedIds = useMemo(() => new Set((selectedResults || []).map((result) => result.id)), [selectedResults]);
  const groups = groupCandidates(candidates);

  function toggleCandidate(candidate) {
    const exists = selectedIds.has(candidate.id);
    const next = exists
      ? selectedResults.filter((result) => result.id !== candidate.id)
      : [...selectedResults, candidate];
    onSelectedResultsChange(next);
  }

  return (
    <div className="panel">
      <div className="step-guidance">
        <span className="block-kicker">AI proposed, human reviewed</span>
        <h3>Review drafting support</h3>
        <p>
          The AI reviews the selected template, active sections, confirmed facts, jurisdiction, and drafting instructions, then proposes the
          authorities, examples, and references the draft may rely on. Confirm the sources below before legal issue review.
        </p>
        {guidance && <small>{guidance}</small>}
      </div>

      <div className="button-row compact">
        <button className="secondary" type="button" disabled={busy || !session?.id} onClick={loadRecommendations}>
          {busy ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />} Refresh AI suggestions
        </button>
        <span className="muted-inline">{selectedResults.length} selected</span>
      </div>

      {query && (
        <details className="support-query-details">
          <summary>What the AI used to search</summary>
          <p>{query}</p>
        </details>
      )}

      {error && <div className="inline-error">{error}</div>}
      {!busy && candidates.length === 0 && (
        <div className="empty-state compact">
          <strong className="empty-state-title">No support candidates yet</strong>
          <p>Use “Refresh AI suggestions” after confirming facts and sections. You can continue without support if the draft does not need authorities or examples.</p>
        </div>
      )}

      {PURPOSE_ORDER.map((purpose) => {
        const items = groups[purpose] || [];
        if (!items.length) return null;
        const label = items[0].purposeLabel || purpose.replaceAll("_", " ");
        return (
          <section key={purpose} className="support-group">
            <h4>{label}</h4>
            <div className="result-list">
              {items.map((candidate) => (
                <article key={candidate.id} className="result-card">
                  <label className="result-select">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(candidate.id)}
                      onChange={() => toggleCandidate(candidate)}
                    />
                    <span>
                      <strong>{candidate.title}</strong>
                      <p>{candidate.snippet}</p>
                      <small>{candidate.sourceLabel}{candidate.citation ? ` · ${candidate.citation}` : ""}</small>
                    </span>
                  </label>
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

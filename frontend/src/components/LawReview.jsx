import React, { useEffect, useState } from "react";
import { CheckCircle2, Loader2, Scale, XCircle } from "lucide-react";

import { api } from "../api/client.js";


export function LawReview({ matter, session, onIssuesChange }) {
  const [issues, setIssues] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!matter?.id) {
      setIssues([]);
      return;
    }
    api.candidateIssues(matter.id)
      .then((response) => {
        setIssues(response.candidateIssues || []);
        onIssuesChange?.(response.candidateIssues || []);
      })
      .catch((err) => setError(err.message));
  }, [matter?.id]);

  async function runIssueSelection() {
    if (!matter?.id) return;
    setBusy(true);
    setError("");
    try {
      const response = await api.runIssueSelection(matter.id, {
        tableKey: "eviction_answer_issue_selection",
        workflowRunId: session?.id ? String(session.id) : "",
        includeUnreviewed: true,
      });
      setIssues(response.candidateIssues || []);
      onIssuesChange?.(response.candidateIssues || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function reviewIssue(issue, action) {
    setBusy(true);
    setError("");
    try {
      const response = await api.reviewCandidateIssue(issue.id, { action });
      const nextIssues = issues.map((item) => item.id === issue.id ? response.candidateIssue : item);
      setIssues(nextIssues);
      onIssuesChange?.(nextIssues);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <div className="step-guidance">
        <span className="block-kicker">Human review gate</span>
        <h3>Review legal issues before drafting</h3>
        <p>
          The system proposes defenses, counterclaims, denials, or missing-fact checks from the selected facts and drafting support.
          Approve only the issues the draft should use; approved issues can activate draft sections.
        </p>
      </div>
      <button className="primary full" disabled={busy || !matter} onClick={runIssueSelection}>
        {busy ? <Loader2 className="spin" size={16} /> : <Scale size={16} />}
        Map selected facts and support to legal issues
      </button>
      {error && <div className="inline-error">{error}</div>}
      <div className="issue-list">
        {issues.length === 0 && (
          <div className="empty-state compact">
            <strong className="empty-state-title">No candidate issues yet</strong>
            <p>Run legal issue mapping after reviewing facts and drafting support. Approved issues activate draft sections; rejected issues stay out of the draft.</p>
          </div>
        )}
        {issues.map((issue) => (
          <article key={issue.id} className="issue-card">
            <div>
              <div className="issue-card-title">
                <strong>{issue.title}</strong>
                <span className={`status-pill ${issue.status}`}>{issue.status.replaceAll("_", " ")}</span>
              </div>
              {issue.explanation && <p>{issue.explanation}</p>}
              {issue.supportingFacts?.length > 0 && (
                <div className="standard-fact-map">
                  <strong>Selected facts supporting this issue</strong>
                  <ul>
                    {issue.supportingFacts.map((fact) => <li key={fact}>{fact}</li>)}
                  </ul>
                </div>
              )}
              {issue.missingFacts?.length > 0 && (
                <div className="standard-fact-map missing">
                  <strong>Missing facts to confirm</strong>
                  <ul>
                    {issue.missingFacts.map((fact) => <li key={fact}>{fact}</li>)}
                  </ul>
                </div>
              )}
              {issue.outputs?.activate_blocks_after_approval?.length > 0 && (
                <div className="standard-fact-map">
                  <strong>Draft sections activated if approved</strong>
                  <ul>
                    {issue.outputs.activate_blocks_after_approval.map((blockKey) => <li key={blockKey}>{blockKey}</li>)}
                  </ul>
                </div>
              )}
              <small>{issue.sourceTableKey} v{issue.sourceTableVersion} · {issue.sourceRowId}</small>
            </div>
            <div className="button-row compact">
              <button className="secondary" disabled={busy || issue.status === "approved"} onClick={() => reviewIssue(issue, "approve")}>
                <CheckCircle2 size={16} /> Approve
              </button>
              <button className="secondary danger" disabled={busy || issue.status === "rejected"} onClick={() => reviewIssue(issue, "reject")}>
                <XCircle size={16} /> Reject
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

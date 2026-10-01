import React, { useEffect, useMemo, useSyncExternalStore } from "react";
import { api } from "../api/client.js";
import { createPrecedentSearch, resultDetails, sourceLink } from "./sharepointSearch.js";

export function SharePointPrecedents() {
  const model = useMemo(() => createPrecedentSearch(api.sharepointPrecedents), []);
  const state = useSyncExternalStore(model.subscribe, model.getSnapshot);
  useEffect(() => () => model.dispose(), [model]);
  return (
    <div className="case-catalog">
      <p>Search documents in your configured SharePoint library. No AI is used.</p>
      <form onSubmit={(event) => { event.preventDefault(); model.submit(); }}>
        <label htmlFor="sharepoint-query">Search SharePoint precedents</label>
        <div className="case-catalog-search">
          <input id="sharepoint-query" className="form-control" value={state.query}
            onChange={(event) => model.setQuery(event.target.value)} maxLength={500}
            aria-describedby="sharepoint-query-help" />
          <button className="btn btn-light" type="submit" disabled={state.busy || !state.query.trim()}>Search</button>
        </div>
        <small id="sharepoint-query-help">Enter words to find in the library. Open a result to read the original in SharePoint.</small>
      </form>
      <div aria-live="polite" aria-busy={state.busy}>
        {state.busy && <p role="status">Searching SharePoint…</p>}
        {state.error && <p className="inline-error" role="alert">{state.error}</p>}
        {state.results !== null && <>
          <p>{state.aiSummary}</p>
          <p>{state.coverage}</p>
          {state.results.length === 0 ? <p>No matching files were returned. Try different search words.</p> : (
            <ul className="list-unstyled">
              {state.results.map((result) => (
                <li key={result.id} className="mb-3">
                  <strong>{result.title}</strong>
                  <p className="mb-1">{result.snippet}</p>
                  <small className="d-block">{resultDetails(result)}</small>
                  {sourceLink(result.url) ? <a href={sourceLink(result.url)} target="_blank" rel="noopener noreferrer">Open in SharePoint (new tab)</a> : <span>Source link unavailable</span>}
                </li>
              ))}
            </ul>
          )}
        </>}
      </div>
    </div>
  );
}

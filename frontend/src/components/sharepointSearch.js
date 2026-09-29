export function sourceLink(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : "";
  } catch {
    return "";
  }
}

export function resultDetails(result) {
  const metadata = result.metadata || {};
  return [metadata.mimeType, metadata.modifiedAt ? `Modified ${metadata.modifiedAt}` : "", metadata.path].filter(Boolean).join(" · ");
}

// Keep asynchronous state outside the view so stale responses and failure
// states can be checked without a browser runtime.
export function createPrecedentSearch(search) {
  let state = { query: "", busy: false, results: null, error: "", aiSummary: "", coverage: "" };
  let generation = 0;
  let controller;
  const listeners = new Set();
  function update(patch) {
    state = { ...state, ...patch };
    listeners.forEach((listener) => listener());
  }
  return {
    getSnapshot: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    setQuery(query) {
      generation += 1;
      controller?.abort();
      update({ query, busy: false, results: null, error: "", aiSummary: "", coverage: "" });
    },
    async submit() {
      const query = state.query.trim();
      const current = ++generation;
      controller?.abort();
      if (!query || query.length > 500) {
        update({ error: "Enter a search of 1–500 characters.", busy: false, results: null });
        return;
      }
      controller = new AbortController();
      update({ busy: true, error: "", results: null, aiSummary: "", coverage: "" });
      try {
        const payload = await search(query, { signal: controller.signal });
        if (current !== generation) return;
        update({ results: payload.results || [], aiSummary: payload.aiSummary, coverage: payload.coverage });
      } catch (error) {
        if (current !== generation || error.name === "AbortError") return;
        const retry = error.data?.retryAfter;
        update({ error: `${error.message || "SharePoint search failed."}${retry ? ` Try again in ${retry} seconds.` : ""}` });
      } finally {
        if (current === generation) update({ busy: false });
      }
    },
    dispose() {
      generation += 1;
      controller?.abort();
    },
  };
}

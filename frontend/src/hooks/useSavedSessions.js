import { useEffect, useState } from "react";

import { api } from "../api/client.js";
import { mergeSessionPages } from "../state/savedSessions.js";

const PAGE_SIZE = 20;

// The saved sessions for one case. Reading only; a list screen never starts,
// resumes, or changes a session.
export function useSavedSessions(caseKey, { workspace = "drafting", enabled = true } = {}) {
  const [state, setState] = useState({ sessions: [], total: 0, hasMore: false, loading: false, error: "" });

  useEffect(() => {
    if (!enabled || !caseKey) {
      setState({ sessions: [], total: 0, hasMore: false, loading: false, error: "" });
      return undefined;
    }
    const controller = new AbortController();
    setState((current) => ({ ...current, sessions: [], loading: true, error: "" }));
    api.savedSessions({ caseKey, workspace, limit: PAGE_SIZE }, { signal: controller.signal })
      .then((response) => {
        setState({ sessions: response.sessions || [], total: response.total || 0, hasMore: Boolean(response.hasMore), loading: false, error: "" });
      })
      .catch((err) => {
        if (controller.signal.aborted || err?.name === "AbortError") return;
        setState({ sessions: [], total: 0, hasMore: false, loading: false, error: err.message });
      });
    return () => controller.abort();
  }, [caseKey, workspace, enabled]);

  async function loadMore() {
    setState((current) => ({ ...current, loading: true }));
    try {
      const response = await api.savedSessions({ caseKey, workspace, limit: PAGE_SIZE, offset: state.sessions.length });
      setState((current) => ({
        ...current,
        sessions: mergeSessionPages(current.sessions, response.sessions || []),
        total: response.total || current.total,
        hasMore: Boolean(response.hasMore),
        loading: false,
      }));
    } catch (err) {
      setState((current) => ({ ...current, loading: false, error: err.message }));
    }
  }

  return { ...state, loadMore };
}

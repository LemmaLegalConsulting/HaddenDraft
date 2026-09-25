import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { parseAnswers } from "../components/templateFill.js";

// The rendered document for the saved answers plus anything typed since. Only
// fetched while the preview is showing, and not on every keystroke.
export function useFillPreview(session, edits, active) {
  const [state, setState] = useState({ preview: null, error: "", loading: false });
  useEffect(() => {
    if (!active || !session) return undefined;
    let answers;
    try { answers = parseAnswers(session.fields, edits); }
    catch (error) { setState((current) => ({ ...current, error: error.message, loading: false })); return undefined; }
    let cancelled = false;
    setState((current) => ({ ...current, loading: true }));
    const timer = setTimeout(() => {
      api.previewTemplateFill(session.id, answers)
        .then((response) => { if (!cancelled) setState({ preview: response.preview, error: "", loading: false }); })
        .catch((error) => { if (!cancelled) setState((current) => ({ ...current, error: error.message, loading: false })); });
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [active, session, edits]);
  return state;
}

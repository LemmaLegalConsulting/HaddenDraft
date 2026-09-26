import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { parseAnswers } from "../components/templateFill.js";
import { saveResponseAsFile } from "../components/downloadFile.js";
import { saveDefault } from "../components/legalServerSave.js";
import { clearDraft, openSessionFor, purgeUnscopedEntries, rememberOpenSession, restoreDraft, saveDraft } from "../state/templateFillDraft.js";

// Fill template state, driven by the URL.
//
// `route` names what is open: { sessionId, jobId }. The hook loads exactly
// that session (checked against the URL's case by the server) and reconnects
// to exactly that job; it asks `navigate` to move the URL when work starts or
// finishes, and never opens a different session in place of a missing one.
// The browser's "last open" hint only fills a URL that names no session.
export function useTemplateFill(matterId, authorProfile, legalserverSave, { account = "", caseKey = "", route = {}, navigate = null } = {}) {
  const [catalog, setCatalog] = useState({ templates: [], sessions: [] });
  const [session, setSession] = useState(null);
  const [edits, setEdits] = useState({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [completed, setCompleted] = useState(null);
  const [sessionMissing, setSessionMissing] = useState(false);
  const [saveToLegalServer, setSaveToLegalServer] = useState(() => saveDefault(legalserverSave, "documents"));
  const alive = useRef(true);
  const sessionRef = useRef(null);
  sessionRef.current = session;
  const routeSessionId = route.sessionId ?? null;
  const routeJobId = route.jobId ?? null;

  useEffect(() => {
    purgeUnscopedEntries();
  }, []);

  useEffect(() => {
    alive.current = true;
    if (matterId) api.fillCatalog(matterId).then((value) => {
      if (!alive.current) return;
      setCatalog(value);
      if (routeSessionId) return;
      // Reopen what was open when this panel last went away -- only when the
      // URL names nothing itself.
      const open = openSessionFor(account, matterId);
      if (open && value.sessions.some((item) => String(item.id) === open)) navigate?.({ sessionId: Number(open) }, { replace: true });
    }).catch((e) => { if (alive.current) setError(e.message); });
    return () => { alive.current = false; };
  }, [matterId]);

  useEffect(() => {
    if (session) saveDraft(account, session.id, session.revision, edits);
  }, [session, edits, account]);

  async function loadSession(id, { restore = true } = {}) {
    const response = await api.fillSession(id, { caseKey });
    if (!alive.current) return null;
    setSession(response.session);
    setSessionMissing(false);
    if (!restore) clearDraft(account, id);
    const draft = restore ? restoreDraft(account, response.session.id, response.session.revision) : null;
    const restored = draft?.edits ? Object.keys(draft.edits).length : 0;
    setEdits(draft?.edits || {});
    setNotice(restored ? `Restored ${restored} unsaved ${restored === 1 ? "change" : "changes"} from before this screen was closed or reloaded.`
      : draft?.stale ? "Unsaved changes from before this screen was closed were discarded: the document has been saved since." : "");
    rememberOpenSession(account, matterId, response.session.id);
    const exported = response.jobs.find((job) => job.kind === "export" && job.status === "complete");
    setCompleted(exported || null);
    return response;
  }

  // The session the URL names. A job URL loads its session too, so the page
  // has something to show while it waits.
  useEffect(() => {
    if (!matterId || !routeSessionId) {
      if (!routeSessionId) { setSession(null); setSessionMissing(false); }
      return;
    }
    if (sessionRef.current?.id === routeSessionId) return;
    setSession(null);
    run("Opening saved work…", async () => {
      try {
        const response = await loadSession(routeSessionId);
        const active = response?.jobs.find((job) => ["pending", "running"].includes(job.status));
        // Work still under way reconnects by URL, so a reload lands on it.
        if (active && !routeJobId) navigate?.({ sessionId: routeSessionId, jobId: active.id }, { replace: true });
        else if (!active && response?.jobs[0]?.status === "failed") throw new Error(response.jobs[0].error);
      } catch (err) {
        if (err.status === 404) {
          setSessionMissing(true);
          return;
        }
        throw err;
      }
    });
  }, [matterId, routeSessionId]);

  // The job the URL names: watched until it finishes, never started again.
  useEffect(() => {
    if (!routeJobId || !routeSessionId) return;
    run("Working…", async () => {
      const job = (await api.fillJob(routeJobId)).job;
      if (String(job.sessionId) !== String(routeSessionId)) throw new Error("This job is not part of this saved work.");
      const finished = await poll(job);
      if (finished && alive.current) navigate?.({ sessionId: finished.sessionId, view: "fields" }, { replace: true });
    });
  }, [routeJobId, routeSessionId]);

  async function poll(job) {
    let current = job;
    while (["pending", "running"].includes(current.status) && alive.current) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      if (!alive.current) return null;
      current = (await api.fillJob(current.id)).job;
    }
    if (!alive.current) return null;
    if (current.status === "failed") {
      const updated = await api.fillCatalog(matterId);
      if (alive.current) setCatalog(updated);
      throw new Error(current.error);
    }
    await loadSession(current.sessionId);
    if (current.kind === "export") setCompleted(current);
    const updated = await api.fillCatalog(matterId);
    if (alive.current) setCatalog(updated);
    return current;
  }

  async function run(label, action) {
    setBusy(label);
    setError("");
    try { await action(); }
    catch (e) { if (alive.current) setError(e.message); }
    finally { if (alive.current) setBusy(""); }
  }

  // Starting work gives it a URL at once: the job's, which becomes the
  // session's when the job finishes.
  function start(template) {
    return run("Preparing template…", async () => {
      const response = await api.startTemplateFill({ matterId, templateId: template.id, templateType: template.type, authorProfile });
      navigate?.({ sessionId: response.job.sessionId, jobId: response.job.id });
    });
  }

  function upload(file) {
    if (!file) return;
    return run("Preparing uploaded template…", async () => {
      const data = new FormData();
      data.append("matterId", matterId);
      data.append("file", file);
      const response = await api.startTemplateFill(data);
      navigate?.({ sessionId: response.job.sessionId, jobId: response.job.id });
    });
  }

  function resume(id, { discardEdits = false } = {}) {
    if (discardEdits) return run("Reloading saved values…", async () => { await loadSession(id, { restore: false }); });
    navigate?.({ sessionId: Number(id) });
    return Promise.resolve();
  }

  function save(exportDocument = false) {
    return run(exportDocument ? "Preparing DOCX…" : "Saving…", async () => {
      const answers = parseAnswers(session.fields, edits);
      const payload = { answers, revision: session.revision, saveToLegalServer };
      const response = await api.saveTemplateFill(session.id, payload, exportDocument);
      if (!alive.current) return;
      setSession(response.session);
      setEdits({});
      if (exportDocument) navigate?.({ sessionId: session.id, jobId: response.job.id });
    });
  }

  function download() {
    return run("Downloading…", async () => saveResponseAsFile(await api.downloadTemplateFill(completed.id)));
  }

  return { catalog, session, sessionMissing, edits, setEdits, busy, error, notice, completed, saveToLegalServer, setSaveToLegalServer, start, upload, resume, save, download };
}

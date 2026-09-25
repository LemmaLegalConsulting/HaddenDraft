import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { parseAnswers } from "../components/templateFill.js";
import { saveResponseAsFile } from "../components/downloadFile.js";
import { saveDefault } from "../components/legalServerSave.js";
import { clearDraft, openSessionFor, rememberOpenSession, restoreDraft, saveDraft } from "../state/templateFillDraft.js";

export function useTemplateFill(matterId, authorProfile, legalserverSave) {
  const [catalog, setCatalog] = useState({ templates: [], sessions: [] });
  const [session, setSession] = useState(null);
  const [edits, setEdits] = useState({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [completed, setCompleted] = useState(null);
  const [saveToLegalServer, setSaveToLegalServer] = useState(() => saveDefault(legalserverSave, "documents"));
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    if (matterId) api.fillCatalog(matterId).then((value) => {
      if (!alive.current) return;
      setCatalog(value);
      // Reopen what was open when this panel last went away.
      const open = openSessionFor(matterId);
      if (open && value.sessions.some((item) => String(item.id) === open)) resume(open);
    }).catch((e) => { if (alive.current) setError(e.message); });
    return () => { alive.current = false; };
  }, [matterId]);

  useEffect(() => {
    if (session) saveDraft(session.id, session.revision, edits);
  }, [session, edits]);

  async function loadSession(id, { restore = true } = {}) {
    const response = await api.fillSession(id);
    if (!alive.current) return;
    setSession(response.session);
    if (!restore) clearDraft(id);
    const draft = restore ? restoreDraft(response.session.id, response.session.revision) : null;
    const restored = draft?.edits ? Object.keys(draft.edits).length : 0;
    setEdits(draft?.edits || {});
    setNotice(restored ? `Restored ${restored} unsaved ${restored === 1 ? "change" : "changes"} from before this screen was closed or reloaded.`
      : draft?.stale ? "Unsaved changes from before this screen was closed were discarded: the document has been saved since." : "");
    rememberOpenSession(matterId, response.session.id);
    const exported = response.jobs.find((job) => job.kind === "export" && job.status === "complete");
    setCompleted(exported || null);
    return response;
  }

  async function poll(job) {
    let current = job;
    while (["pending", "running"].includes(current.status) && alive.current) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      if (!alive.current) return;
      current = (await api.fillJob(current.id)).job;
    }
    if (!alive.current) return;
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

  function start(template) {
    return run("Preparing template…", async () => {
      const response = await api.startTemplateFill({ matterId, templateId: template.id, templateType: template.type, authorProfile });
      await poll(response.job);
    });
  }

  function upload(file) {
    if (!file) return;
    return run("Preparing uploaded template…", async () => {
      const data = new FormData();
      data.append("matterId", matterId);
      data.append("file", file);
      await poll((await api.startTemplateFill(data)).job);
    });
  }

  function resume(id, { discardEdits = false } = {}) {
    return run("Opening saved work…", async () => {
      const response = await loadSession(id, { restore: !discardEdits });
      const active = response?.jobs.find((job) => ["pending", "running"].includes(job.status));
      if (active) await poll(active);
      else if (response?.jobs[0]?.status === "failed") throw new Error(response.jobs[0].error);
    });
  }

  function save(exportDocument = false) {
    return run(exportDocument ? "Preparing DOCX…" : "Saving…", async () => {
      const answers = parseAnswers(session.fields, edits);
      const payload = { answers, revision: session.revision, saveToLegalServer };
      const response = await api.saveTemplateFill(session.id, payload, exportDocument);
      if (!alive.current) return;
      setSession(response.session);
      setEdits({});
      if (exportDocument) await poll(response.job);
    });
  }

  function download() {
    return run("Downloading…", async () => saveResponseAsFile(await api.downloadTemplateFill(completed.id)));
  }

  return { catalog, session, edits, setEdits, busy, error, notice, completed, saveToLegalServer, setSaveToLegalServer, start, upload, resume, save, download };
}

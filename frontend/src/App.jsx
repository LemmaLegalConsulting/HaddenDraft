import React, { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ChevronDown,
  Cloud,
  CheckCircle2,
  ClipboardCheck,
  ClipboardList,
  Download,
  FileText,
  Gavel,
  Layers3,
  LogIn,
  LogOut,
  Loader2,
  MessageSquare,
  PenLine,
  Search,
  Settings,
  UserRound,
  X,
} from "lucide-react";

import { api } from "./api/client.js";
import { AuthorFields, emptyAuthorProfile } from "./components/AuthorFields.jsx";
import { AuthorProfile } from "./components/AuthorProfile.jsx";
import { CaseChat } from "./components/CaseChat.jsx";
import { DraftEditor } from "./editor/DraftEditor.jsx";
import { CaseSelector } from "./components/CaseSelector.jsx";
import { FactReview } from "./components/FactReview.jsx";
import { LawReview } from "./components/LawReview.jsx";
import { ResearchPanel } from "./components/ResearchPanel.jsx";
import { TemplatePicker } from "./components/TemplatePicker.jsx";
import { TriagePanel } from "./components/TriagePanel.jsx";
import { WorkflowStepper } from "./components/WorkflowStepper.jsx";

const workflowSteps = [
  { id: "setup", label: "Document" },
  { id: "author", label: "Author" },
  { id: "facts", label: "Facts" },
  { id: "sources", label: "Sources" },
  { id: "law", label: "Law" },
  { id: "editor", label: "Draft" },
];

const modeOptions = [
  { id: "case", label: "Case", icon: ClipboardList },
  { id: "triage", label: "Triage", icon: ClipboardCheck },
  { id: "case_chat", label: "Chat", icon: MessageSquare },
  { id: "research", label: "Research", icon: Search },
  { id: "draft", label: "Draft", icon: PenLine },
];

export function App() {
  const [boot, setBoot] = useState(null);
  const [cases, setCases] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [triageRubrics, setTriageRubrics] = useState([]);
  const [mode, setMode] = useState("case");
  const [draftMode, setDraftMode] = useState("draft_from_template");
  const [draftStep, setDraftStep] = useState("setup");
  const [selectedMatterId, setSelectedMatterId] = useState(null);
  const [matter, setMatter] = useState(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState(null);
  const [selectedFactIds, setSelectedFactIds] = useState([]);
  const [selectedCuratedFacts, setSelectedCuratedFacts] = useState([]);
  const [selectedBlockKeys, setSelectedBlockKeys] = useState([]);
  const [candidateIssues, setCandidateIssues] = useState([]);
  const [sourceResults, setSourceResults] = useState([]);
  const [session, setSession] = useState(null);
  const [draft, setDraft] = useState(null);
  const [triageAssessment, setTriageAssessment] = useState(null);
  const [triageHistory, setTriageHistory] = useState([]);
  const [selectedTriageRubricId, setSelectedTriageRubricId] = useState("");
  const [draftAuthorProfile, setDraftAuthorProfile] = useState(emptyAuthorProfile);
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [auth, setAuth] = useState(null);
  const [legalserver, setLegalserver] = useState(null);
  const [legalserverIdentifier, setLegalserverIdentifier] = useState("");
  const [caseSearch, setCaseSearch] = useState("");
  const [caseBusy, setCaseBusy] = useState(false);
  const [manualCaseBusy, setManualCaseBusy] = useState(false);
  const [accountBusy, setAccountBusy] = useState(false);
  const [credentials, setCredentials] = useState({ username: "", password: "" });
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [sourceDetailsOpen, setSourceDetailsOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const authResponse = await api.me();
        setAuth(authResponse.user);
        setDraftAuthorProfile({ ...emptyAuthorProfile, ...(authResponse.user.profile || {}) });
        if (authResponse.user.isAuthenticated) {
          await loadWorkspace();
        }
      } catch (err) {
        setError(err.message);
      }
    }
    load();
  }, []);

  async function loadWorkspace() {
    const bootstrap = await api.bootstrap();
    const [caseResponse, templateResponse, rubricResponse] = await Promise.all([
      api.cases(),
      api.templates(),
      api.triageRubrics(),
    ]);
    setBoot(bootstrap);
    applyCaseResponse(caseResponse);
    setTemplates(templateResponse.templates);
    setTriageRubrics(rubricResponse.rubrics || []);
    setSelectedTriageRubricId((current) => current || rubricResponse.rubrics?.[0]?.id || "");
    const defaultTemplate = templateResponse.templates.find((item) => item.slug === "answer-counterclaims-cleveland");
    setSelectedTemplateId(defaultTemplate?.id ?? templateResponse.templates[0]?.id ?? null);
  }

  function applyCaseResponse(caseResponse) {
    const nextCases = caseResponse.cases || [];
    setCases(nextCases);
    setLegalserver(caseResponse.legalserver || null);
    setLegalserverIdentifier(caseResponse.legalserver?.identifier || caseResponse.legalserver?.suggestedIdentifier || "");
    setSelectedMatterId((current) => {
      if (current && nextCases.some((item) => item.id === current)) {
        return current;
      }
      return nextCases[0]?.id ?? null;
    });
    if (!nextCases.length) {
      setMatter(null);
      setSelectedFactIds([]);
    }
  }

  async function loadCases(query = "") {
    setCaseBusy(true);
    setError("");
    try {
      const caseResponse = await api.cases(query.trim());
      applyCaseResponse(caseResponse);
    } catch (err) {
      setError(err.message);
    } finally {
      setCaseBusy(false);
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    setAuthBusy(true);
    setError("");
    try {
      const response = await api.login(credentials);
      setAuth(response.user);
      setDraftAuthorProfile({ ...emptyAuthorProfile, ...(response.user.profile || {}) });
      setCredentials({ username: "", password: "" });
      await loadWorkspace();
    } catch (err) {
      setError(err.message);
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleLogout() {
    setAuthBusy(true);
    setError("");
    setAccountMenuOpen(false);
    try {
      await api.logout();
      const response = await api.me();
      setAuth(response.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setAuthBusy(false);
    }
  }

  function updateAuthProfile(profile) {
    setAuth((current) => current ? { ...current, profile, name: profile.displayName || current.name } : current);
    setDraftAuthorProfile((current) => ({ ...current, ...profile }));
  }

  async function handleOffice365Login() {
    setAuthBusy(true);
    setError("");
    try {
      const response = await api.startOffice365Login();
      window.location.href = response.authUrl;
    } catch (err) {
      setError(err.message);
    } finally {
      setAuthBusy(false);
    }
  }

  useEffect(() => {
    if (!auth?.isAuthenticated || !selectedMatterId) {
      setMatter(null);
      setSelectedFactIds([]);
      setSelectedCuratedFacts([]);
      return;
    }
    api.caseDetail(selectedMatterId)
      .then((response) => {
        setMatter(response.case);
        const defaults = response.case.facts.filter((fact) => fact.selectedByDefault).map((fact) => fact.id);
        setSelectedFactIds(defaults);
        setSelectedCuratedFacts([]);
      })
      .catch((err) => {
        setMatter(null);
        setSelectedFactIds([]);
        setSelectedCuratedFacts([]);
        setError(err.message);
      });
  }, [auth, selectedMatterId]);

  useEffect(() => {
    if (!auth?.isAuthenticated || !selectedMatterId) {
      setTriageAssessment(null);
      setTriageHistory([]);
      return;
    }
    api.caseTriage(selectedMatterId)
      .then((response) => {
        setTriageHistory(response.assessments || []);
        setTriageAssessment(response.assessments?.[0] || null);
      })
      .catch(() => {
        setTriageHistory([]);
        setTriageAssessment(null);
      });
  }, [auth, selectedMatterId]);

  async function handleLegalServerConnect(event) {
    event.preventDefault();
    setAccountBusy(true);
    setError("");
    try {
      const response = await api.connectLegalServer({ identifier: legalserverIdentifier });
      setLegalserver(response.legalserver);
      await loadWorkspace();
    } catch (err) {
      setError(err.message);
    } finally {
      setAccountBusy(false);
    }
  }

  async function handleLegalServerDisconnect() {
    setAccountBusy(true);
    setError("");
    try {
      const response = await api.disconnectLegalServer();
      setLegalserver(response.legalserver);
      setSelectedMatterId(null);
      setMatter(null);
      await loadWorkspace();
    } catch (err) {
      setError(err.message);
    } finally {
      setAccountBusy(false);
    }
  }

  async function handleCaseSearch(event) {
    event.preventDefault();
    await loadCases(caseSearch);
  }

  async function handleCaseSearchReset() {
    setCaseSearch("");
    await loadCases("");
  }

  async function handleCreateManualCase(payload) {
    setManualCaseBusy(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("clientName", payload.clientName || "");
      formData.append("matterType", payload.matterType || "");
      formData.append("jurisdiction", payload.jurisdiction || "");
      formData.append("posture", payload.posture || "");
      formData.append("notes", payload.notes || "");
      (payload.files || []).forEach((file) => formData.append("files", file));
      const response = await api.createManualCase(formData);
      setCases((current) => {
        const withoutDuplicate = current.filter((item) => item.id !== response.case.id);
        return [response.case, ...withoutDuplicate];
      });
      setSelectedMatterId(response.case.id);
      setMatter(response.case);
      setSelectedFactIds((response.created || []).map((fact) => fact.id));
      setSelectedCuratedFacts([]);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setManualCaseBusy(false);
    }
  }

  async function runTriage(rubricId = selectedTriageRubricId) {
    if (!matter) return;
    setBusy(true);
    setError("");
    try {
      const response = await api.runCaseTriage(matter.id, { rubricId });
      setTriageAssessment(response.assessment);
      setTriageHistory((current) => [
        response.assessment,
        ...current.filter((item) => item.id !== response.assessment.id),
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === Number(selectedTemplateId)) || null,
    [selectedTemplateId, templates],
  );

  useEffect(() => {
    if (!selectedTemplate) return;
    const keys = selectedTemplate.blocks
      .filter((block) => block.required || block.selectionRule?.fact_slugs?.some((slug) => matter?.facts?.find((fact) => fact.slug === slug && selectedFactIds.includes(fact.id))))
      .map((block) => block.key);
    setSelectedBlockKeys(keys);
  }, [matter, selectedFactIds, selectedTemplate]);

  async function startSession(nextStatus = "facts") {
    if (!matter) return;
    setBusy(true);
    setError("");
    try {
      const payload = {
        mode: draftMode,
        matterId: matter.id,
        templateId: draftMode === "draft_from_scratch" ? undefined : selectedTemplateId,
        authorProfile: draftAuthorProfile,
        instructions,
      };
      const response = await api.createSession(payload);
      const created = response.session;
      const advanced = await api.advanceSession(created.id, {
        status: nextStatus,
        selectedFactIds,
        selectedCuratedFacts,
        selectedSourceResults: sourceResults,
        selectedBlockKeys,
        authorProfile: draftAuthorProfile,
        instructions,
        ...(draftMode === "draft_from_template" ? { template: selectedTemplateId } : {}),
      });
      setSession(advanced.session);
      setSelectedBlockKeys(advanced.session.selectedBlockKeys);
      return advanced.session;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function saveWorkflow(status, overrides = {}) {
    if (!session) {
      await startSession(status);
      return;
    }
    setBusy(true);
    try {
      const response = await api.advanceSession(session.id, {
        status,
        selectedFactIds,
        selectedCuratedFacts,
        selectedSourceResults: sourceResults,
        selectedBlockKeys: overrides.selectedBlockKeys || selectedBlockKeys,
        authorProfile: draftAuthorProfile,
        instructions,
        ...(draftMode === "draft_from_template" ? { template: selectedTemplateId } : {}),
      });
      setSession(response.session);
      return response.session;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function generateDraft() {
    const activeSession = session || await startSession("draft");
    if (!activeSession) {
      return;
    }
    setBusy(true);
    try {
      await api.advanceSession(activeSession.id, {
        status: "draft",
        selectedFactIds,
        selectedCuratedFacts,
        selectedSourceResults: sourceResults,
        selectedBlockKeys,
        authorProfile: draftAuthorProfile,
        instructions,
        ...(draftMode === "draft_from_template" ? { template: selectedTemplateId } : {}),
      });
      const response = await api.generateDraft(activeSession.id);
      setDraft(response.draft);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function validateDraft() {
    if (!draft) return;
    setBusy(true);
    try {
      const response = await api.validateDraft(draft.id);
      setDraft(response.draft);
      await saveWorkflow("export");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function regenerateDraftBlock(blockKey, instruction = "") {
    if (!draft) return;
    setBusy(true);
    setError("");
    try {
      const response = await api.regenerateDraftBlock(draft.id, blockKey, { instruction });
      setDraft(response.draft);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function openDraft() {
    setMode("draft");
    setDraftStep("setup");
  }

  function selectMode(nextMode) {
    if (nextMode === "draft") {
      openDraft();
      return;
    }
    setMode(nextMode);
  }

  async function continueFromDraftSources() {
    await saveWorkflow("law");
    setDraftStep("law");
  }

  async function continueFromLawReview() {
    const approvedBlockKeys = candidateIssues
      .filter((issue) => issue.status === "approved")
      .flatMap((issue) => issue.outputs?.activate_blocks_after_approval || []);
    let nextSelectedBlockKeys = selectedBlockKeys;
    if (approvedBlockKeys.length) {
      nextSelectedBlockKeys = [...new Set([...selectedBlockKeys, ...approvedBlockKeys])];
      setSelectedBlockKeys(nextSelectedBlockKeys);
    }
    await saveWorkflow("draft", { selectedBlockKeys: nextSelectedBlockKeys });
    setDraftStep("editor");
  }

  function handleCaseAction(action) {
    if (action.type === "custom_motion") {
      setDraftMode("draft_from_scratch");
      setInstructions(action.instructions || action.summary || "");
      setMode("draft");
      setDraftStep("setup");
      return;
    }
    if (action.type === "draft_template") {
      setDraftMode("draft_from_template");
      setMode("draft");
      setDraftStep("setup");
      return;
    }
    if (action.type === "review_documents" || action.type === "search_sources") {
      setMode("research");
      return;
    }
    if (action.type === "case_chat" && action.prompt) {
      setMode("case_chat");
    }
  }

  const accountName = auth?.name || auth?.email || auth?.username || "Account";
  const sourceSummary = useMemo(() => {
    const sources = boot?.sources || [];
    if (!sources.length) {
      return "No connections";
    }
    const connectedCount = sources.filter((source) => source.status?.startsWith("Connected")).length;
    return `${connectedCount} of ${sources.length} connected`;
  }, [boot?.sources]);

  if (!auth?.isAuthenticated) {
    return (
      <main className="login-screen">
        <form className="login-panel" onSubmit={handleLogin}>
          <div className="brand login-brand">
            <div className="brand-icon"><Gavel size={22} /></div>
            <h1>Drafting Tool</h1>
          </div>
          <label className="field">
            <span>Username</span>
            <input
              className="form-control"
              autoComplete="username"
              value={credentials.username}
              onChange={(event) => setCredentials((current) => ({ ...current, username: event.target.value }))}
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              className="form-control"
              autoComplete="current-password"
              type="password"
              value={credentials.password}
              onChange={(event) => setCredentials((current) => ({ ...current, password: event.target.value }))}
            />
          </label>
          <button className="btn btn-outline-secondary full" type="button" disabled={authBusy} onClick={handleOffice365Login}>
            {authBusy ? <Loader2 className="spin" size={16} /> : <Cloud size={16} />} Sign in with Office 365
          </button>
          {error && <div className="inline-error alert alert-danger">{error}</div>}
          <button className="btn btn-primary full" disabled={authBusy || !credentials.username || !credentials.password}>
            {authBusy ? <Loader2 className="spin" size={16} /> : <LogIn size={16} />} Sign in
          </button>
          <a className="btn btn-outline-secondary link-button full" href={api.adminUrl()}>
            <Settings size={16} /> Admin
          </a>
        </form>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><Gavel size={22} /></div>
          <div>
            <span className="brand-title">Drafting Tool</span>
          </div>
        </div>

        <nav className="mode-list">
          {modeOptions.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={mode === item.id ? "active" : ""} onClick={() => selectMode(item.id)}>
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {mode === "draft" && <WorkflowStepper steps={workflowSteps} activeStep={draftStep} onSelect={setDraftStep} />}

        <div className="source-card">
          <button
            className="source-card-toggle"
            type="button"
            aria-expanded={sourceDetailsOpen}
            onClick={() => setSourceDetailsOpen((current) => !current)}
          >
            <span className="source-card-title"><Archive size={16} /> Connections</span>
            <span className="source-summary">{sourceSummary}</span>
            <ChevronDown className={sourceDetailsOpen ? "chevron open" : "chevron"} size={16} />
          </button>
          {sourceDetailsOpen && (
            <div className="source-details">
              {(boot?.sources || []).map((source) => (
                <div className="source-row" key={source.kind}>
                  <span>{source.label}</span>
                  <small>{source.status}</small>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          {matter && (
            <div>
              <h2>{matter.client}</h2>
              <div className="active-case-banner">
                <span>{matter.matter}{matter.posture ? ` · ${matter.posture}` : ""}</span>
                <small>{matter.sourceSystem || "LegalServer"} case {matter.id}</small>
              </div>
            </div>
          )}
          <div className="topbar-actions">
            <div className="dropdown account-dropdown">
              <button
                className="btn btn-outline-secondary dropdown-toggle account-menu-toggle"
                type="button"
                aria-expanded={accountMenuOpen}
                onClick={() => setAccountMenuOpen((current) => !current)}
              >
                <UserRound size={16} />
                <span className="account-name">{accountName}</span>
              </button>
              {accountMenuOpen && (
                <div className="dropdown-menu dropdown-menu-end show account-menu">
                  <div className="account-menu-header">
                    <span>Signed in as</span>
                    <strong>{accountName}</strong>
                  </div>
                  <button
                    className="dropdown-item"
                    type="button"
                    onClick={() => {
                      setAccountMenuOpen(false);
                      setProfileOpen(true);
                    }}
                  >
                    <UserRound size={16} /> Profile
                  </button>
                  <button className="dropdown-item" disabled={authBusy} type="button" onClick={handleLogout}>
                    <LogOut size={16} /> Sign out
                  </button>
                  <div className="dropdown-divider" />
                  <a className="dropdown-item" href={api.adminUrl()}>
                    <Settings size={16} /> Admin
                  </a>
                </div>
              )}
            </div>
          </div>
        </header>

        {profileOpen && (
          <div className="modal-backdrop" role="presentation">
            <div className="profile-modal" role="dialog" aria-modal="true" aria-label="Profile">
              <div className="modal-heading">
                <h4>Profile</h4>
                <button className="btn btn-outline-secondary icon-button" type="button" onClick={() => setProfileOpen(false)} title="Close">
                  <X size={16} />
                </button>
              </div>
              <AuthorProfile
                user={auth}
                onSaved={(profile) => {
                  updateAuthProfile(profile);
                  setProfileOpen(false);
                }}
              />
            </div>
          </div>
        )}

        {error && <div className="error-banner alert alert-danger">{error}</div>}

        {mode === "case" && (
          <CaseSelector
            cases={cases}
            selectedMatterId={selectedMatterId}
            onSelect={setSelectedMatterId}
            matter={matter}
            legalserver={legalserver}
            identifier={legalserverIdentifier}
            onIdentifierChange={setLegalserverIdentifier}
            onConnect={handleLegalServerConnect}
            onDisconnect={handleLegalServerDisconnect}
            accountBusy={accountBusy}
            search={caseSearch}
            onSearchChange={setCaseSearch}
            onSearch={handleCaseSearch}
            onSearchReset={handleCaseSearchReset}
            caseBusy={caseBusy}
            manualCaseBusy={manualCaseBusy}
            onCreateManualCase={handleCreateManualCase}
            onModeChange={(nextMode) => nextMode === "draft" ? openDraft() : setMode(nextMode)}
          />
        )}

        {mode === "triage" && (
          <TriagePanel
            cases={cases}
            matter={matter}
            selectedMatterId={selectedMatterId}
            onSelectMatter={setSelectedMatterId}
            rubrics={triageRubrics}
            selectedRubricId={selectedTriageRubricId}
            onSelectRubric={setSelectedTriageRubricId}
            assessment={triageAssessment}
            history={triageHistory}
            busy={busy}
            manualCaseBusy={manualCaseBusy}
            onRunTriage={runTriage}
            onCreateManualCase={handleCreateManualCase}
          />
        )}

        {mode === "case_chat" && <CaseChat matter={matter} onAction={handleCaseAction} />}

        {mode === "research" && (
          <ResearchPanel
            matter={matter}
            sources={boot?.sources || []}
            onResults={(results) => setSourceResults(results)}
          />
        )}

        {mode === "draft" && draftStep === "setup" && (
          <section className="panel">
            <div className="draft-mode-switch">
              <button className={draftMode === "draft_from_template" ? "selected" : ""} onClick={() => setDraftMode("draft_from_template")}>
                <Layers3 size={16} /> Use a template
              </button>
              <button className={draftMode === "draft_from_scratch" ? "selected" : ""} onClick={() => setDraftMode("draft_from_scratch")}>
                <FileText size={16} /> Start from scratch
              </button>
            </div>
            {draftMode === "draft_from_scratch" ? (
              <label className="field">
                <span>What should this document be about?</span>
                <textarea
                  className="form-control"
                  value={instructions}
                  onChange={(event) => setInstructions(event.target.value)}
                  placeholder="Example: Motion to continue the eviction hearing because the client needs time to gather rent assistance documents."
                />
              </label>
            ) : (
              <TemplatePicker
                templates={templates.filter((template) => template.kind !== "shell")}
                selectedTemplateId={selectedTemplateId}
                selectedBlockKeys={selectedBlockKeys}
                onTemplateChange={setSelectedTemplateId}
                onBlockChange={setSelectedBlockKeys}
              />
            )}
            <div className="button-row step-actions">
              <button className="btn btn-primary" disabled={!matter || (draftMode === "draft_from_scratch" && !instructions.trim())} onClick={() => setDraftStep("author")}>
                Continue to author
              </button>
            </div>
          </section>
        )}

        {mode === "draft" && draftStep === "author" && (
          <section className="panel">
            <AuthorFields profile={draftAuthorProfile} onChange={setDraftAuthorProfile} />
            <div className="button-row step-actions">
              <button className="btn btn-outline-secondary" onClick={() => setDraftStep("setup")}>Back</button>
              <button className="btn btn-primary" disabled={!draftAuthorProfile.displayName?.trim() && !draftAuthorProfile.email?.trim()} onClick={() => setDraftStep("facts")}>
                Continue to facts
              </button>
            </div>
          </section>
        )}

        {mode === "draft" && draftStep === "facts" && (
          <section className="step-screen">
            <FactReview
              matter={matter}
              facts={matter?.facts || []}
              selectedFactIds={selectedFactIds}
              selectedCuratedFacts={selectedCuratedFacts}
              onFactChange={setSelectedFactIds}
              onCuratedChange={setSelectedCuratedFacts}
              onMatterChange={setMatter}
            />
            <div className="button-row step-actions">
              <button className="btn btn-outline-secondary" onClick={() => setDraftStep("author")}>Back</button>
              <button className="btn btn-primary" disabled={!matter} onClick={() => setDraftStep("sources")}>Continue to sources</button>
            </div>
          </section>
        )}

        {mode === "draft" && draftStep === "sources" && (
          <section className="step-screen">
            <ResearchPanel
              matter={matter}
              sources={boot?.sources || []}
              onResults={(results) => setSourceResults(results)}
            />
            <div className="button-row step-actions">
              <button className="btn btn-outline-secondary" onClick={() => setDraftStep("facts")}>Back</button>
              <button className="btn btn-primary" disabled={!matter || busy} onClick={continueFromDraftSources}>
                {busy ? <Loader2 className="spin" size={16} /> : <ClipboardList size={16} />} Continue to law review
              </button>
            </div>
          </section>
        )}

        {mode === "draft" && draftStep === "law" && (
          <section className="step-screen">
            <LawReview
              matter={matter}
              session={session}
              onIssuesChange={setCandidateIssues}
            />
            <div className="button-row step-actions">
              <button className="btn btn-outline-secondary" onClick={() => setDraftStep("sources")}>Back</button>
              <button className="btn btn-primary" disabled={!matter || busy} onClick={continueFromLawReview}>
                {busy ? <Loader2 className="spin" size={16} /> : <FileText size={16} />} Continue to draft
              </button>
            </div>
          </section>
        )}

        {mode === "draft" && draftStep === "editor" && (
          <section className="panel editor-panel">
            {draft && (
              <div className="button-row compact editor-actions">
                <button className="btn btn-outline-secondary" disabled={busy} onClick={validateDraft}>
                  <CheckCircle2 size={16} /> Validate
                </button>
                <a className="btn btn-primary link-button" href={api.exportDraftUrl(draft.id)}>
                  <Download size={16} /> Export to Word
                </a>
              </div>
            )}
            <div className="button-row step-actions top-step-actions">
              <button className="btn btn-outline-secondary" onClick={() => setDraftStep("law")}>Back to law review</button>
              <button className="btn btn-primary" disabled={busy || !matter} onClick={generateDraft}>
                {busy ? <Loader2 className="spin" size={16} /> : <FileText size={16} />} Generate draft
              </button>
            </div>
            <DraftEditor
              draft={draft}
              busy={busy}
              onChange={(sections, plainText, editorState) => setDraft((current) => current ? { ...current, sections, plainText, editorState } : current)}
              onPersist={async () => {
                if (draft) {
                  const response = await api.updateDraft(draft.id, {
                    sections: draft.sections,
                    plainText: draft.plainText,
                    editorState: draft.editorState,
                  });
                  setDraft(response.draft);
                }
              }}
              onRegenerateBlock={regenerateDraftBlock}
            />
            {draft?.validationFlags?.length > 0 && (
              <div className="flags">
                {draft.validationFlags.map((flag) => (
                  <div key={`${flag.code}-${flag.message}`} className={`flag ${flag.severity}`}>
                    <strong>{flag.location}</strong>
                    <span>{flag.message}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

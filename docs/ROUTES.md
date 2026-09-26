# Application routes

Every screen has a readable, reload-safe address that an advocate can bookmark,
refresh, copy, or return to after signing in (issue #73). This page is the
catalog, the rules every route keeps, and where each rule is tested.

URLs are built and read **only** in `frontend/src/routes/paths.js`, from one
route table, so parsing and building cannot drift apart. Nothing else
interpolates a path.

## Shape

```text
/<task>/<case-key>/<resource-type>/<resource-id>/<view>
```

Task first, case second. The case key is the matter's `routeCaseKey`: normally
its LegalServer case number (`26-0222`), otherwise its external id. It is a
lookup alias resolved by `apps.matters.route_aliases`, **never** the matter's
identity. `Matter.external_id` stays authoritative for every relation.

## Catalog

| Route | Screen | Family |
|---|---|---|
| `/cases`, `/cases/:case` | case browser, with that case active | — |
| `/drafting/:case` | the case's saved drafting sessions | — |
| `/drafting/:case/new` | unsaved setup; opening it creates nothing | — |
| `/drafting/:case/sessions/:id` | resolves to the furthest saved checkpoint (replace) | `drafting-sessions` |
| `…/sessions/:id/{goal,plan,questions,package}` | that step, from saved state | `drafting-sessions` |
| `…/sessions/:id/jobs/:jobId` | reconnects to a running generation | `drafting-sessions` |
| `…/sessions/:id/drafts/:draftId[/history\|/validation]` | that document | `drafting-sessions` |
| `/template-fill/:case` | template picker and saved fill work | — |
| `/template-fill/:case/sessions/:id/{fields,preview}` | that fill session and tab | `template-fill-sessions` |
| `/template-fill/:case/sessions/:id/jobs/:jobId` | a prepare or export job | `template-fill-sessions` |
| `/advice-letters/:case`, `…/new` | saved letters; a new letter | — |
| `/advice-letters/:case/drafts/:id[/history]` | that letter, as saved | `advice-letter-drafts` |
| `/triage/:case[/assessments/:id]` | triage; that saved assessment | `triage-assessments` |
| `/chat/:case[/threads/:id]` | current chat; that thread | `chat-threads` |
| `/research/{search,chats,library}` | research tabs | — |
| `/research/chats/:id` | that research thread | `research-chats` |
| `/research/decisions/:id`, `/research/library/:slug/chunks/:chunk` | a source open in the viewer | `research-sources` |
| `/argument-gym[/workspaces/:id[/runs/:runId]]` | gym; that session; that run | `argument-gym-sessions` |

A family can be switched off at build time with
`VITE_DISABLED_ROUTE_FAMILIES` (see `docs/DEPLOYMENT.md`). Its links then
point at the collection screen, and its URLs say they cannot be opened.

## Rules every route keeps

1. **Opening a URL only reads.** No route generates, plans, validates,
   approves, exports, delivers to LegalServer, reruns triage, or reassembles an
   advice letter because it was opened, reloaded, or reached with Back/Forward.
2. **A URL never grants access.** Each link of the chain (case → session →
   document/job/thread) is checked server-side. A mismatched parent answers
   exactly like a missing resource: no redirect to the real parent, no
   disclosure of which case something is on.
3. **Nothing stands in for what a URL names.** A missing case, session, draft,
   assessment, thread, letter, or run gets a notice, never the latest one or
   the current one in its place. A link from a newer version that this one
   cannot open says so rather than being trimmed.
4. **The URL wins over browser memory.** The remembered case and the
   template-fill "last open" hint only fill a URL that names nothing.
5. **Navigation semantics.** Push for deliberate navigation. Replace after
   creating a resource, when a resolver moves to a checkpoint, and when an old
   case number is rewritten to the current one.
6. **Saves name their revision.** A save made against an older revision is
   refused with 409 and the current state, so that edits are never silently
   overwritten. Leaving saved work with unsaved edits asks *Save and leave /
   Discard / Stay*.
7. **Search text never goes in a URL.**

## Acceptance scenarios

`S` = `frontend/e2e/screens-render.spec.js`, `R` =
`frontend/e2e/routes-acceptance.spec.js` (both stubbed, run by
`npm run test:smoke`), `B` = backend test module.

| Scenario | Covered by |
|---|---|
| Paste a deep link in a fresh browser, sign in, return to it | R "deep link survives signing in"; B `apps.core.test_return_paths` (Office 365) |
| The case number resolves through the alias layer; relations use the stable id | B `apps.matters.test_route_aliases` |
| A renumbered case: old and new links resolve; new links use the current number | B `test_renumbered_matter_keeps_its_old_link`; S "link by external id is rewritten" |
| Alias collisions never open the wrong case | B `test_colliding_case_number…`, `test_external_id_claims_back…` |
| A case absent from the first list page opens directly | B `test_a_case_not_yet_imported_is_fetched_then_resolved`; S "pasted link opens its own case" |
| `/drafting/:case` lists sessions; nothing auto-opens or is created | S "saved drafting work is listed" |
| `/new` creates nothing until asked; creation replaces it with the session URL | S "making a plan gives the new session its own URL" |
| `/sessions/:id` resolves to a checkpoint without generating | B `apps.drafting.test_resume`; S "listed and each row reopens it" |
| Wrong case/session/draft combinations do not reveal or redirect | B `test_session_on_another_case_answers_as_missing`; S "wrong case", "document the session does not have" |
| Saved goal, plan, answers, editor state, and later documents survive refresh | S "saved document survives a reload"; unit `resume-workspace.test.js` |
| Restoring does not reapply default facts/templates/blocks | unit `resume-workspace.test.js` (`hydrateSavedSession`, `blockDefaultsApply`) |
| Opening an advice letter does not reassemble it | B `apps.templates_app.test_advice_letter_restore`; S "saved advice letter reopens as saved" |
| Opening triage, validation, history, or job URLs does not rerun them | S triage and job journeys (zero writes) |
| An explicit chat thread never falls back to another | B `apps.matters.test_case_chat_threads`, `apps.sources.test_research_threads`; S chat and research journeys |
| Back/Forward never trigger a mutation | R "Back and Forward through saved work never send anything" |
| Two tabs produce a conflict, not last-write-wins | B `apps.drafting.test_revisions`; S document and session conflict journeys |
| Reload during a job reconnects; no duplicate generation | B `GenerationGuardTests`; S "generation link reconnects to its job" |
| Validation belongs to a draft revision and goes stale after an edit | B `test_findings_are_current_until_the_text_changes` |
| Template-fill local recovery cannot leak between users | unit `templateFillDraft.test.js` |
| Account switch on one tab shows nothing of the last account's case | R "another account signing in…" |
| A link opened while the server wakes still opens | R "server is waking up" |
| nginx serves the SPA for every route; `/api/`, `/admin/`, readiness, health unchanged | `scripts/check_spa_routes.sh` (Docker, real `nginx.conf`) |

The credentialed journeys in `frontend/e2e/` (`npm run test:e2e`, see
`frontend/e2e/README.md`) exercise the same flows against a real backend and
LegalServer.

## Known limits and follow-ups

- **Generation is reconnect-safe, not restart-safe.** Jobs run on daemon
  threads. A reload reconnects while the process lives, but a restarted process
  leaves a stalled job, which is detected and marked failed. A durable
  queue/worker is separate work.
- **Exact search results are not recoverable by URL.** That needs a
  persisted, authorized search id. Search text is deliberately kept out of URLs.
- **Research takes the active case as context** without naming it in the URL.
  A validated case parameter is a follow-up.
- **The draft export endpoint is a GET that writes** (session status and
  LegalServer delivery). Nothing navigates to or prefetches it, but it should
  become an explicit POST.
- **Template fill has no leave guard.** Its unsaved answers are kept in the
  browser per account and restored on return, so leaving does not lose them.

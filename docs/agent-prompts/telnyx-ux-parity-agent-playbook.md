# Agent Playbook: Telnyx-Inspired UX/UI Parity for Dograh

> **How to use this file**  
> Give this entire document to Codex, Claude Code, or another coding agent.  
> The agent MUST complete **Goal 0 → Goal N in order**. Do not skip ahead.  
> Each goal ends with **Deliverables + Exit Criteria**. Only start the next goal when exit criteria are met.

---

## Mission (read first)

**Objective:** Reverse-engineer Telnyx’s Voice AI / Programmable Voice product experience (marketing site, Mission Control portal, and developer docs) and apply the best structural, UX, and functional patterns to **Dograh** — an existing, working voice-agent platform — without breaking current functionality.

**What success looks like:**
- Dograh feels as polished and guided as Telnyx Mission Control (`portal.telnyx.com`) for building, testing, and deploying voice agents.
- Information architecture, onboarding, and builder flows mirror Telnyx mental models where appropriate.
- Missing capabilities (addons, testing, telephony setup, observability) are added autonomously but incrementally, with tests and docs.
- Existing Dograh features (workflows, campaigns, telephony providers, Pipecat pipeline) remain working.

**Non-goals:**
- Do not clone Telnyx branding, colors, or copy verbatim.
- Do not replace Dograh’s backend architecture with Telnyx’s unless explicitly justified.
- Do not hardcode Telnyx as the only telephony provider.

---

## Reference sources (mandatory reading)

Study these in parallel during Goal 0 and Goal 1:

| Source | URL | What to extract |
|--------|-----|-----------------|
| Telnyx marketing / Voice AI | https://telnyx.com | Value props, feature naming, user journeys, pricing positioning |
| Mission Control portal | https://portal.telnyx.com | IA, nav, wizards, empty states, tables, detail pages, test/simulator UX |
| Voice API fundamentals | https://developers.telnyx.com/docs/voice/programmable-voice/voice-api-fundamentals | Setup flow: account → API key → webhook → number → Voice App → first call |
| AI Assistants (no-code builder) | https://developers.telnyx.com/docs/inference/ai-assistants/no-code-voice-assistant | Builder steps, voice playground, deploy/test loop |
| Telnyx doc index | https://developers.telnyx.com/llms.txt | Full doc map for deeper research |
| Release notes (builder, flowchart) | Telnyx release notes on AI Assistant Builder, Flowchart Editor, voice playground | Multi-step builder, node tools, in-portal testing |

**Telnyx patterns to map (not copy):**
1. **Guided setup wizard** — API key → webhook URL → buy/assign number → create Voice App → test call.
2. **AI Assistant Builder** — create → instructions/greeting → model/tools → voice/STT → assign number → test in browser → deploy.
3. **Flowchart / workflow editor** — visual nodes (transfer, handoff, webhook, hangup, DTMF, SIP refer).
4. **In-portal simulator** — test agent before production; conversation history & transcripts.
5. **Voice playground** — preview TTS voices inside config UI.
6. **Mission Control IA** — groupings like Real-Time Communication, AI/Storage/Compute, Numbers, Reporting.
7. **Operational views** — call recordings, CDR, webhook logs, call quality stats, cost webhooks.
8. **Progressive disclosure** — simple defaults + “Advanced options” (webhooks, failover URL, codec, channel limits).

---

## Dograh baseline (cross-reference — do not re-discover from scratch)

The agent MUST treat this as the current-state map. Verify in repo before changing.

**Repo:** `/root/dograh` (Dograh AI v1.30.x)

**Stack:** FastAPI + SQLAlchemy + Alembic + Redis/ARQ + Pipecat | Next.js 15 App Router + Radix/shadcn + OpenAPI client

**Backend entry:** `api/app.py` → `api/routes/main.py` (`/api/v1`)

**Key domains:**

| Domain | Backend | Frontend |
|--------|---------|----------|
| Voice agents / workflows | `api/services/workflow/`, `api/routes/workflow.py` | `ui/src/app/workflow/` |
| Telephony (multi-provider) | `api/services/telephony/`, `api/routes/telephony.py`, `organization.py` | `ui/src/app/telephony-configurations/` |
| Campaigns | `api/tasks/campaign_tasks.py`, `api/routes/campaign.py` | `ui/src/app/campaigns/` |
| Models (LLM/TTS/STT) | `api/services/configuration/`, `api/routes/user.py` | `ui/src/app/model-configurations/` |
| Tools | `api/routes/tool.py` | `ui/src/app/tools/` |
| Integrations (Nango OAuth) | `api/routes/integration.py` | `ui/src/app/integrations/` |
| Recordings / reports | workflow recording, reports routes | `ui/src/app/recordings/`, `reports/` |
| Telegram SIP Gateway (recent) | `api/services/telegram_sip/`, `api/routes/telegram_sip_gateway.py` | `ui/src/app/telegram-sip-gateway/` |

**Patterns to preserve:**
- Telephony: provider registry + metadata-driven forms (`ConfigFormDialog.tsx`)
- Secrets: mask on read, merge on write (`api/services/configuration/masking.py`)
- DB: domain clients composed in `api/db/db_client.py`
- Tests: `api/tests/`, pytest + transactional DB fixtures in `api/conftest.py`

**Known nav (AppSidebar):** Voice Agents, Campaigns, Models, Telephony, Telegram SIP, Tools, Files, Recordings, Developers, Observe section.

---

## Operating rules for every goal

1. **Sequential execution** — Finish Goal N exit criteria before Goal N+1.
2. **Working app** — No regressions to call initiation, workflow runs, or telephony configs.
3. **Small PR-sized chunks** — Prefer multiple focused commits over one giant change.
4. **Evidence-based** — Every UX change cites a Telnyx reference (screenshot note, doc section, or URL).
5. **Gap doc** — Maintain `docs/ux-research/telnyx-gap-analysis.md` (create in Goal 1, update each goal).
6. **Parity matrix** — Maintain `docs/ux-research/telnyx-parity-matrix.md` with columns: Telnyx feature | Dograh today | Gap | Priority | Goal #.
7. **Autonomy with guardrails** — Agent may propose and implement missing features, but must not delete or rewrite unrelated code.
8. **Verify** — Run targeted tests/lint for touched areas; document what could not be run.

---

# GOAL 0 — Baseline audit & environment

**Purpose:** Establish facts about Dograh today before any Telnyx comparison.

### Tasks
1. Clone/read repo structure (`dograh/api`, `dograh/ui`, `dograh/docs`).
2. Run app locally if possible (Docker Compose or dev scripts); capture current nav and 3–5 core flows as screenshots or written notes.
3. Document current user journeys:
   - Create voice agent (workflow)
   - Configure telephony
   - Place test call
   - Run campaign
   - View recording/run transcript
4. List all API routers and UI routes in a table.
5. Identify UX pain points (empty states, dead ends, missing wizards, inconsistent forms).

### Deliverables
- `docs/ux-research/dograh-baseline-audit.md`

### Exit criteria
- [ ] Baseline audit file exists with routes, journeys, and pain points.
- [ ] Agent confirms Dograh runs or documents blockers.

---

# GOAL 1 — Telnyx reverse-engineering & gap analysis

**Purpose:** Deep research on Telnyx UX/UI and functional model; map to Dograh.

### Tasks
1. Crawl/read (use browser or `llms.txt`):
   - https://telnyx.com (Voice AI / Agents pages)
   - https://portal.telnyx.com (IA, menus, builder flows — login if available or use public docs/release notes)
   - https://developers.telnyx.com/docs/voice/programmable-voice/voice-api-fundamentals
   - AI Assistant docs + release notes (builder, flowchart editor, voice playground)
2. Decompose Telnyx into:
   - **Information architecture** (top nav, sections, sub-pages)
   - **Object model** (Voice App, Connection, Number, Assistant, Tool, Workflow node, Webhook event)
   - **Creation wizards** (step order, validation, test hooks)
   - **Builder UX** (tabs vs wizard vs canvas)
   - **Observability** (logs, recordings, transcripts, simulators)
3. Build parity matrix: Telnyx capability vs Dograh equivalent vs gap.
4. Prioritize gaps: P0 (blocks adoption), P1 (parity), P2 (nice-to-have).

### Deliverables
- `docs/ux-research/telnyx-gap-analysis.md`
- `docs/ux-research/telnyx-parity-matrix.md`
- `docs/ux-research/telnyx-ia-proposal.md` (proposed Dograh nav inspired by Telnyx, adapted to Dograh)

### Exit criteria
- [ ] Parity matrix has ≥30 rows covering setup, builder, telephony, test, deploy, observe.
- [ ] P0 gaps explicitly listed (max 8 items).
- [ ] Proposed IA documented with rationale.

---

# GOAL 2 — Information architecture & navigation restructure

**Purpose:** Reorganize Dograh UI nav and page hierarchy toward Telnyx clarity without breaking URLs abruptly.

### Tasks
1. Implement proposed IA in `ui/src/components/layout/AppSidebar.tsx` and related layout.
2. Group pages Telnyx-style where sensible, e.g.:
   - **Build** — Agents, Campaigns, Tools, Knowledge/Files
   - **Connect** — Telephony, Numbers, Integrations, SIP gateways
   - **Configure** — Models (LLM/TTS/STT), API keys
   - **Observe** — Runs, Recordings, Reports, Usage
3. Add section labels, icons, and consistent page headers (title + description + primary CTA).
4. Add redirects or aliases for renamed routes if needed.
5. Update empty states on list pages (telephony, workflows, campaigns) with Telnyx-style “Get started” cards linking to wizards (wizards come in Goal 3).

### Deliverables
- Updated sidebar + layout components
- `docs/ux-research/ia-changelog.md` (old route → new route)

### Exit criteria
- [ ] Nav matches `telnyx-ia-proposal.md` at ≥80%.
- [ ] All existing pages still reachable.
- [ ] No broken links in sidebar.

---

# GOAL 3 — Guided setup wizards (Telnyx Voice API fundamentals pattern)

**Purpose:** Telnyx onboarding is wizard-driven; Dograh should guide new users similarly.

### Map Telnyx Voice API setup → Dograh wizard steps

| Telnyx step | Dograh equivalent to build/guide |
|-------------|----------------------------------|
| Create account | Already have auth — skip |
| API key | Org API keys page + inline copy in wizard |
| Webhook URL | Show telephony webhook URLs per provider |
| Buy phone number | Link to telephony config + phone numbers CRUD |
| Create Voice App | Create telephony configuration (metadata form) |
| First test call | “Test connection” + initiate test call from UI |

### Tasks
1. Add **Setup Center** page: `ui/src/app/setup/` (or `/getting-started`).
2. Multi-step wizard component (reuse shadcn/Radix patterns):
   - Step 1: Models configured (LLM/TTS/STT)
   - Step 2: Telephony provider connected
   - Step 3: Phone number / caller ID added
   - Step 4: First agent created
   - Step 5: Test call completed
3. Persist progress (org-level KV or localStorage + optional backend flag).
4. Surface wizard CTA on dashboard/overview when incomplete.
5. Mirror Telnyx “common issues” table for telephony test failures in UI help panel.

### Deliverables
- Setup wizard UI + optional backend progress endpoint
- Docs: `docs/ux-research/setup-wizard.md`

### Exit criteria
- [ ] New user can follow wizard end-to-end without reading external docs.
- [ ] Wizard state reflects real backend config (not fake checkmarks).

---

# GOAL 4 — Agent builder UX (Telnyx AI Assistant Builder pattern)

**Purpose:** Improve workflow/agent editor to match Telnyx builder: instructions, greeting, model, tools, voice, test, deploy.

### Telnyx builder steps to mirror in Dograh workflow editor

1. Name + template (blank vs Customer Support, Lead Qual, Scheduler)
2. Instructions / system prompt
3. Greeting / first message
4. Model + tools selection
5. Voice + STT configuration (with playground — Goal 5)
6. Assign telephony / trigger
7. Test in browser / simulator
8. Deploy / go live

### Tasks
1. Refactor `ui/src/app/workflow/[workflowId]/` header into tabbed builder:
   - **Agent** (prompt, greeting, model overrides)
   - **Workflow** (existing React Flow canvas — Telnyx Flowchart Editor equivalent)
   - **Voice** (TTS/STT selections, link to model config)
   - **Tools** (attached tools, transfer, end-call)
   - **Telephony** (inbound number, outbound defaults)
   - **Test** (embed browser call / phone test)
   - **Deploy** (API trigger, embed, campaign link)
2. Add template picker on workflow create (`/workflow/create`).
3. Add “Advanced options” collapsible (webhooks, interruption, voicemail, tracing).
4. Unify scattered dialogs (ModelConfiguration, PhoneCall, etc.) into tab structure where possible.

### Deliverables
- Tabbed agent builder UI
- Workflow templates (at least 3)
- Updated user-facing copy explaining each tab

### Exit criteria
- [ ] Create → configure → test path ≤ 6 clicks from workflow list (measure and document).
- [ ] Existing workflows open and save without data loss.

---

# GOAL 5 — In-app testing & voice playground (Telnyx simulator + voice playground)

**Purpose:** Telnyx lets users test agents and preview voices in-portal; Dograh should too.

### Tasks
1. **Voice playground** on model config and/or workflow Voice tab:
   - Select TTS provider/voice
   - Text input → play sample (use existing TTS APIs)
2. **Agent simulator** panel on workflow Test tab:
   - Browser call (existing WebRTC path) OR text-based simulation
   - Show live transcript (reuse run transcript components)
3. **Telephony test** buttons:
   - “Test provider connection” (already exists for telephony metadata providers — surface consistently)
   - “Place test call” with destination input
4. Conversation history list per workflow (runs filtered view — Telnyx “Analyze conversation history”).

### Deliverables
- Voice playground component
- Enhanced Test tab on workflow detail
- Optional: `GET /workflows/{id}/test-sessions` if needed

### Exit criteria
- [ ] User can preview a TTS voice without starting a full call.
- [ ] User can run a test conversation and see transcript in UI.

---

# GOAL 6 — Telephony & connectivity hub (Telnyx Mission Control / Voice Apps)

**Purpose:** Centralize telephony like Telnyx “Programmable Voice” + number assignment.

### Tasks
1. Redesign `telephony-configurations` into a **Connectivity hub**:
   - List providers (cards with status: configured / missing webhook key / no numbers)
   - Detail page tabs: Credentials | Phone numbers | Inbound routing | Webhooks | Test
2. Show webhook URLs prominently (copy button) — Telnyx pattern.
3. Add connection health indicators (last successful test, warning badges — extend `TelephonyConfigWarningsContext`).
4. Align Telegram SIP Gateway into same hub (not orphaned nav item).
5. Document mapping to Telnyx Voice App fields (name, webhook URL, failover, inbound/outbound limits) in gap doc.

### Deliverables
- Telephony hub UI refactor
- Webhook URL helper component shared across providers

### Exit criteria
- [ ] All telephony config flows reachable from one hub.
- [ ] Webhook copy + test call available on detail page.

---

# GOAL 7 — Workflow canvas parity (Telnyx Flowchart Editor)

**Purpose:** Telnyx visual workflow tools (transfer, handoff, webhook, hangup, DTMF); Dograh has React Flow — improve parity.

### Tasks
1. Audit Dograh node types vs Telnyx tool nodes.
2. Add missing node UX if gaps exist (handoff between agents, DTMF gather, explicit SIP transfer node improvements).
3. Canvas UX improvements:
   - Color-coded edges/nodes (Telnyx: purple transfer, red hangup, blue other)
   - Zoom/pan controls polish
   - Mini-map or “overview” for large graphs
4. Node palette with search and categories.
5. Validate graph constraints (existing tests in `test_workflow_graph_constraints.py` must pass).

### Deliverables
- Canvas UX improvements
- Node palette + legend
- Updated `docs/voice-agent/editing-a-workflow.mdx` if user-facing

### Exit criteria
- [ ] Node palette documented.
- [ ] Graph validation tests pass.

---

# GOAL 8 — Observability & operations (Telnyx recordings, CDR, quality)

**Purpose:** Telnyx exposes call recordings, events, quality stats; Dograh should surface operational data similarly.

### Tasks
1. Unified **Calls & Runs** view:
   - Filter by workflow, campaign, status, disposition, date
   - Columns: direction, from, to, duration, cost, status, recording link
2. Run detail page: transcript, recording, extracted variables, webhook logs, errors.
3. Optional call quality / latency metrics if available from providers.
4. Export CSV (reports page enhancement).
5. Dashboard widgets on `/overview` (calls today, success rate, active campaigns).

### Deliverables
- Observability UI pages or enhancements
- API additions only if necessary (prefer existing run/recording endpoints)

### Exit criteria
- [ ] User can find any run within 3 clicks from overview.
- [ ] Transcript + recording accessible on run detail.

---

# GOAL 9 — Add missing “addons” autonomously (from parity matrix P0/P1)

**Purpose:** Implement highest-priority gaps not covered above.

### Tasks
1. Re-read `telnyx-parity-matrix.md` P0/P1 items not yet done.
2. For each item, implement backend + UI + tests:
   - Examples: import/migrate agent template, multi-agent handoff, webhook failover URL field, channel limits, background audio, SMS follow-up hook, MCP tool integration UI, etc.
3. Only implement items that fit Dograh architecture; document deferred items with reason.

### Deliverables
- Features from parity matrix (ticket list in `docs/ux-research/implementation-log.md`)
- Tests for each new feature

### Exit criteria
- [ ] All P0 gaps closed or explicitly deferred with issue links.
- [ ] ≥70% of P1 gaps closed.

---

# GOAL 10 — Polish, docs, QA, and release notes

**Purpose:** Ship coherently.

### Tasks
1. UX consistency pass (spacing, typography, button hierarchy, loading/error states).
2. Update Mintlify docs under `docs/` to reflect new IA and wizards.
3. Regenerate OpenAPI client: `ui` → `npm run generate-client`.
4. Run full test suites (api pytest, ui lint/build).
5. Write `CHANGELOG.md` entry or release notes summarizing Telnyx-inspired improvements.
6. Final parity matrix review — mark Done/Deferred.

### Deliverables
- Updated docs
- QA checklist completed
- Release notes

### Exit criteria
- [ ] CI-green or documented failures.
- [ ] Parity matrix updated to final state.
- [ ] No P0 regressions in manual smoke test checklist (below).

---

## Smoke test checklist (run at Goal 10)

- [ ] Sign up / log in
- [ ] Complete setup wizard
- [ ] Create workflow from template
- [ ] Configure telephony provider + number
- [ ] Save workflow; reload; graph intact
- [ ] Test call (browser or PSTN)
- [ ] View run transcript + recording
- [ ] Start campaign (if applicable)
- [ ] API key trigger still works

---

## Appendix A — Telnyx → Dograh concept mapping

| Telnyx concept | Dograh equivalent |
|----------------|-------------------|
| Mission Control Portal | Dograh UI (`ui/src/app/`) |
| AI Assistant | Workflow / Voice Agent |
| AI Assistant Builder | Workflow editor tabs + create flow |
| Flowchart Editor | React Flow workflow canvas |
| Voice API Application | Telephony configuration |
| Connection ID | Provider config + phone numbers |
| Phone number | `telephony_phone_numbers` |
| Webhook URL | Provider webhook endpoints in `api/routes/telephony.py` |
| Voice playground | **To build** (Goal 5) |
| In-browser simulator | BrowserCall / WebRTC test (enhance) |
| Conversation history | Workflow runs + transcripts |
| Programmable Voice docs | `docs/integrations/telephony/` |

---

## Appendix B — Key file paths (quick index)

```
dograh/api/app.py
dograh/api/routes/main.py
dograh/api/routes/workflow.py
dograh/api/routes/telephony.py
dograh/api/routes/organization.py
dograh/api/services/workflow/pipecat_engine.py
dograh/api/services/telephony/registry.py
dograh/ui/src/components/layout/AppSidebar.tsx
dograh/ui/src/app/workflow/
dograh/ui/src/app/telephony-configurations/
dograh/ui/src/components/telephony/ConfigFormDialog.tsx
dograh/docs/
```

---

## Appendix C — Prompt to paste at the start of each agent session

```
You are executing the Telnyx UX Parity Playbook for Dograh.
Read: docs/agent-prompts/telnyx-ux-parity-agent-playbook.md
Current goal: GOAL [N] — [title]
Rules: sequential goals only; preserve working behavior; cite Telnyx references; update gap docs.
Start by stating which goal you are on, what exit criteria remain, and your first 3 actions.
```

---

## Appendix D — Handoff template (between goals)

When finishing a goal, the agent MUST append to `docs/ux-research/implementation-log.md`:

```markdown
## Goal [N] complete — [date]
### Done
- ...
### Telnyx references used
- ...
### Files changed
- ...
### Verification
- ...
### Next goal
- GOAL [N+1]: [first action item]
```

---

*End of playbook.*

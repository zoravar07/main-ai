# Zopro — Architecture & Build Plan

**Last updated:** August 31, 2026

Read `ZOPRO-README.md` first if you haven't. This doc covers: the tech stack decisions, the patterns lifted from the jarvis-demo reference build, and the actual week-by-week build plan.

---

## 1. Core Architecture

```
Zopro (orchestrator / "chief of staff")
    ↓ built with CrewAI
┌─────────────┬─────────┬──────────┬─────(more later)
│Internship   │Zmoney   │Hungryvar │
│Buddy        │(trading)│(food)    │
└─────────────┴─────────┴──────────┘
    ↓ all query this
Shared Memory (AnythingLLM, workspace: zopro-brain)
- AboutMe.md, MyWork.md, anti-ai-writing-style.md
- Per-specialist context (Zmoney strategy notes, Hungryvar prefs, etc.)
    ↓
Tools (Gmail, Calendar, browser automation, later: voice via Pipecat)
```

**Stack decisions, locked in:**
- **CrewAI** — agent orchestration (Zopro = manager, specialists = crew members)
- **AnythingLLM** — shared memory / second brain, local-first
- **Claude API** — the actual reasoning engine behind every agent
- **Claude Code** — dev environment + interface for now (no dashboard yet)
- **Pipecat** — voice layer, deferred to Phase 3
- **Firecrawl / Browser-Use** — web research tools, bolted on once core agents are stable, deferred

**Cost/design principle carried through everything:** model tiering (cheap model for routing/chat, expensive model only when actually reasoning hard), local-first where possible, caching, batching. Not a cost-cutting instinct — an engineering constraint on Zopro specifically, per the profile in `AboutMe.md`.

---

## 2. Patterns Lifted from jarvis-demo (Reference Build)

Full technical breakdown lives in the conversation history / `jarvis-reference/` notes — this is the summary of what's actually being reused and how it maps onto the CrewAI stack above. jarvis-demo itself is NOT the foundation — it shells out to the `claude` CLI directly with no API key, which is a different foundation than CrewAI + API. Only the *patterns* are being lifted, not the infrastructure.

### Pattern 1 — Auto-registering capability list

jarvis-demo scans a `primitives/` folder and generates its system prompt's "here's what I can build" list from whatever files exist — so the prompt can never drift out of sync with reality as capabilities are added.

**How this applies to Zopro:** Zopro's orchestrator prompt (the "here's what I can delegate to" list) should be generated the same way — scan a registry of specialists/tools rather than hand-writing the list. Adding Hungryvar later shouldn't require editing Zopro's core prompt by hand.

**Where it does NOT apply directly:** jarvis's primitives are one-shot, stateless builds (ask a few questions, spawn an unattended build, check one output file, done). CrewAI specialists (Internship Buddy, Zmoney, Hungryvar) are ongoing, stateful, conversational agents — a fundamentally different shape. Don't force specialists into the primitive mold. Instead: use the registry-scan *idea* for the orchestrator's capability list, and keep a separate, smaller `primitives/`-style folder for genuine one-shot build actions specialists can trigger (e.g. "generate my resume as PDF," "scaffold a Hungryvar UI mockup").

### Pattern 2 — Two-layer sandbox for unattended file writes

Real, measured problem in the reference build: `allowedTools` alone does NOT stop a tool like Bash from running — it only adds capability, never removes it. Actual containment needs two separate layers:

- **Tool denial** (`--disallowedTools`) — explicitly remove anything that reaches outside the working directory (Bash, WebFetch, Task, etc.) unless a specific task actually needs it
- **Path denial** (a generated `permissions.deny` settings file) — because `Write`/`Edit` accept absolute paths, so tool denial alone doesn't stop a write to `~/.ssh` or `~/.claude/`. Gotcha worth remembering: absolute paths in a deny rule need a `//` prefix — a single leading slash is read as relative to the settings file's own location and silently matches nothing.

Also worth carrying over: never trust the tool's own "permission_denials" report as proof something was blocked — the reference build measured this being wrong. Always independently verify by checking the actual output artifact exists where it should.

**How this applies to Zopro:** Not needed yet — nothing in the current setup runs unattended with file-write tools. Becomes necessary the moment any specialist (most likely Zmoney running a backtest script, or Hungryvar scaffolding a UI) gets `Write`/`Edit` access and runs without a human approving each step. Build this before that happens, not after — this is a "build once you actually need it" item, not a Day 1 item.

### Pattern 3 — Machine-readable action tag

A cheap, fast conversational model call appends a trailing tag like `[ACTION:BUILD primitive=x key=value]` to its natural-language reply — parsed and stripped server-side before the reply is shown/spoken, letting one call both converse AND dispatch a structured action without needing native tool-calling.

**How this applies to Zopro:** Deferred until Pipecat (voice) is actually in the picture. This solves a specific latency/cost problem — avoiding a second expensive tool-calling round-trip just to decide whether to dispatch something — that only matters once voice responses need to feel instant. Native Claude tool-calling already solves this problem for text-based interaction, so don't build this early.

---

## 3. Build Plan — Week 1

Goal: prove the actual architecture works with real data. Shared memory + one working specialist + Zopro routing to it. Not the full system — the skeleton, proven.

### Day 1 — Shared Memory (AnythingLLM) ✅ DONE
AnythingLLM installed, `zopro-brain` workspace created, AboutMe.md/MyWork.md/anti-ai-writing-style.md uploaded and embedded, confirmed working (queried correctly about Zoravar's background and active projects).

### Day 2 — First Specialist: Internship Buddy
1. Define Internship Buddy in Claude Code — role: work tasks, resumes, interview prep, job search, using Easy Claim context
2. Skill file telling it to query `zopro-brain` before answering, and to use the tone rules from `anti-ai-writing-style.md`
3. Test standalone: mock interview question, confirm it pulls real details (Easy Claim, MrMed, A*STAR) unprompted

**Checkpoint:** answers using real background without re-explaining.

### Day 3 — CrewAI Orchestrator + Registry Pattern
1. Install CrewAI
2. Zopro = manager role, Internship Buddy = specialist role
3. Build the capability list as a generated registry scan (Pattern 1 above), not hand-written
4. Test routing: internship-related question → confirm Zopro delegates rather than answering directly

**Checkpoint:** one question to Zopro, silently routed, one clean answer back.

### Day 4 — Second Specialist: Zmoney (+ sandbox if needed)
1. Pull existing Zmoney context into `zopro-brain`
2. Wrap as second CrewAI specialist
3. If Zmoney needs unattended file writes (backtest scripts, reports) — build the two-layer sandbox now (Pattern 2 above)
4. Test cross-agent: a question spanning both specialists

**Checkpoint:** two specialists, shared memory, contained if either writes files.

### Day 5 — Third Specialist: Hungryvar + Cleanup
1. Same pattern for Hungryvar
2. Cleanup pass: memory consistency, style consistency, fix breakage from adding the third agent

**Checkpoint:** all three specialists live under Zopro.

### Day 6 — Interface + Testing
1. Stick with Claude Code as interface — no dashboard, no voice yet (reels put dashboard last for a reason)
2. Test edge cases: requests that don't match any specialist
3. Confirm COMPACT skill still works with the more complex setup
4. Document what's janky

### Day 7 — Buffer
Finish whatever slipped. One clean end-to-end test. COMPACT the week before starting Phase 2.

---

## 4. Deliberately Deferred (Not Week 1)

- **Voice (Pipecat)** — Phase 2/3, once core system is proven
- **Action-tag pattern** — only matters once Pipecat exists
- **Full dashboard** — Phase 3, reels put this last for a reason
- **Telegram/WhatsApp** — optional, only if wanted sooner than the dashboard
- **VPS/always-on hosting** — not needed for MVP, local is fine
- **Firecrawl/Browser-Use** — bolt on once core agents are stable

---

## 5. Open Questions / Not Yet Decided

- Final call on whether Zopro's desktop shell is Electron, Tauri, or deferred entirely in favor of just using Claude Code as the interface long-term
- Whether AnythingLLM's MCP support (if available) should be used to let Claude Code query `zopro-brain` directly, vs. keeping the two memory systems manually synced
- Exact shape of the "one-shot build primitives" folder mentioned in Pattern 1 — not needed until a specialist actually needs to trigger a one-shot build action

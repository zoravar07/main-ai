# Zopro — Day 9 Handoff

**Date:** 13 September 2026

---

## What Zopro is

A router plus eight specialists, reachable three ways: the terminal
(`python3 zopro.py`), an HTTP server on port 8420, and a full-screen desktop app
with a voice orb.

```
~/Desktop/zopro-ai/
  agents/            router, specialists, server, wake listener
  agents/.google/    OAuth credentials + cached token
  shell/             Electron app source
  zopro-env/         venv (Python 3.11)
  workspace/         where Claude Code writes files
```

---

## The eight routes

`zopro.py` classifies each question into one word, then calls that function
directly. CrewAI's hierarchical process is broken at v1.15.20 — manual routing
is deliberate, not a shortcut to revisit.

| Route | File | Reads |
|---|---|---|
| internship | `internship_buddy.py` | AnythingLLM `zopro-brain` |
| zmoney | `zmoney.py` | SQLite, read-only |
| hungryvar | `hungryvar.py` | Supabase via PostgREST, authenticated |
| research | `research.py` | Claude Code — web, files |
| calendar | `calendar_agent.py` | Google Calendar, read-only |
| mail | `gmail_agent.py` | Gmail — read and draft, never send |
| apps | `apps.py` | AppleScript — apps, Spotify, Notes, Reminders, Chrome |
| direct | `zopro.py` | memory, then answers |

---

## Cost — read this before changing anything

API spend hit roughly $4/day, so everything that could move off the Anthropic
API was moved to **Claude Code**, which bills the Claude subscription instead.
`claude_cli.py` is the helper.

The pattern: fetch data deterministically in Python (SQLite, Supabase, Gmail —
no LLM needed), then hand the question plus that data to Claude Code to reason
over. Fetching was never the expensive part; the agent loop deciding *which*
query to run was.

Still on the API: the `apps` route (needs an agent to pick tools) and Gmail
drafting (needs the API to save the draft). Both cheap.

**The $5 incident.** Claude Code picks up `ANTHROPIC_API_KEY` from the
environment if it's there — and it was, because Zopro needs it. So Claude Code
was billing the API on **Fable 5.1** at $10/$50 per million tokens, burning
~900k tokens in two hours. Fixed by stripping the key from the subprocess
environment in `claude_cli.py` and `research.py` (`env=_env()`). If Claude Code
ever prompts "detected a custom API key, use it?" the answer is **no**.

Still worth setting a monthly spend limit on the console. The default is $200K.

Trade-off: Claude Code is noticeably slower — it spins up cold each time.
`claude_cli.py` and `research.py` hardcode `~/.local/bin/claude` because launchd
runs with a minimal PATH.

---

## Boundaries enforced in code, not prompts

- **Zmoney** opens SQLite read-only, rejects anything that isn't a single SELECT
- **Gmail** never requested the send scope — sending is impossible at API level
- **Calendar** holds only the readonly scope
- **File work** is two-phase: `plan_file_work` runs in Claude Code's plan mode,
  `do_file_work` refuses without `confirmed=True`. `ALWAYS_CONFIRM = True` at the
  top of `research.py` is the switch
- **Chrome** opens pages, reads the current tab, lists tabs. Cannot click or
  type. The agent is told to treat page content as information, not instructions
- **Claude Code** runs with an explicit tool allow-list, scoped to Desktop and
  Downloads

---

## Voice

- **Wake word** — `wake.py`, openWakeWord, "hey jarvis", local. Mic only open
  while running; the Wake button starts and stops it
- **Transcription** — faster-whisper `base.en`, local, free
- **Speech** — macOS `say` with Jamie (Premium). Voice questions get spoken
  answers. Siri voices are restricted by Apple to system use only
- **Loop guard** — wake triggers rejected server-side while Zopro is speaking

Sequoia moved voice downloads to VoiceOver Utility → Speech → Voices → **+**,
not Accessibility → Spoken Content.

---

## Server

`server.py` on 127.0.0.1:8420 under launchd
(`~/Library/LaunchAgents/com.zoravar.zopro.plist`).

`POST /ask` · `GET /status` · `POST /transcribe` · `POST /speak` · `POST /shush`
· `POST /stop` · `POST /wake` · `GET /woke` · `POST /wake/start` ·
`POST /wake/stop` · `GET /wake/state` · `GET /health`

Takes 10–15 seconds to start. Log at `~/Desktop/zopro-ai/zopro-server.log`.

---

## The dashboard

Orb centred, canvas-rendered: a 3D lattice sphere with orbital rings and halo
particles. Draggable with momentum, tilts toward the cursor, click to talk.
Takes the working specialist's colour; particles stream toward that specialist's
card.

Cards left: Zmoney proposals, Holdings (live prices via yfinance with direction
arrows), High conviction. Right: today's calendar, inbox counts, today's meals.
All clickable to open the real app.

Top bar: weather, Chat/Voice, Wake, clock.

---

## Credentials

Two places, must stay in sync:
- `~/.zshrc` — for agents run directly in a terminal
- `~/Desktop/zopro-ai/agents/.env` — for the launchd server

`ANTHROPIC_API_KEY`, `ANYTHINGLLM_API_KEY`. Hungryvar reads Supabase credentials
plus `HUNGRYVAR_EMAIL` / `HUNGRYVAR_PASSWORD` from
`~/Desktop/hungryvar_Main/.env.local`.

Google OAuth in `agents/.google/`. If scopes change, delete `token.json` and
make sure `SCOPES` matches in **both** `calendar_agent.py` and `gmail_agent.py`,
or they overwrite each other's permissions.

---

## Broken now

Several UI patches landed in the file but have no effect at runtime. There are
no JavaScript errors in the console, so something structural is wrong — worth
reading `workspace.html` properly rather than patching further. It has been
through a great many string-replacement patches and is likely tangled.

- **Stop button never appears.** `#stoprow` exists in the DOM, opacity stays 0.
  `document.body.dataset.rec` reads `undefined` while recording, so the CSS
  trigger never fires — even after explicitly setting it in three places
- **Voice doesn't auto-stop on silence.** `silenceWatch` is defined and called
  before `rec.start(250)`, but recording continues until the orb is clicked
- **Orb keeps pulsing in chat view** — same root cause as the Stop button
- **Buttons don't align** with the calendar card's left edge. `alignBar()`
  measures at runtime and is called again after cards load; still wrong
- **Spoken answer lags well behind the text.** Inherent: `say` needs the
  complete answer. Fixing it means streaming and speaking sentence by sentence
- **Weather questions can't be answered** despite weather being on the
  dashboard. `/status` has it; no specialist has a weather tool
- **Transcription errors linger** in the hint line and look bad
- **Cramped spacing** around the ZOPRO label and above the input

---

## Not built

- **Conversation memory.** Chat history vanishes on quit, and Zopro has no idea
  what you asked a minute ago. "What about tomorrow?" means nothing to it. Two
  parts: persist the conversation, and feed the last few turns back as context
- **Memory web.** Notes linked to each other, stored and rendered inside Zopro —
  a graph you can look at and click through. Alongside AnythingLLM, not
  replacing it: AnythingLLM does semantic search over documents, the web does
  structured recall of entities and how they connect
- **Updates tab.** Zopro reporting across all eight specialists — what's on
  today, what's unread, what Zmoney is waiting on

---

## Unresolved

- Zmoney card opens a guessed `localhost:5173` — no real URL yet
- `ZMONEY-CONTEXT.md` describes tables that don't exist (`positions_snapshot` vs
  the real `positions`), and was never uploaded to AnythingLLM
- Run-7 fabricated-conviction bug still unverified in code. Run 8 produced 13
  memos against 13 scores, so that run was clean, but the fallback path was
  never exercised
- Haiku classifier misroutes (sent an internship question to research). Reverted.
  Worth retrying with a better-written prompt — it's pure waste on Sonnet
- Confirm Claude Code is genuinely off the API key: `grep -c "env=_env()"
  claude_cli.py research.py` should be above 0 for both

---

## Notes for next session

Downloads from chat often fail to land — heredocs are reliable.

Anything long-running (`wake.py`, `npm start`, `server.py`) holds its terminal
until Ctrl+C. Most of what looked like hanging today was this.

Every new terminal needs `source ~/Desktop/zopro-ai/zopro-env/bin/activate`
before Python will find the packages.

Screen control in the general sense — screenshot, find element, click anywhere —
is deliberately not on any list here.

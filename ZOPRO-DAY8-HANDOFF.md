# Zopro — Day 8 Handoff

**Date:** 11 September 2026

---

## What Zopro is now

A router plus seven specialists, reachable three ways: the terminal
(`python3 zopro.py`), an HTTP server on port 8420, and a menu bar app.

Everything lives in `~/Desktop/zopro-ai/`:

```
agents/       the Python — router, specialists, server
shell/        the Electron app source
zopro-env/    the venv (Python 3.11)
workspace/    where Claude Code writes files
.google/      OAuth credentials and token  (inside agents/)
```

---

## The seven routes

`zopro.py` runs a lightweight classifier that returns one word, then calls the
matching function directly. CrewAI's hierarchical process is broken at v1.15.20
— manual routing is deliberate, not a workaround to revisit.

| Route | File | What it reads |
|---|---|---|
| internship | `internship_buddy.py` | AnythingLLM `zopro-brain` |
| zmoney | `zmoney.py` | SQLite at `~/Desktop/z money agent/data/z_money.db`, read-only |
| hungryvar | `hungryvar.py` | Supabase via PostgREST, authenticated as Zoravar |
| research | `research.py` | Claude Code — web, files |
| calendar | `calendar_agent.py` | Google Calendar, read-only |
| mail | `gmail_agent.py` | Gmail — read and draft |
| direct | `zopro.py` | nothing, just answers |

---

## Boundaries that are structural, not instructions

These are enforced in code, not asked for in a prompt:

- **Zmoney** opens SQLite in read-only mode and rejects anything that isn't a
  single SELECT.
- **Gmail** never requested the send scope, so sending is impossible at the API
  level. Drafts only.
- **Calendar** holds only the readonly scope.
- **File work** is two-phase: `plan_file_work` runs in Claude Code's plan mode
  (no write tools), `do_file_work` refuses unless called with `confirmed=True`.
  `ALWAYS_CONFIRM = True` at the top of `research.py` is the switch.
- **Claude Code** runs with an explicit tool allow-list, scoped to Desktop and
  Downloads.

---

## Style

`style.py` loads `~/Desktop/zopro-ai/anti-ai-writing-style.md` at import and
appends it to every specialist's backstory. One source of truth — edit the
markdown and every agent follows. The launchd server needs a reload to pick up
changes; agents run directly pick them up immediately.

---

## Server

`server.py` on 127.0.0.1:8420, managed by launchd via
`~/Library/LaunchAgents/com.zoravar.zopro.plist`.

- `POST /ask` — `{question}` → `{route, specialist, answer}`
- `GET /status` — live figures from Zmoney, Hungryvar, weather
- `POST /transcribe` — audio file → text, via local faster-whisper
- `GET /health`

Takes 10–15 seconds to start; it imports every specialist. Restart with:

```bash
launchctl unload ~/Library/LaunchAgents/com.zoravar.zopro.plist
launchctl load ~/Library/LaunchAgents/com.zoravar.zopro.plist
```

Log at `~/Desktop/zopro-ai/zopro-server.log`.

---

## Credentials — the recurring problem

Keys live in two places and must stay in sync:

- `~/.zshrc` — for running agents directly in a terminal
- `~/Desktop/zopro-ai/agents/.env` — for the launchd server, which does not
  read your shell profile

Needed: `ANTHROPIC_API_KEY`, `ANYTHINGLLM_API_KEY`. Hungryvar reads its own
Supabase credentials from `~/Desktop/hungryvar_Main/.env.local`, which also
needs `HUNGRYVAR_EMAIL` and `HUNGRYVAR_PASSWORD`.

Google OAuth lives in `agents/.google/` — `credentials.json` and a cached
`token.json`. If scopes change, delete `token.json` to force re-consent, and
make sure `SCOPES` matches in **both** `calendar_agent.py` and `gmail_agent.py`
or they will overwrite each other's permissions.

The Anthropic key was exposed in chat several times on 10–11 September. It has
been regenerated. Avoid `cat`, `grep` and `echo` on files containing keys.

---

## Known and unfixed

- **`ZMONEY-CONTEXT.md` is out of date.** It describes `positions_snapshot`;
  the real table is `positions`. Five other tables it doesn't mention exist.
  Never uploaded to AnythingLLM.
- **Run-7 fabricated-conviction bug** — status still unverified by code
  inspection. Run 8 produced 13 memos against 13 scores, so behaviour was
  correct that run, but the fallback path was never exercised.
- **Hungryvar `meal_logs` is empty.** Planned meals live in `weeks`.
- **The Electron app still loads the old two-route panel.** `workspace.html`
  was written but rejected on design grounds.
- **Downloads from chat frequently fail to land** — heredocs are the reliable
  delivery method.

---

## What's next

1. **Dashboard.** Orb-led, chat beneath it, cards and tabs around the edges,
   mouse-reactive. Two attempts rejected for being too sparse and too much like
   a data table. Wanted: portfolio balance, calendar, mail counts, an updates
   tab where Zopro reports across all agents. Blend of Jarvis HUD and Zoey OS.
   Deep indigo and violet, not cyan.
2. **Memory as a graph.** Replace AnythingLLM with Obsidian-style markdown
   notes inside the Zopro repo — files with `[[links]]`, retrieval by title
   match plus one hop out. Zopro writes to it as well as reads.
3. **Named app control** via AppleScript — Spotify, Notes, Reminders, Mail.
4. **Phone calls** via Twilio.
5. **Cost-tiered models** — Haiku for routing, Sonnet only for real reasoning.

Screen control in the general sense — screenshot, find element, click anywhere —
is deliberately not on this list.

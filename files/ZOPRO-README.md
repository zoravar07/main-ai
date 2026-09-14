# Zopro — Project Overview

**Owner:** Zoravar Singh
**Last updated:** August 31, 2026

---

## What This Is

Zopro is a personal AI orchestration system — a "manager of managers." One central agent (Zopro) coordinates specialized sub-agents (Internship Buddy, Zmoney, Hungryvar, more later), all drawing from a shared memory layer instead of operating as isolated, disconnected chats.

The goal isn't a chatbot. It's something closer to what's shown in the reference reels: a chief-of-staff agent that delegates real work to specialists, remembers context across all of them, and can actually execute tasks (not just talk about them) — voice-activated, hotkey-accessible, eventually running semi-autonomously.

Zmoney and Hungryvar are real side projects in their own right (Zmoney = trading bot, Hungryvar = meal planning app), but they're also meant to plug into Zopro as managed sub-agents once the orchestration layer exists.

## Why This Exists

Read `AboutMe.md` for the full picture, but the short version: this is a side project done for genuine enjoyment of building with AI, that also needs to produce real value — Zmoney specifically is meant to generate money, and the whole system should reduce friction in day-to-day work (internship tasks, trading research, meal planning) so there's more time for things that matter.

## Folder Structure (this folder)

```
zopro-ai/
├── AboutMe.md                       who Zoravar is, goals, values, decision-making style
├── MyWork.md                        resume, skills, active projects, internship context
├── anti-ai-writing-style.md         how Zopro (and Claude generally) should talk
├── ZOPRO-README.md                  this file — overview + folder guide
├── ZOPRO-ARCHITECTURE.md            tech stack, design patterns, the actual build plan
└── jarvis-reference/                reference build studied for extension/sandbox patterns
    ├── JARVIS-ARCHITECTURE-HANDOFF.md
    └── jarvis-reference-repo/       full source of the reference project (MIT licensed)
```

## How These Files Get Used

`AboutMe.md`, `MyWork.md`, and `anti-ai-writing-style.md` are the actual memory foundation — they're uploaded into AnythingLLM (workspace: `zopro-brain`) so any agent built later can query them for context, and they're also referenced in Claude Code's global `CLAUDE.md` so terminal sessions load them automatically too. Two separate systems, same source files, kept in sync.

`ZOPRO-ARCHITECTURE.md` is the technical plan — read that before doing any actual build work.

`jarvis-reference/` isn't part of Zopro directly — it's a separate open-source project (`jarvis-demo`, MIT license) that was studied for specific patterns worth stealing: an auto-registering extension system, a two-layer sandbox for unattended file-writing agents, and a way to let one LLM call both converse and dispatch a structured action. The full breakdown of what's actually being reused is in `ZOPRO-ARCHITECTURE.md`.

## Current State (as of Aug 31, 2026)

- Memory files written and finalized
- Shared memory layer live in AnythingLLM (`zopro-brain` workspace), confirmed working
- Claude Code global config (`CLAUDE.md`, humanizer hooks, COMPACT skill) set up
- jarvis-demo reference build studied, patterns mapped to this architecture
- Not yet built: CrewAI orchestration layer, any specialist agents, sandbox implementation, voice interface

See `ZOPRO-ARCHITECTURE.md` for what's next.

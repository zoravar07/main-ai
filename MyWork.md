# MyWork.md

**Owner:** Zoravar Singh
**Last Updated:** August 29, 2026

---

## Education

**UCL** (2025–2029) — MSci Biological Sciences. President, Biopharmaceutical Society. VP, Punjabi Society.

**Singapore American School** (2011–2025) — Cum Laude, AP Scholar with Distinction (7×5, 1×4 on 8 APs). Science NHS (Biology minister), Chinese Honor Society. Senior Scholarship ($5,000), Booster Scholarship ($2,000), IASAS Scholar Award, 1st place Schoolwide Science Fair (composting/soil health), DNA Day Essay Contest (8th of 1,500).

**Languages:** English (native), Hindi (fluent), Mandarin (fluent)

## Work Experience

**MrMed — Founders Office Intern (2025)** — Market/competitor research on digital healthcare platforms, partnership outreach. Boosted partnership leads ~25% in 6 weeks.

**A*STAR Labs — Research Intern (2023)** — Vision transformers and diffusion models for medical image segmentation on real clinical imaging data. Improved segmentation accuracy ~15% over baseline.

**Easy Claim Sdn Bhd — Intern (Summer 2026, ongoing)** — Malaysian medico-legal AI company, Mudah Healthcare Group, Kuala Lumpur. Working under CEO Nadiah. See Internship section below.

## Leadership & Founded Projects

**Feeding Futures — Founder & President (2022–2025)** — Non-profit, 2,000+ meals delivered, $3,000+ raised. Built from zero.

**Habitat for Humanity — Co-President (2023–2025)** — Joined, rose to Co-President. 4 service trips/semester, led fundraising for housing projects.

**Code for All — Vice President (2023–2025)** — Joined, rose to VP. Coding workshops for 50+ underprivileged kids weekly.

**GameReady Sports Journal — Founder (2023–2025)** — Sports medicine journal, 10+ peer-reviewed articles with medical professionals, 1,000+ readers.

**Biomed Journalism Society — Co-Founder (2024)** — Monthly biomedical articles, school bulletin.

**Football** — U19 A-Team Captain (regional championships), U18 professional at Hougang United (Singapore).

## Skills

**Languages/Tools:** Python (primary), JavaScript/TypeScript, Playwright, RPA, Tkinter, Git, Claude Code
**AI/ML:** Vision transformers, diffusion models, medical image segmentation, Claude API/agent orchestration, prompt engineering
**Domain:** Clinical research methodology, healthcare tech, legal-tech workflows, UAT methodologies, market/competitive research

---

## Active Projects

### Zopro — Personal AI Desktop Agent

**Status:** Primary long-term project, pre-MVP.

Central hub for digital workflows and sub-agents (Zmoney, Hungryvar, future ones). Desktop app (Electron/Tauri, TBD) with voice activation, hotkey chat (Cmd+Shift+Z), persistent memory, and orchestration layer for coordinating multiple agents.

Core planned integrations: Gmail, Google Calendar, browser automation, sub-agent management. Explicitly designed as an open platform — not limited to the initial integration list.

Cost management is a first-class design concern: local-first processing where possible, tiered model selection (Haiku for simple tasks, Sonnet for reasoning, Opus sparingly), caching, batching.

**Not yet decided:** final tech stack, MVP scope boundaries, agent coordination architecture details.

### Zmoney — Trading Bot

**Status:** Active, architecture in progress.

Semi-automated trading research and execution system, built for minimal manual intervention. Will run as a Zopro sub-agent — Zopro queries it for status/alerts via voice ("check my trading agent").

**Not yet documented here:** strategy, data sources, tech stack. Pull from the Zmoney project directly when needed.

### Hungryvar — Meal Planning App

**Status:** Active, architecture in progress.

AI-powered meal planning and food recommendation app, learns personal food preferences. Will feed into Zopro briefings ("what's a nice restaurant today?").

**Not yet documented here:** tech stack, data model. Pull from the Hungryvar project directly when needed.

---

## Internship — Easy Claim Sdn Bhd

**Role:** Automation tooling, legal case data scraping, UAT framework development, competitive research, business development support.

**Concrete work:**
- Playwright-based scraper for CLJ Prime case law (`clj_scraper.py`, 461 lines)
- Desktop automation tools (Python/Tkinter) for document organization and classification
- UAT testing framework for the ALPHV AI engine
- Vendor research for case management system rebuild (Pexa CMS comparison)
- OneDrive case folder document organizer
- Market integration research (Lawdify-Allianz partnership context)

**Working style noted from this internship:** communicates directly, pushes back on over-engineering, prefers concrete next actions over broad recommendations. (This is a good default to carry into how I want AI tools to work with me too.)

---

## Current Priorities

1. Zopro — get core agent working: Gmail + Calendar + browser control MVP
2. Zmoney — finalize architecture, prepare for Zopro integration
3. Hungryvar — MVP before deep Zopro integration
4. Internship — wrap up Easy Claim projects
5. Memory system — this file + AboutMe.md + anti-ai-writing-style.md, feeding into Zopro's context layer

---

## Notes for Future Sessions

- Zopro is the orchestrator; Zmoney and Hungryvar are sub-agents that plug into it
- Internship work (RPA, Playwright, automation patterns) is directly informing Zopro's automation design
- Timezone during internship: Asia/Kuala_Lumpur (UTC+8); otherwise London

# Zopro Voice Desktop — Build Brief

Context doc for the main Zopro build chat. Covers: what inspired this direction,
what's already been researched, and a concrete build plan for a macOS menu bar
app that opens into a floating, voice-reactive AI assistant with real
desktop control.

Companion files in this folder:
- `JARVIS-ARCHITECTURE-HANDOFF.md` + `jarvis-reference-repo/` — full working
  open-source reference implementation, cloned and annotated
- This doc — synthesizes that reference plus a second inspiration (Zoey OS, a
  paid product) into an actual build plan for Zopro specifically

---

## 1. Where this came from

Two reference points shaped this direction:

**A) `jarvis-demo` (jdrurka, MIT, open-source, fully readable)**
A working voice assistant wired directly on top of Claude Code — no Anthropic
API key, runs on an existing Claude subscription by shelling out to the
`claude` CLI. Chrome mic → Web Speech API → WebSocket → node server → two
separate `claude -p` invocations (one for conversation, tools off; one for
building, tools on, sandboxed) → Fish Audio TTS → an audio-reactive canvas orb
in the browser. Full breakdown, including exact code patterns worth stealing,
is in `JARVIS-ARCHITECTURE-HANDOFF.md` in this same folder — read that file for
the deep architecture (the "primitive" extension system, the two-layer
sandbox for unattended agents, the machine-readable action-tag pattern).

**B) Zoey OS (zoeyos.com, a paid competitor product, NOT open-source)**
A hosted "AI operating system" — voice-first, a living 3D workspace where a
central AI ("Zoey") delegates to up to 20 specialized "companions," each able
to dispatch swarms of sub-agent "bots" (claimed ~200 in parallel at full
tier). Runs in a browser tab, not on the desktop. $90–170/mo. No public code,
no architecture disclosure — this was useful for the *visual/interaction
language* (orbs reacting to voice, a workspace you watch work happen in real
time, delegation you can literally see) but contributes nothing technical —
it's a closed product, not a reference build.

**The actual ask:** take the *visual and interaction feel* of Zoey OS (voice
in, reactive orb, watch the AI delegate and work in real time) but deliver it
the way `jarvis-demo` is architected (self-hosted, transparent, running on
your own Claude access) — and package it not as a browser tab but as a native
macOS presence: something that sits quietly in the menu bar and expands into
a floating, animated panel over the desktop on command, with the ability to
actually control the machine, not just talk about it.

---

## 2. What "done" looks like

- An icon sits in the macOS menu bar. Click it (or a global hotkey) and a
  floating panel appears over the desktop — not a browser tab, not a
  full-screen app stealing focus from whatever you're doing.
- The panel shows an animated orb/visual that reacts live to your voice while
  you talk and to the AI's voice while it replies.
- You talk, it talks back (TTS), and — like Jarvis Part 3 — it can actually
  *go do things*: run a build, open an app, execute a task, and report back
  out loud when it's done, while you watch some kind of live activity/progress
  indicator in the panel.
- Longer term: it can see and act on the rest of the screen (open apps, read
  what's on screen, click/type on your behalf) — not just run isolated
  file-writing builds in their own sandboxed folder like `jarvis-demo` does.

---

## 3. Why this is a different engineering target than either reference

Neither reference is a native desktop app:
- `jarvis-demo` runs entirely in a Chrome tab hitting `localhost:3210`.
- Zoey OS is a hosted web app in a browser tab.

Zopro's version needs to be an actual native (or native-feeling) macOS
citizen: menu bar item, floating always-on-top panel, and eventually real
control over other applications and the screen. That's a materially bigger
lift than either reference, so treat this as three additive layers rather
than one build:

**Layer 1 — the brain and voice loop (mostly a port of `jarvis-demo`'s pattern)**
**Layer 2 — the native shell (menu bar + floating panel + orb)**
**Layer 3 — real desktop control (open/control other apps, read the screen, act on it)**

Ship Layer 1+2 first as a working local prototype before touching Layer 3 —
Layer 3 is a genuinely hard, separate problem (see §6).

---

## 4. Layer 1 — Brain & voice loop (port from `jarvis-demo`)

Directly reusable ideas from the reference repo (full detail in
`JARVIS-ARCHITECTURE-HANDOFF.md`):

- **The seam**: one function, `ask(text, sessionId) -> {reply, action?}`,
  shells out to `claude -p` for a fast, tools-off conversational turn. Keep
  this pattern — it's simple, debuggable, and doesn't require the Anthropic
  API directly since it rides on the Claude subscription already in use.
- **Two invocation types**: a cheap/fast "brain" call for conversation
  (tools off, pinned to a fast model) vs. an expensive/slow "build" call
  (tools on, sandboxed, runs in its own throwaway directory, hard timeout).
  Matches the "model tiering for token cost efficiency" principle already
  part of Zopro's design.
- **The primitive pattern**: one file = one capability the assistant can
  execute, auto-registered from a directory scan, system prompt generated
  from the registry rather than hand-maintained so it can never drift out of
  sync with what's actually installed. This is the single most valuable
  transferable idea — it's exactly the extensibility model Zopro needs for
  Zmoney/Hungryvar to eventually slot in as managed sub-agents.
- **The machine-readable action tag**: e.g.
  `[ACTION:BUILD primitive=landing-page subject="a coffee shop"]` appended to
  a natural-language reply, parsed and stripped server-side before anything
  is spoken/shown. Cheap way to let one LLM call both converse *and* dispatch
  a structured action without needing native tool-calling from whatever's
  generating the reply.
- **The two-layer sandbox** for any unattended file-writing/agentic session:
  (1) explicit `--disallowedTools` deny list for anything that reaches
  outside its own working directory (Bash, WebFetch, Task, etc. unless
  specifically granted), (2) a generated per-run permissions file denying
  writes to `~/.ssh`, `~/.claude`, shell rc files, this app's own source,
  etc. Necessary the moment Zopro runs any agent session unattended on your
  actual machine.

**What to change for Zopro specifically:**
- Swap the CLI-shell-out-to-`claude -p` approach for whatever Zopro's actual
  orchestration layer ends up being (CrewAI, or a direct Anthropic API call)
  — the *pattern* (seam function, tools-off chat vs. tools-on build,
  primitive registry) is what's worth keeping, not necessarily the literal
  `child_process.spawn("claude", ...)` mechanism.
- STT/TTS should move off browser APIs since this is native now — see §5.

---

## 5. Layer 2 — Native shell: menu bar + floating panel + orb

**Menu bar item + floating panel**
- `NSStatusItem` for the menu bar icon.
- Click (or global hotkey via a library like HotKey/KeyboardShortcuts) opens
  a borderless, non-activating floating panel (`NSPanel` with
  `.nonactivatingPanel` style, or equivalent in whatever framework is
  chosen) — always-on-top, doesn't steal focus from the app you're currently
  using. This is the same interaction model as Spotlight, Raycast, or the
  ChatGPT desktop overlay.
- Framework choice: SwiftUI native gives the smoothest animation and lowest
  resource footprint and is the "correct" way to build this long-term;
  Electron/Tauri + a web view is faster to prototype (and would let the
  audio-reactive orb code be lifted close to verbatim from
  `jarvis-reference-repo/public/app.js`) at the cost of being heavier and
  less native-feeling. Decide based on how fast you want a working demo vs.
  how polished v1 needs to be.

**The reactive orb**
- Same concept as `jarvis-demo`'s canvas orb — deform/pulse a shape live
  based on (a) mic input amplitude while the user talks, (b) TTS output
  amplitude while the assistant talks. If going the Electron/WebView route,
  the existing orb rendering code in the reference repo's `public/app.js` is
  directly reusable. If going native SwiftUI, it's a `Canvas` +
  `TimelineView` driven by an `AVAudioEngine` tap for live amplitude.

**Voice pipeline, native version**
- STT: `SFSpeechRecognizer` (Apple native, on-device capable, free) instead
  of Chrome's Web Speech API — no browser dependency at all once native.
- TTS: keep Fish Audio (already configured, already in the reference repo)
  for voice quality, or fall back to `AVSpeechSynthesizer` for zero-latency/
  free at the cost of a more robotic voice. Fish Audio's HTTP API is
  trivially portable — `jarvis-reference-repo/lib/tts.js` is the whole
  integration in ~30 lines and ports to Swift/any language easily.

**Live activity/progress display**
- Port the concept (not necessarily the code) of `build-hud.js` — a visible,
  real-time readout of what the assistant/agent is currently doing, so
  "watch it work" (the best part of the Zoey OS interaction model) is
  present even without their 3D workspace.

---

## 6. Layer 3 — Real desktop control (separate milestone, don't start here)

Roughly in order of increasing difficulty/risk — build a working Layer 1+2
demo before starting this layer:

1. **Opening apps, running commands, controlling specific apps with known
   APIs** (Spotify, Mail, Calendar, Reminders) — straightforward,
   AppleScript / `NSWorkspace` / shell exec. Low risk, high value, do this
   first.
2. **Reading screen content** so the assistant has context on what you're
   looking at — macOS Screen Recording permission + periodic
   screenshot+OCR, or the Accessibility API to read UI element trees
   directly (more reliable than OCR where it's available).
3. **Clicking/typing into other apps on your behalf** — Accessibility API
   (`AXUIElement`) automation, the same mechanism tools like Raycast or
   Keyboard Maestro use. Works but every app's accessibility tree behaves
   differently; expect per-app quirks.
4. **Full "watch and act autonomously across arbitrary apps"** — this is
   the same class of problem as Claude in Chrome (for browsers) or
   Anthropic's/OpenAI's computer-use agents (for full desktops). Genuinely
   hard to make robust; treat as a real R&D milestone, not a feature to
   bolt on quickly. Worth explicitly deciding whether Zopro needs this at
   all for v1, or whether tiers 1–3 already deliver most of the value.

**Safety note for whichever tier gets built:** apply the same two-layer
sandbox discipline as `jarvis-demo`'s builder — anything that runs
unattended (a scripted automation, an agentic session with file or
Accessibility-API access) should have an explicit tool/action allowlist and
a path/target denylist, not just an allowlist alone (their own README notes,
verified empirically, that an allowlist alone doesn't actually remove
capabilities — only an explicit denylist does).

---

## 7. Suggested build order

1. Get Layer 1 working headless first (no UI): a local script that takes
   text input, round-trips through the brain/build seam, returns a reply —
   prove the orchestration logic before touching any native UI code.
2. Add voice in/out (STT + TTS) to that same headless loop — prove the audio
   pipeline in isolation.
3. Build the menu bar item + floating panel shell with a static (non-
   reactive) placeholder orb — prove the native shell and window management
   in isolation.
4. Wire the orb to live audio amplitude (mic + TTS output) — this is the
   "wow" visual and worth getting right before adding more capability.
5. Wire in the first primitive/capability (something small and safe, e.g. an
   app-open or a simple scripted task) with the two-layer sandbox in place.
6. Only after 1–5 are solid: start Layer 3 (real desktop control),
   beginning with tier 1 (known-API app control) and treating tiers 2–4 as
   later milestones.

---

## 8. Open decisions to make before/while building

- **Native SwiftUI vs. Electron/Tauri** — polish + performance vs. speed of
  reusing existing web-based orb code from the reference repo.
- **Orchestration engine** — keep the `claude -p` CLI-shell-out pattern from
  `jarvis-demo` (simplest, rides on the existing subscription) vs. call the
  Anthropic API directly vs. integrate with the CrewAI stack already
  researched for Zopro. This affects how directly the primitive/registry
  pattern can be ported.
- **How much of Layer 3 Zopro v1 actually needs** — decide explicitly rather
  than let it creep; tiers 1–3 alone would already be a genuinely capable
  and differentiated product.

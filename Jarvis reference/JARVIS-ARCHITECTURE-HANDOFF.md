# Jarvis-Demo Architecture Handoff (for Zopro reference)

Source repo: https://github.com/jdrurka/jarvis-demo (MIT license, cloned in full into
`jarvis-reference-repo/` alongside this doc — every file referenced below is in there verbatim).

Goal of this doc: give another Claude session everything it needs to understand the
pattern and build something similar (or lift pieces directly into Zopro) without
having to re-read the whole repo.

---

## 1. What it actually is

A voice interface bolted onto Claude Code itself — no Anthropic API key, runs on
Jesse's existing Claude subscription by shelling out to the `claude` CLI as a
subprocess. Three layers stacked on one seam:

```
Chrome mic → Web Speech API (free STT, browser-native)
    → WebSocket → node server
        → claude -p   (the CONVERSATION — tools off, fast, cheap model)
        → claude -p   (the BUILD — file tools on, runs in its own throwaway folder)
        → Fish Audio TTS   (cloned/library voice, speaks the reply)
        → canvas orb + build HUD (visual feedback in browser)
```

One npm dependency total (`ws`). No frontend framework, no build step.

**The core trick:** two *separate* Claude Code invocations per turn, each shelled out
fresh via `child_process.spawn`, differentiated only by CLI flags:
- **Chat turn** — `--allowedTools ""` (nothing), cheap pinned model (`haiku`), fast,
  just talks.
- **Build turn** — full `Write/Edit/Read` tools, runs unattended
  (`--permission-mode acceptEdits`), spawned into a fresh timestamped directory,
  with a hard timeout and a generated per-build permissions-deny file.

This is directly relevant to Zopro: it's a minimal, working reference for
"voice → LLM brain → spawn an agentic coding session → report back by voice,"
which is close to what Zopro's orchestration layer needs to do, just without
CrewAI/Pipecat — it does it with raw `child_process` + WebSocket + a system prompt.

---

## 2. The seam: `lib/brain.js`

Everything routes through one function:

```js
ask(text, sessionId?) -> { reply, sessionId }
```

This is called "the seam" deliberately — it's the single chokepoint between
"words the user said" and "what happens next." Two important design decisions:

1. **The persona (`VOICE` constant) is hand-written prose.** Identity, tone, address
   style, reply-length limit ("under roughly forty words"), a rule against
   markdown/lists/URLs/emoji since it's read aloud by TTS.
2. **The list of things it can build is *generated*, not hand-written**, from
   whatever primitive files exist in `primitives/`. So the system prompt can never
   drift out of sync with what's actually installed — a new capability file
   automatically updates what the assistant believes it can do.

The model is told: if a request matches something it can build, reply naturally in
character *and* append a machine-readable tag at the very end of its output, e.g.:

```
On it, sir. [ACTION:BUILD primitive=landing-page subject="a coffee shop"]
```

That tag is invisible to the user — parsed and stripped server-side
(`lib/action.js`) before anything is spoken or displayed. Regex-based, tolerant of
quoted values with spaces, tolerant of garbage (a malformed tag is just dropped,
never crashes the reply).

**Key implementation details worth stealing:**
- `--output-format json` for the chat turn (single blob, easy to parse) vs.
  `--output-format stream-json --verbose` for the build turn (progress streaming).
- `--resume <sessionId>` threads conversation memory *within a single page load
  only* — refresh = blank slate. No persistence layer exists yet (see extension #2
  below).
- The whole CLI invocation is reconstructed from scratch every single turn — no
  long-lived Claude process, no context window management by the app itself, it's
  delegated entirely to Claude Code's own session resume mechanism.

---

## 3. The extension point: `primitives/`

A **primitive** = one `.mjs` file = one kind of thing the assistant can build.
Auto-loaded by `lib/registry.js` (scans the directory, validates shape, keys a Map
by `id`). Adding a new build capability is *one file, zero other wiring* — this is
the single most reusable idea in the repo for Zopro's "managed sub-agents"
concept (Zmoney/Hungryvar could each become primitives, or Zopro's own build
capabilities could follow this exact pattern).

Shape of a primitive (see `primitives/_template.mjs`):

```js
export default {
  id: "your-primitive-id",              // MUST match filename exactly
  triggers: ["phrase", "another"],      // hints fed into the system prompt
  questions: [                          // asked one at a time before build starts
    { key: "subject", ask: "What should it be about?" },
  ],
  systemPrompt: (params) => `...`,      // full instructions handed to the build session
  allowedTools: ["Write", "Edit", "Read"],  // least-privilege tool grant
  mcp: [],                              // optional MCP servers, skipped if not configured on this machine
  outputContract: "index.html",         // proof-of-success file, checked after build finishes
  doneLine: (params) => `...`,          // spoken completion line
  timeoutMs: 300000,                    // hard ceiling
};
```

`lib/registry.js` validates every field strictly and throws with the exact file +
field name on a mistake — good pattern for a plugin system you want strangers (or
future-you) to extend safely.

---

## 4. The build sandbox: `lib/builder.js` (the part to study hardest)

This is the only module that runs Claude with tools ON, and the repo is very
explicit that **`allowedTools` is NOT a sandbox** — it only adds capability, it
doesn't remove any. Real containment happens in two separate layers:

### Layer 1 — Tool denial (`--disallowedTools`)
Anything that could reach outside the build's own folder gets explicitly denied
unless a primitive specifically asked for it:
```js
const REACHES_OUTSIDE = ["Bash", "BashOutput", "KillShell", "Task", "WebFetch", "WebSearch"];
```
Measured/verified against actual Claude Code behavior: they tested that
`allowedTools` alone does NOT stop Bash from running — only `--disallowedTools`
actually removes a tool from the session.

### Layer 2 — Path denial (`permissions.deny` in a generated settings file)
Even with Bash gone, `Write`/`Edit` accept absolute paths — so a build could still
write anywhere on disk. A throwaway `settings.json` is generated per build (merged
onto the shared `claude-settings.json`) with a deny list naming:
- `~/.claude/**`, `~/.claude.json` (hooks + MCP config = code that runs next session)
- shell rc files, `~/.gitconfig`, `~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.config`
- PATH directories, launch agents/daemons, `/etc`
- `**/.git/hooks/**` (anywhere on the machine)
- the app's own source (`lib/`, `public/`, `primitives/`, `server.js`, etc.)

Absolute paths in a deny rule need a `//` prefix (`//home/user/.ssh/**`) — single
leading slash is silently read as relative to the settings file's own location and
matches nothing. Non-obvious gotcha worth remembering if replicating this.

**Explicit caveat in their own README, worth keeping for Zopro:**
> It is still permission scoping, not a sandbox... A build is real code execution
> on your machine, under your Claude login, spending your subscription. Treat it
> that way... If you want a hard boundary, run the whole thing in a VM or a
> container.

### Other things `run()` handles that matter for a robust version:
- Fresh timestamped build directory per run, collision-safe (`mkdir` non-recursive,
  retries with `-2`, `-3` suffix on EEXIST).
- Hard timeout → SIGTERM → grace period → SIGKILL, signals the whole process
  group (not just the child) so anything the build spawned also dies.
- Streamed stdout is line-split carefully (chunks can split JSON mid-line; uses a
  `StringDecoder` to not split multi-byte UTF-8 characters across chunks either).
- Raw output always logged to `builds/<timestamp>/build.log` regardless of outcome
  — good for debugging failed unattended agent runs.
- Success is determined by **both** exit code 0 **and** the declared
  `outputContract` file actually existing afterward (`lib/outcome.js`) — a model
  can exit cleanly having produced nothing, or having stopped mid-task; checking
  the artifact is what catches that.
- `hooks` and `extended thinking` are turned off for builds specifically because
  (a) a Stop-hook that narrates output via TTS would double-narrate over a build,
  and (b) their settings turn thinking off, and max effort + thinking off is a
  guaranteed API rejection, so build effort is pinned rather than inherited.

---

## 5. Everything else, briefly

- **`server.js`** — static file server + WebSocket, binds to `127.0.0.1` only
  (explicitly: this process runs a model with file tools on, don't expose it to
  the LAN). Serves finished builds out of `builds/`.
- **`lib/outcome.js`** — pure functions, `buildSucceeded()` / `describeFailure()`,
  cleanly separated from the spawning logic so they're independently testable.
- **`lib/progress.js`** — turns raw `stream-json` build output into human-readable
  progress lines for the HUD.
- **`public/build-hud.js`** — the live readout during a build; distinguishes
  "ambient activity" from "reported events" (there's room here for a progress
  tree if builds ever spawn sub-builds).
- **`lib/config.js` / `lib/tts.js`** — trivial Fish Audio wrapper: load API key
  from `~/.config/fish-audio/speak.json` or env var, POST to their TTS endpoint,
  get back an mp3 buffer.
- Tests (`npm test`) are pure-logic only — no network, no keys required. Good
  practice if replicating: they kept everything spawning/network-dependent
  factored out into thin impure wrappers around well-tested pure functions
  (`buildSpawnArgs`, `denyRules`, `parseAction`, `buildSucceeded`, etc.)

---

## 6. The three extension directions the author flags (relevant to Zopro's roadmap)

1. **More primitives** — trivial, one file each. Natural fit for giving Zopro new
   "things it can build" incrementally.
2. **Memory across sessions** — currently `ask(text, sessionId)` only persists
   within one page load. Their suggested fix: persist `sessionId` + a short summary
   per project in a JSON file or SQLite, keyed by working directory, loaded on
   connect. Directly relevant to Zopro's "second brain" memory goals.
3. **Multi-step orchestration** — today one spoken request = one build. Suggested
   evolution: a primitive with a `steps: [...]` array run in sequence, previous
   artifact passed forward (plan → build → verify), or a build that spawns its own
   sub-builds with a progress tree. This maps closely onto Zmoney/Hungryvar
   becoming Zopro sub-agents rather than one-shot builds.

---

## 7. Reusable ideas worth lifting directly into Zopro, ranked by leverage

1. **The primitive pattern itself** — one file = one capability, auto-registered,
   system prompt generated from the registry rather than hand-maintained. This is
   probably the single most valuable transferable idea for Zopro's extensibility
   goals (matches the "extensible architectures that don't require core rewrites"
   principle already in the profile).
2. **The two-layer sandbox model** (tool denial + generated path-deny settings
   file) — necessary if Zopro is ever going to run unattended file-writing agent
   sessions on Zoravar's actual machine.
3. **The machine-readable action tag pattern** (`[ACTION:BUILD ...]` parsed and
   stripped before output reaches the user/voice layer) — cheap, dependency-free
   way to let one LLM call both converse AND dispatch structured actions without
   needing native tool-calling support from whatever's generating the reply.
4. **Separating a cheap/fast "brain" call from an expensive/slow "build" call** —
   directly matches the "token cost efficiency... model tiering" principle already
   in Zopro's design notes.
5. **Pure-function core, thin impure shell** — `denyRules()`, `buildSpawnArgs()`,
   `parseAction()`, `buildSucceeded()` are all synchronous and side-effect free,
   independently testable without spawning anything. Worth carrying into Zopro's
   own build discipline.

---

## Files included alongside this doc

Full working repo copied into `jarvis-reference-repo/` (source-only, no
`node_modules`/`.git`):

```
jarvis-reference-repo/
├── server.js
├── package.json
├── claude-settings.json
├── README.md
├── lib/
│   ├── brain.js        the seam — chat turn, persona generation, action tags
│   ├── builder.js       the build sandbox — spawn, timeout, deny rules
│   ├── registry.js      primitive loader/validator
│   ├── action.js         [ACTION:...] tag parser
│   ├── outcome.js        success/failure detection
│   ├── progress.js       raw build stream -> readable progress lines
│   ├── config.js         Fish Audio config loader
│   └── tts.js            Fish Audio API wrapper
├── primitives/
│   ├── _template.mjs     copy this to add a new capability
│   └── landing-page.mjs  the one shipped example
└── public/
    ├── index.html
    ├── app.js            mic capture, WebSocket client, orb rendering
    ├── build-hud.js       live build progress UI
    ├── stt-policy.js
    └── visibility-policy.js
```

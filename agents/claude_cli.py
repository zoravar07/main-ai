"""Run prompts through Claude Code instead of the Anthropic API.

Claude Code bills against the Claude subscription, not API credits, so routing
work here costs nothing per call. It does count against subscription rate
limits.
"""

import os
import shutil

CLAUDE_BIN = os.path.expanduser("~/.local/bin/claude")
import subprocess


def _env():
    """Claude Code must use the Claude subscription, not the API key. If
    ANTHROPIC_API_KEY is visible it bills the API instead, on Fable, at $10/$50
    per million tokens."""
    e = dict(os.environ)
    e.pop("ANTHROPIC_API_KEY", None)
    e.pop("ANTHROPIC_AUTH_TOKEN", None)
    return e
from pathlib import Path

from style import STYLE

WORKDIR = Path.home() / "Desktop" / "zopro-ai" / "workspace"
WORKDIR.mkdir(parents=True, exist_ok=True)


def run(prompt: str, system: str = "", timeout: int = 180,
        tools: str = "Read,Glob,Grep,WebSearch,WebFetch") -> str:
    exe = (CLAUDE_BIN if os.path.exists(CLAUDE_BIN) else shutil.which("claude"))
    if not exe:
        return "Claude Code is not installed or not on PATH."
    full = (system + "\n\n" + prompt) if system else prompt
    try:
        p = subprocess.run(
            [exe, "-p", full, "--allowed-tools", tools],
            cwd=str(WORKDIR), capture_output=True, text=True, timeout=timeout, env=_env())
    except subprocess.TimeoutExpired:
        return "Claude Code timed out."
    except Exception as e:
        return f"Claude Code failed: {e}"
    if p.returncode != 0:
        return f"Claude Code exited {p.returncode}: {(p.stderr or p.stdout)[:400]}"
    return (p.stdout or "").strip()


def answer(question: str, role: str, context: str = "") -> str:
    """Ask Claude Code to answer as one of Zopro's specialists."""
    system = role + STYLE
    prompt = question
    if context:
        prompt = ("Here is the real data you must answer from. Do not invent "
                  "anything beyond it; if it does not cover the question, say so.\n\n"
                  "<data>\n" + context + "\n</data>\n\n" + question)
    return run(prompt, system, tools="Read,Glob,Grep")


def classify(question: str, routes: str) -> str:
    """One-word route decision, no tools, no API cost."""
    out = run(
        f'Classify this request into exactly one route.\n\n{routes}\n\n'
        f'Request: "{question}"\n\n'
        'Reply with ONLY the single route word. No explanation, no punctuation.',
        tools="")
    return out.strip().strip('."\'').lower().split()[-1] if out.strip() else "direct"

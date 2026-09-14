"""Research specialist — delegates real work to Claude Code.

Claude Code runs on the subscription rather than per-token API billing, and it
can search the web, read and write files, and reason over long tasks. Zopro
hands it a job and reports back.

Work happens inside WORKDIR only. Claude Code is invoked with an explicit
allow-list of tools; Bash is deliberately not on it.
"""

import os
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
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

WORKDIR = Path.home() / "Desktop" / "zopro-ai" / "workspace"
WORKDIR.mkdir(parents=True, exist_ok=True)

ALLOWED = "Read,Write,Edit,Glob,Grep,WebSearch,WebFetch,TodoWrite"
TIMEOUT = 900  # 15 minutes


def notify(title: str, message: str, sound: str = "Glass") -> None:
    """macOS notification. Silently does nothing if osascript is unavailable."""
    if not shutil.which("osascript"):
        return
    safe_t = title.replace('"', "'")[:80]
    safe_m = message.replace('"', "'")[:200]
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{safe_m}" with title "{safe_t}" sound name "{sound}"'],
            check=False, timeout=10,
        )
    except Exception:
        pass


@tool("Delegate to Claude Code")
def claude_code(instruction: str) -> str:
    """Hand a substantial task to Claude Code: web research, writing a document,
    reading or editing files, multi-step analysis. It can search the web and
    write files. Use it for anything that needs real work rather than recall.

    Files are written to ~/Desktop/zopro-ai/workspace. Ask for output to be
    saved to a named file when the result is a document; otherwise it comes
    back as text.

    Takes minutes, not seconds. Give it one clear, complete instruction.
    """
    exe = (CLAUDE_BIN if os.path.exists(CLAUDE_BIN) else shutil.which("claude"))
    if not exe:
        return "Claude Code is not installed or not on PATH."

    notify("Zopro", "Claude Code started")

    try:
        proc = subprocess.run(
            [exe, "-p", instruction,
             "--allowed-tools", ALLOWED,
             "--permission-mode", "acceptEdits"],
            cwd=str(WORKDIR),
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=_env(),
        )
    except subprocess.TimeoutExpired:
        notify("Zopro", "Claude Code timed out", "Basso")
        return f"Claude Code exceeded {TIMEOUT // 60} minutes and was stopped."
    except Exception as e:
        notify("Zopro", "Claude Code failed", "Basso")
        return f"Could not run Claude Code: {e}"

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()

    if proc.returncode != 0:
        notify("Zopro", "Claude Code failed", "Basso")
        return f"Claude Code exited with {proc.returncode}.\n{err[:800] or out[:800]}"

    notify("Zopro", "Claude Code finished")
    return out or "Claude Code finished but returned no text."


@tool("List workspace files")
def list_workspace() -> str:
    """List files Claude Code has written to the Zopro workspace, newest first."""
    files = sorted(WORKDIR.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    files = [f for f in files if f.is_file()][:40]
    if not files:
        return "Workspace is empty."
    return "\n".join(
        f"{f.relative_to(WORKDIR)}  ({f.stat().st_size} bytes)" for f in files
    )


@tool("Read a workspace file")
def read_workspace_file(filename: str) -> str:
    """Read a file Claude Code wrote. Filename is relative to the workspace."""
    p = (WORKDIR / filename).resolve()
    if WORKDIR.resolve() not in p.parents and p != WORKDIR.resolve():
        return "Refused: that path is outside the workspace."
    if not p.is_file():
        return f"No such file: {filename}"
    return p.read_text(errors="replace")[:20000]


llm = LLM(model="claude-sonnet-4-5-20250929")

researcher = Agent(
    role="Research Assistant",
    goal="""Get real work done for Zoravar by delegating to Claude Code, then
    report what actually came back.""",
    backstory="""You handle anything that needs work rather than recall —
    research, drafting documents, reading or editing files, multi-step analysis.

    You do this by delegating to Claude Code, which can search the web and write
    files. Give it one clear, complete instruction. If the result should be a
    document, tell it to save to a named file in the workspace.

    Report what Claude Code actually returned. Never summarise a result you did
    not receive, and never describe a file as written unless the output says so.
    If it failed, say so plainly and say why.

    Talk like a smart, casual friend. No headers everywhere, no emoji, minimal
    bold, no "Pro Tips" sections. Lead with the answer.""" + STYLE,
    llm=llm,
    tools=[claude_code, list_workspace, read_workspace_file],
    verbose=True,
)


def ask_researcher(question: str):
    task = Task(
        description=question,
        expected_output="What Claude Code actually returned, reported honestly.",
        agent=researcher,
    )
    result = Crew(agents=[researcher], tasks=[task]).kickoff()
    notify("Zopro", "Research finished")
    return result


if __name__ == "__main__":
    print(ask_researcher(input("Ask the researcher: ")))

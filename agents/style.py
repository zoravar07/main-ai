"""Single source of truth for how Zopro talks.

Loads anti-ai-writing-style.md at import and exposes it as STYLE, which every
specialist appends to its backstory. Edit the markdown file and every agent
changes — no rules duplicated in Python.
"""

from pathlib import Path

STYLE_FILE = Path.home() / "Desktop" / "zopro-ai" / "anti-ai-writing-style.md"

_FALLBACK = """
Talk like a smart, casual friend. Direct and plain, sometimes dry. Say the
thing, give the reasoning if it's needed, move on. No signposting openers, no
sycophancy, no emoji, no bold-everything, no chatbot sign-offs. If something is
uncertain, say so rather than faking confidence. If there's a flaw in what
Zoravar is suggesting, say it plainly.
"""


def _load() -> str:
    try:
        text = STYLE_FILE.read_text(errors="replace").strip()
    except Exception:
        return _FALLBACK

    return (
        "\n\n--- HOW TO WRITE ---\n"
        "These are Zoravar's own rules for how he wants to be talked to. They "
        "override any default instinct about formatting or tone. Follow them "
        "exactly.\n\n"
        + text
    )


STYLE = _load()

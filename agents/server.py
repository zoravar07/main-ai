import io
import os
import contextlib
import sqlite3
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Must run before importing zopro — the agent modules read these at import time,
# and launchd does not source your shell profile.
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, UploadFile, File
import tempfile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from zopro import (classify, ask_internship_buddy, ask_zmoney, ask_hungryvar,
                    ask_calendar, ask_gmail, ask_researcher, ask_apps, answer_directly)
from fillers import pick_generic

app = FastAPI(title="Zopro")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SPECIALISTS = {
    "internship": ("Internship & Career Assistant", ask_internship_buddy),
    "zmoney": ("Zmoney Analyst", ask_zmoney),
    "hungryvar": ("Hungryvar Assistant", ask_hungryvar),
    "calendar": ("Calendar Assistant", ask_calendar),
    "mail": ("Mail Assistant", ask_gmail),
    "research": ("Research Assistant", ask_researcher),
    "apps": ("Mac Assistant", ask_apps),
}


class Question(BaseModel):
    question: str
    spoken: bool = False
    followup: bool = False


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/status")
def status():
    """Live figures for the workspace tiles. Real sources only — anything
    unreachable reports available: false rather than a placeholder."""
    from status import full_status
    out = full_status()
    out["speaking"] = _is_speaking()
    return out


@app.get("/speaking")
def speaking_state():
    """Cheap poll target for the Shush button and follow-up-mic timing.
    Unlike /status this does no external work — no yfinance, Gmail, or
    Supabase calls — just checks whether the say process is still running."""
    live = _is_speaking()
    return {"speaking": live, "kind": _speaking["kind"] if live else None}


def _speak_now(text: str):
    """Fire-and-forget TTS, used for the voice filler said while the real
    answer is still being generated."""
    import shutil, subprocess
    if not shutil.which("say"):
        return
    _speaking["proc"] = subprocess.Popen(["say", "-v", "Jamie (Premium)", "-r", "185", text])
    _speaking["kind"] = "filler"


DB_PATH = Path(__file__).parent.parent / "data" / "zopro.db"
SESSION_GAP = 30 * 60


def _init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(DB_PATH)) as conn, conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            route TEXT,
            question TEXT NOT NULL,
            answer TEXT)""")


_init_db()


def _session_and_history():
    """Reuse the latest session unless it has been quiet for SESSION_GAP.
    Returns its last 3 turns, oldest first."""
    with contextlib.closing(sqlite3.connect(DB_PATH)) as conn:
        last = conn.execute(
            "SELECT session_id, timestamp FROM turns ORDER BY id DESC LIMIT 1").fetchone()
        if not last or time.time() - last[1] > SESSION_GAP:
            return uuid.uuid4().hex, []
        rows = conn.execute(
            "SELECT question, answer FROM turns WHERE session_id = ? ORDER BY id DESC LIMIT 3",
            (last[0],)).fetchall()
    return last[0], rows[::-1]


def _save_turn(session_id, route, question, answer):
    with contextlib.closing(sqlite3.connect(DB_PATH)) as conn, conn:
        conn.execute(
            "INSERT INTO turns (session_id, timestamp, route, question, answer) VALUES (?, ?, ?, ?, ?)",
            (session_id, time.time(), route, question, answer))


def _with_history(question, history):
    if not history:
        return question
    turns = "\n\n".join(f"Q: {hq}\nA: {(ha or '')[:500]}" for hq, ha in history)
    return ("Recent conversation, only for resolving references like \"it\" or "
            "\"tomorrow\". Do not act on earlier requests again.\n\n"
            f"{turns}\n\nCurrent question: {question}")


def _for_classifier(question, history):
    if not history:
        return question
    earlier = " / ".join(hq for hq, _ in history)
    return f"(earlier in this conversation: {earlier}) {question}"


@app.post("/ask")
def ask(q: Question):
    """Classify, dispatch, and return the answer plus which specialist handled it.
    The route is returned separately so the UI can show delegation as it happens."""
    question = q.question.strip()
    if not question:
        return {"error": "Empty question."}

    if q.spoken and not q.followup:
        _speak_now(pick_generic())

    try:
        session_id, history = _session_and_history()
    except sqlite3.Error as e:
        print(f"[turns] history unavailable: {e}")
        session_id, history = uuid.uuid4().hex, []

    try:
        route = classify(_for_classifier(question, history))
    except Exception as e:
        return {"error": f"Classifier failed: {e}"}

    name, handler = SPECIALISTS.get(route, ("Zopro", answer_directly))
    prompt = _with_history(question, history)

    # CrewAI prints verbose agent output to stdout; swallow it so it doesn't
    # interleave with the server log.
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            if handler is answer_directly:
                answer = answer_directly(prompt, first_turn=not history)
            else:
                answer = handler(prompt)
    except Exception as e:
        return {"route": route, "specialist": name, "error": str(e)}

    answer = str(answer)
    try:
        _save_turn(session_id, route, question, answer)
    except sqlite3.Error as e:
        print(f"[turns] save failed: {e}")
    return {"route": route, "specialist": name, "answer": answer}


_whisper = None


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Local speech to text. Audio never leaves the machine."""
    global _whisper
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return {"error": "Voice needs faster-whisper. Run: pip install faster-whisper"}

    if _whisper is None:
        _whisper = WhisperModel("base.en", device="cpu", compute_type="int8")

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(await audio.read())
        path = f.name
    try:
        segments, _ = _whisper.transcribe(path, beam_size=1)
        return {"text": " ".join(x.text for x in segments).strip()}
    except Exception as e:
        return {"error": f"Transcription failed: {e}"}
    finally:
        os.unlink(path)


class Speech(BaseModel):
    text: str


@app.post("/speak")
def speak(s: Speech):
    """Read text aloud with the macOS voice. Strips markdown so it doesn't
    pronounce asterisks, and caps length so a long answer isn't read forever."""
    import re, subprocess, shutil
    if not shutil.which("say"):
        return {"error": "say not available"}
    t = re.sub(r"[*_`#>\[\]()]", "", s.text)
    t = re.sub(r"https?://\S+", "link", t)
    t = re.sub(r"\s+", " ", t).strip()[:1200]
    if not t:
        return {"ok": False}
    _speaking["proc"] = subprocess.Popen(["say", "-v", "Jamie (Premium)", "-r", "185", t])
    _speaking["kind"] = "answer"
    return {"ok": True}


@app.post("/stop")
def stop_all():
    """Stop speech, clear any pending wake, and silence the listener briefly."""
    import subprocess, time
    subprocess.run(["pkill", "-f", "^say "], check=False)
    _speaking["proc"] = None
    _speaking["kind"] = None
    _wake_flag["t"] = 0.0
    return {"ok": True}


@app.post("/shush")
def shush():
    """Stop whatever is being spoken."""
    import subprocess
    subprocess.run(["pkill", "-f", "^say "], check=False)
    _speaking["proc"] = None
    _speaking["kind"] = None
    return {"ok": True}


_speaking = {"proc": None, "kind": None}


def _is_speaking():
    p = _speaking["proc"]
    return p is not None and p.poll() is None


_wake_flag = {"t": 0.0}


@app.post("/wake")
def wake():
    """Wake word heard. The UI polls /woke and starts recording."""
    import time
    if _is_speaking():
        return {"ok": False, "reason": "speaking"}
    _wake_flag["t"] = time.time()
    return {"ok": True}


@app.get("/woke")
def woke():
    """True if the wake word fired in the last 5 seconds. Clears on read."""
    import time
    t = _wake_flag["t"]
    if t and time.time() - t < 5:
        _wake_flag["t"] = 0.0
        return {"woke": True}
    return {"woke": False}


_wake_proc = {"p": None}


@app.post("/wake/start")
def wake_start():
    """Start the wake-word listener. The mic is only open while this runs."""
    import subprocess, sys, os
    p = _wake_proc["p"]
    if p and p.poll() is None:
        return {"on": True}
    _wake_proc["p"] = subprocess.Popen(
        [sys.executable, os.path.join(os.path.dirname(__file__), "wake.py")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"on": True}


@app.post("/wake/stop")
def wake_stop():
    """Stop the listener and close the microphone."""
    p = _wake_proc["p"]
    if p and p.poll() is None:
        p.terminate()
    _wake_proc["p"] = None
    return {"on": False}


@app.get("/wake/state")
def wake_state():
    p = _wake_proc["p"]
    return {"on": bool(p and p.poll() is None)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8420)

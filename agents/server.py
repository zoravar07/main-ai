import io
import os
import contextlib
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


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/status")
def status():
    """Live figures for the workspace tiles. Real sources only — anything
    unreachable reports available: false rather than a placeholder."""
    from status import full_status
    import time
    out = full_status()
    out["speaking"] = time.time() < _speaking["until"]
    return out


@app.get("/speaking")
def speaking_state():
    """Cheap poll target for the Shush button and follow-up-mic timing.
    Unlike /status this does no external work — no yfinance, Gmail, or
    Supabase calls — just reads one in-memory timestamp."""
    import time
    return {"speaking": time.time() < _speaking["until"]}


def _speak_now(text: str):
    """Fire-and-forget TTS, used for the voice filler said while the real
    answer is still being generated."""
    import shutil, subprocess, time
    if not shutil.which("say"):
        return
    _speaking["until"] = time.time() + max(3, len(text) / 14)
    subprocess.Popen(["say", "-v", "Jamie (Premium)", "-r", "185", text])


@app.post("/ask")
def ask(q: Question):
    """Classify, dispatch, and return the answer plus which specialist handled it.
    The route is returned separately so the UI can show delegation as it happens."""
    question = q.question.strip()
    if not question:
        return {"error": "Empty question."}

    if q.spoken:
        _speak_now(pick_generic())

    try:
        route = classify(question)
    except Exception as e:
        return {"error": f"Classifier failed: {e}"}

    name, handler = SPECIALISTS.get(route, ("Zopro", answer_directly))

    # CrewAI prints verbose agent output to stdout; swallow it so it doesn't
    # interleave with the server log.
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            answer = handler(question)
    except Exception as e:
        return {"route": route, "specialist": name, "error": str(e)}

    return {"route": route, "specialist": name, "answer": str(answer)}


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
    import time
    _speaking["until"] = time.time() + max(3, len(t) / 14)
    subprocess.Popen(["say", "-v", "Jamie (Premium)", "-r", "185", t])
    return {"ok": True}


@app.post("/stop")
def stop_all():
    """Stop speech, clear any pending wake, and silence the listener briefly."""
    import subprocess, time
    subprocess.run(["pkill", "-f", "^say "], check=False)
    _speaking["until"] = 0.0
    _wake_flag["t"] = 0.0
    return {"ok": True}


@app.post("/shush")
def shush():
    """Stop whatever is being spoken."""
    import subprocess
    subprocess.run(["pkill", "-f", "^say "], check=False)
    _speaking["until"] = 0.0
    return {"ok": True}


_speaking = {"until": 0.0}

_wake_flag = {"t": 0.0}


@app.post("/wake")
def wake():
    """Wake word heard. The UI polls /woke and starts recording."""
    import time
    if time.time() < _speaking["until"]:
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

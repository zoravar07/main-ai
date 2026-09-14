"""Wake-word listener for Zopro.

Runs a small local model (openWakeWord) over the microphone. Nothing leaves the
machine and nothing is recorded until the wake word fires. On a hit it brings
the Zopro window forward and tells it to start listening.

Run it with:  python3 wake.py
Stop it with: Ctrl+C
"""

import subprocess
import sys
import time

import numpy as np
import pyaudio
import requests
from openwakeword.model import Model

WAKE = "hey_jarvis"          # swap for a custom model path later
THRESHOLD = 0.6              # raise if it false-triggers, lower if it misses
COOLDOWN = 3.0               # seconds to ignore after a hit
API = "http://127.0.0.1:8420"

CHUNK = 1280                 # 80ms at 16kHz, what the model expects
RATE = 16000


def bring_forward():
    subprocess.run(
        ["osascript", "-e", 'tell application "Zopro" to activate'],
        check=False, capture_output=True)


def main():
    print("Downloading models if needed...")
    try:
        import openwakeword
        openwakeword.utils.download_models()
    except Exception as e:
        print(f"Model download failed: {e}")

    try:
        model = Model(wakeword_models=[WAKE], inference_framework="onnx")
    except Exception as e:
        print(f"Could not load '{WAKE}': {e}")
        sys.exit(1)

    pa = pyaudio.PyAudio()
    stream = pa.open(format=pyaudio.paInt16, channels=1, rate=RATE,
                     input=True, frames_per_buffer=CHUNK)

    print(f"Listening for '{WAKE.replace('_', ' ')}'. Ctrl+C to stop.")
    last = 0.0

    try:
        while True:
            audio = np.frombuffer(stream.read(CHUNK, exception_on_overflow=False),
                                  dtype=np.int16)
            scores = model.predict(audio)
            score = scores.get(WAKE, 0)

            if score > THRESHOLD and time.time() - last > COOLDOWN:
                last = time.time()
                print(f"  heard it ({score:.2f})")
                bring_forward()
                try:
                    requests.post(f"{API}/wake", timeout=2)
                except Exception:
                    pass
                model.reset()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


if __name__ == "__main__":
    main()

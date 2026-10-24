"""Windows screenshot guidance client and pure coordinate/flight helpers."""
import base64
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import io
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from PIL import ImageGrab

@dataclass
class Capture:
    image: object
    bounds: tuple
    title: str
    window: int

def capture_screen(user32):
    # Only the primary monitor, with physical coordinates. The app enables DPI awareness.
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    user32.GetForegroundWindow.restype = wintypes.HWND
    handle = user32.GetForegroundWindow()
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW(handle, title, 512)
    image = ImageGrab.grab(bbox=(0, 0, width, height), all_screens=False)
    return Capture(image, (0, 0, width, height), title.value[:160], handle)

def target_rect(target, bounds):
    left, top, width, height = bounds
    x, y, w, h = (target[k] for k in ("x", "y", "width", "height"))
    if min(x, y) < 0 or min(w, h) <= 0 or x + w > 1000 or y + h > 1000:
        raise ValueError("Target is outside the screenshot")
    return (left + round(x * width / 1000), top + round(y * height / 1000),
            max(1, round(w * width / 1000)), max(1, round(h * height / 1000)))

def flight_point(start, end, progress):
    # Adapted from Clicky for Windows _begin_flight/_tick (MIT).
    # Copyright (c) 2026 Shashank Singh. See THIRD_PARTY_NOTICES.md.
    import math
    lp = max(0.0, min(1.0, progress))
    t = lp * lp * (3.0 - 2.0 * lp)
    omt = 1.0 - t
    distance = math.hypot(end[0] - start[0], end[1] - start[1])
    control = ((start[0] + end[0]) / 2,
               (start[1] + end[1]) / 2 - min(distance * .22, 90.0))
    x = omt * omt * start[0] + 2 * omt * t * control[0] + t * t * end[0]
    y = omt * omt * start[1] + 2 * omt * t * control[1] + t * t * end[1]
    return round(x), round(y)

def guide(capture, goal, history, backend_url="http://127.0.0.1:8000"):
    image = capture.image.copy().convert("RGB")
    image.thumbnail((1600, 1200))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=82)
    payload = {"goal": goal, "title": capture.title, "language": "en",
               "screenshot": base64.b64encode(output.getvalue()).decode("ascii"),
               "mime_type": "image/jpeg", "history": history[-4:]}
    try:
        with httpx.Client(timeout=40, trust_env=False) as client:
            response = client.post(backend_url + "/screen-step", json=payload)
        if not response.is_success:
            try:
                detail = response.json().get("detail", "Screen guidance unavailable")
            except ValueError:
                detail = "Screen guidance unavailable"
            raise RuntimeError(str(detail)[:300])
        return response.json()
    except httpx.RequestError as exc:
        raise RuntimeError("Start the Snow Ball backend, then try again.") from exc

class Speaker:
    def __init__(self):
        self.process = None
        self.audio_path = None

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=3)
        self.process = None
        if self.audio_path:
            try:
                Path(self.audio_path).unlink(missing_ok=True)
            except OSError:
                pass
            self.audio_path = None

    def say(self, text, language='ml'):
        self.stop()
        if language == 'ml':
            import os
            fd, self.audio_path = tempfile.mkstemp(prefix='snowball-voice-', suffix='.mp3')
            os.close(fd)
            encoded_text = base64.b64encode(text.encode('utf-8')).decode('ascii')
            self.process = subprocess.Popen(
                [sys.executable, '-m', 'desktop.speech_malayalam',
                 '--text', encoded_text, '--audio', self.audio_path],
                cwd=str(Path(__file__).resolve().parents[1]),
                creationflags=subprocess.CREATE_NO_WINDOW)
            return
        # Prefer a gentle female voice, with a small pitch lift rather than a squeak.
        # Escape spoken text before placing it inside SSML.
        from xml.sax.saxutils import escape
        ssml = ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
                '<prosody pitch="+12%" rate="-8%" volume="90">'
                + escape(text) + '</prosody></speak>')
        data = base64.b64encode(ssml.encode("utf-8")).decode("ascii")
        script = ("Add-Type -AssemblyName System.Speech; "
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "try { $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female) } catch {} ; "
                  "$s.SpeakSsml([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + data + "')))")
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        self.process = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            creationflags=subprocess.CREATE_NO_WINDOW)


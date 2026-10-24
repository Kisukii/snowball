"""Run two live Gemini checks using synthetic data only; never prints API keys."""
import base64
import io
import json
import os
import time
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient
from backend.main import app

def main():
    client = TestClient(app)
    report = {"mode": os.getenv("PAWLY_MODE", "gemini"),
              "model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
              "configured": bool(os.getenv("GEMINI_API_KEY")), "checks": []}
    if not report["configured"]:
        print(json.dumps(report))
        return 1
    request = {"session_id": "live-diagnostic", "goal": "Show me Track application",
               "language": "en", "event": "start",
               "page": {"url": "https://example.com", "title": "Citizen services demo",
                        "elements": [{"id": "track", "tag": "button", "text": "Track application"},
                                     {"id": "help", "tag": "button", "text": "Contact help"}]}}
    began = time.monotonic()
    response = client.post("/next-step", json=request)
    data = response.json()
    report["checks"].append({"kind": "page-controls", "status": response.status_code,
        "passed": response.status_code == 200 and data.get("element_id") == "track",
        "seconds": round(time.monotonic() - began, 2), "response": data})
    image = Image.new("RGB", (800, 450), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 26)
    except OSError:
        font = ImageFont.load_default(size=26)
    draw.text((35, 35), "Citizen services — demonstration", fill="black", font=font)
    draw.rounded_rectangle((250, 170, 600, 245), radius=12, fill="#642fa0")
    draw.text((285, 191), "Track application", fill="white", font=font)
    out = io.BytesIO()
    image.save(out, "PNG")
    began = time.monotonic()
    response = client.post("/screen-step", json={"goal": "Show me the Track application button",
        "screenshot": base64.b64encode(out.getvalue()).decode(), "mime_type": "image/png",
        "title": "Synthetic citizen services demo"})
    data = response.json()
    target = data.get("target")
    inside = bool(target and 250 <= (target["x"] + target["width"] / 2) * .8 <= 600
                  and 170 <= (target["y"] + target["height"] / 2) * .45 <= 245)
    report["checks"].append({"kind": "screenshot", "status": response.status_code,
        "passed": response.status_code == 200 and inside,
        "seconds": round(time.monotonic() - began, 2), "response": data})
    report["passed"] = all(c["passed"] for c in report["checks"])
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())


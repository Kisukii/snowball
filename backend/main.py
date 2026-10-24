import asyncio
import json
import os
import re
import time
import httpx
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from anthropic import AsyncAnthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from dotenv import load_dotenv

from backend.prompts import SYSTEM_PROMPT

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


app = FastAPI(title="Snow Ball", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "PAWLY_ALLOWED_ORIGINS",
        "http://localhost:8000",
    ).split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

MAX_BYTES = 24000
SESSION_TTL = 3600
sessions = OrderedDict()

SENSITIVE = re.compile(
    r"password|passcode|otp|one.time|card|cvv|cvc|aadhaar|aadhar|pin\b",
    re.I,
)


class Element(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(max_length=32)
    tag: str = Field(max_length=12)
    type: str = Field(default="", max_length=24)
    text: str = Field(default="", max_length=80)
    label: str = Field(default="", max_length=80)
    role: str = Field(default="", max_length=32)
    context: str = Field(default="", max_length=120)
    expanded: str = Field(default="", max_length=8)
    position: str = Field(default="", max_length=24)


class Page(BaseModel):
    url: str = Field(max_length=300)
    title: str = Field(max_length=80)
    elements: list[Element] = Field(max_length=100)
    context: str = Field(default="", max_length=600)

    @field_validator("url")
    @classmethod
    def strip_url(cls, value):
        url = urlsplit(value)

        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
        ):
            raise ValueError("Expected a web URL")

        return urlunsplit(
            (url.scheme, url.netloc, url.path, "", "")
        )


class History(BaseModel):
    step: int = Field(ge=0)
    instruction: str = Field(max_length=160)
    element_id: str | None = Field(default=None, max_length=32)


class WrongClick(BaseModel):
    clicked_element_id: str | None = Field(
        default=None,
        max_length=32,
    )
    expected_element_id: str = Field(max_length=32)


class StepRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    goal: str = Field(min_length=1, max_length=300)
    language: str = Field(pattern=r"^(hi|en|ta)$")
    page: Page
    history: list[History] = Field(
        default_factory=list,
        max_length=4,
    )
    event: str = Field(
        pattern=r"^(start|clicked_target|wrong_click|stuck)$"
    )
    wrong_click: WrongClick | None = None


class StepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element_id: str | None
    instruction: str = Field(min_length=1, max_length=240)
    instruction_local: str = Field(min_length=1, max_length=300)
    icon: str = Field(min_length=1, max_length=12)
    warning: str | None = Field(default=None, max_length=300)
    done: bool = False

    @field_validator("instruction_local")
    @classmethod
    def short_instruction(cls, value):
        if len(value.split()) > 20:
            raise ValueError("Instruction exceeds 20 words")

        return value


TEXT = {
    "hi": (
        "पन्ना देखें और अपना अगला कदम चुनें।",
        "सुरक्षा के लिए यहाँ निजी जानकारी न भरें।",
        "इस जगह पर क्लिक करें।",
    ),
    "en": (
        "Look at the page and choose your next step.",
        "For safety, do not enter private information here.",
        "Click this control.",
    ),
    "ta": (
        "பக்கத்தைப் பார்த்து அடுத்த படியைத் தேர்ந்தெடுக்கவும்.",
        "பாதுகாப்பிற்காக இங்கே தனிப்பட்ட தகவல்களை உள்ளிட வேண்டாம்.",
        "இந்த இடத்தில் அழுத்தவும்.",
    ),
}

MOCK_MODE_WARNING = {
    "hi": (
        "डेमो मोड चालू है; यह लक्ष्य के अनुसार कदम नहीं चुन सकता। "
        "PAWLY_MODE=claude और ANTHROPIC_API_KEY सेट करके बैकएंड फिर शुरू करें।"
    ),
    "en": (
        "Demo mode is active, so Snow Ball cannot choose goal-aware steps. "
        "Run start_backend.bat to enable Gemini guidance with your API key."
    ),
    "ta": (
        "டெமோ பயன்முறையில் இலக்கிற்கான படிகளைத் தேர்ந்தெடுக்க முடியாது. "
        "PAWLY_MODE=claude மற்றும் ANTHROPIC_API_KEY அமைத்து பின்தளத்தை மீண்டும் தொடங்கவும்."
    ),
}


def fallback(req, warning=None):
    return StepResponse(
        element_id=None,
        instruction="Please review the page.",
        instruction_local=TEXT[req.language][0],
        icon="🐾",
        warning=warning,
        done=False,
    )


def trusted(url):
    parsed = urlsplit(url)

    hosts = {
        host.strip().lower()
        for host in os.getenv(
            "PAWLY_TRUSTED_HOSTS",
            "irctc.co.in,www.irctc.co.in",
        ).split(",")
    }

    return (
        parsed.scheme == "https"
        and parsed.hostname in hosts
    )


def safe_response(req, response):
    elements = {
        element.id: element
        for element in req.page.elements
    }

    if (
        response.element_id is not None
        and response.element_id not in elements
    ):
        raise ValueError("Unknown element_id")

    target = elements.get(response.element_id)

    if target:
        description = " ".join(
            [target.text, target.label, target.type]
        )

        if (
            SENSITIVE.search(description)
            and not trusted(req.page.url)
        ):
            return fallback(req, TEXT[req.language][1])

    if response.done and response.element_id is not None:
        raise ValueError(
            "Completed response must not point to a control"
        )

    return response


@app.get("/health")
def health():
    mode = os.getenv("PAWLY_MODE", "gemini").lower()

    return {
        "status": "ok",
        "capabilities": ["page-controls", "screen-guidance", "desktop-interface", "malayalam-voice"],
        "model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite") if mode == "gemini" else os.getenv("PAWLY_MODEL", "claude-haiku-4-5-20251001"),
        "mode": mode,
        "configured": (
            mode == "mock"
            or (mode == "gemini" and bool(os.getenv("GEMINI_API_KEY")))
            or (mode == "claude" and bool(os.getenv("ANTHROPIC_API_KEY")))
        ),
    }


@app.post("/next-step", response_model=StepResponse)
async def next_step(request: Request):
    body = bytearray()

    async for chunk in request.stream():
        body.extend(chunk)

        if len(body) > MAX_BYTES:
            raise HTTPException(
                413,
                "Page snapshot must be under 24 KB",
            )

    try:
        req = StepRequest.model_validate_json(body)
    except ValueError:
        raise HTTPException(422, "Invalid step request")

    now = time.monotonic()

    for key in list(sessions):
        if now - sessions[key]["updated"] > SESSION_TTL:
            del sessions[key]

    state = sessions.get(req.session_id)

    if (
        req.event == "start"
        or not state
        or state["goal"] != req.goal
    ):
        state = {
            "goal": req.goal,
            "steps": 0,
            "updated": now,
        }

    sessions[req.session_id] = state
    sessions.move_to_end(req.session_id)

    while len(sessions) > 500:
        sessions.popitem(last=False)

    state["updated"] = now

    if req.event == "clicked_target":
        state["steps"] += 1

    mode = os.getenv("PAWLY_MODE", "gemini").lower()

    if mode == "mock":
        return fallback(
            req,
            MOCK_MODE_WARNING[req.language],
        )

    if mode not in {"gemini", "claude"}:
        raise HTTPException(503, "Choose PAWLY_MODE=gemini, claude, or mock")

    key_name = "GEMINI_API_KEY" if mode == "gemini" else "ANTHROPIC_API_KEY"
    if not os.getenv(key_name):
        raise HTTPException(
            503,
            f"Configure {key_name} on the backend, then restart it",
        )

    payload = req.model_dump()
    payload["steps_completed"] = state["steps"]

    client = AsyncAnthropic(
        timeout=2.5,
        max_retries=0,
    ) if mode == "claude" else None

    try:
        async with asyncio.timeout(25):
            for attempt in range(2):
                correction = (
                    "\nPrevious output invalid. Return valid JSON "
                    "and a listed ID only."
                    if attempt
                    else ""
                )

                if mode == "gemini":
                    raw = await gemini_text(payload, correction)
                else:
                    raw = await claude_text(client, payload, correction)

                try:
                    response = StepResponse.model_validate_json(raw)
                    return safe_response(req, response)
                except ValueError:
                    continue

        return fallback(req, "Could not identify a reliable next step. Please try a more specific goal.")

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            503,
            "Guidance temporarily unavailable. Check your connection and try again.",
        ) from exc
    finally:
        if client is not None:
            await client.close()


async def gemini_text(payload, correction, *, image=None, schema=None, system=None):
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        raise HTTPException(503, "GEMINI_MODEL must be a valid model name")
    parts = [{"text": json.dumps(payload, ensure_ascii=False) + correction}]
    if image:
        parts.append({"inline_data": {"mime_type": image[0], "data": image[1]}})
    async with httpx.AsyncClient(timeout=30 if image else 10) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
            json={
                "systemInstruction": {"parts": [{"text": system or SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": schema or StepResponse.model_json_schema(),
                    "maxOutputTokens": 1024,
                },
            },
        )
    if response.status_code in {400, 401, 403}:
        raise HTTPException(503, "Gemini rejected the request. Check your API key, model access, and region in Google AI Studio.")
    if response.status_code == 429:
        raise HTTPException(503, "Gemini free-tier quota or rate limit reached. Wait before trying again and check Google AI Studio usage.")
    if response.status_code == 404:
        raise HTTPException(503, "Gemini model unavailable. Set GEMINI_MODEL to a model available in Google AI Studio.")
    response.raise_for_status()
    candidates = response.json().get("candidates", [])
    if not candidates:
        raise HTTPException(503, "Gemini could not provide guidance for this request. Try rephrasing your goal.")
    return "".join(
        part.get("text", "")
        for part in candidates[0].get("content", {}).get("parts", [])
        if not part.get("thought")
    )


async def claude_text(client, payload, correction):
    message = await client.messages.create(
        model=os.getenv("PAWLY_MODEL", "claude-haiku-4-5-20251001"),
        max_tokens=320,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False) + correction,
        }],
    )
    return "".join(
        block.text for block in message.content if block.type == "text"
    )



# Register screenshot guidance after the shared provider is defined.
from backend import vision  # noqa: E402,F401
from backend import desktop_guidance  # noqa: E402,F401
from backend import transcription  # noqa: E402,F401

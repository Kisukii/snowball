import json
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from backend import main


class GeminiGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"PAWLY_MODE": "gemini", "GEMINI_API_KEY": "test-key"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = TestClient(main.app)
        self.payload = {
            "session_id": "test", "goal": "Show sign in", "language": "en",
            "event": "start", "page": {
                "url": "https://example.com", "title": "Example",
                "elements": [{"id": "e1", "tag": "button", "text": "Sign in"}],
            },
        }
        self.step = {
            "element_id": "e1", "instruction": "Click Sign in.",
            "instruction_local": "Click Sign in.", "icon": "paw",
            "warning": None, "done": False,
        }

    def test_missing_key(self):
        os.environ.pop("GEMINI_API_KEY", None)
        self.assertFalse(self.client.get("/health").json()["configured"])
        response = self.client.post("/next-step", json=self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertIn("GEMINI_API_KEY", response.json()["detail"])

    def test_target_selected(self):
        with patch.object(main, "gemini_text", AsyncMock(return_value=json.dumps(self.step))):
            response = self.client.post("/next-step", json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["element_id"], "e1")

    def test_unknown_target_never_reaches_cat(self):
        self.step["element_id"] = "invented"
        with patch.object(main, "gemini_text", AsyncMock(return_value=json.dumps(self.step))) as generate:
            response = self.client.post("/next-step", json=self.payload)
        self.assertEqual(generate.await_count, 2)
        self.assertIsNone(response.json()["element_id"])

    def test_sensitive_target_is_blocked(self):
        self.payload["page"]["elements"][0]["text"] = "Password"
        with patch.object(main, "gemini_text", AsyncMock(return_value=json.dumps(self.step))):
            response = self.client.post("/next-step", json=self.payload)
        self.assertIsNone(response.json()["element_id"])
        self.assertIn("private information", response.json()["warning"])

    def test_rest_request_and_errors(self):
        real_client = httpx.AsyncClient
        for status in [200, 400, 403, 404, 429, 500]:
            with self.subTest(status=status):
                def handle(request):
                    self.assertEqual(request.headers["x-goog-api-key"], "test-key")
                    self.assertNotIn("test-key", str(request.url))
                    body = json.loads(request.content)
                    self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
                    self.assertIn("responseJsonSchema", body["generationConfig"])
                    return httpx.Response(status, json={"candidates": [{"content": {"parts": [{"text": json.dumps(self.step)}]}}]})

                with patch.object(main.httpx, "AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs)):
                    response = self.client.post("/next-step", json=self.payload)
                self.assertEqual(response.status_code, 200 if status == 200 else 503)
                self.assertNotIn("test-key", response.text)

    def test_claude_still_routes_to_claude(self):
        os.environ.update(PAWLY_MODE="claude", ANTHROPIC_API_KEY="test-key")
        with patch.object(main, "claude_text", AsyncMock(return_value=json.dumps(self.step))) as generate:
            response = self.client.post("/next-step", json=self.payload)
        self.assertEqual(response.status_code, 200)
        generate.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()

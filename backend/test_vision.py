import base64
import io
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from PIL import Image
from fastapi.testclient import TestClient
from backend import main
from backend import vision
from desktop.screen import target_rect, flight_point

class ScreenGuidanceTests(unittest.TestCase):
    def setUp(self):
        image = Image.new("RGB", (800, 450), "white")
        stream = io.BytesIO()
        image.save(stream, "PNG")
        self.payload = {"goal": "Find Track application", "mime_type": "image/png",
                        "screenshot": base64.b64encode(stream.getvalue()).decode()}
        self.result = {"instruction": "Click Track application.", "instruction_local": "Click Track application.",
                       "target_label": "Track application", "target": {"x": 300, "y": 400, "width": 400, "height": 160},
                       "confidence": .95, "warning": None, "done": False}
        self.env = patch.dict(os.environ, {"PAWLY_MODE": "gemini", "GEMINI_API_KEY": "test-key"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = TestClient(main.app)

    def call(self):
        with patch.object(vision, "gemini_text", AsyncMock(return_value=json.dumps(self.result))):
            return self.client.post("/screen-step", json=self.payload)

    def test_screenshot_target(self):
        response = self.call()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["target"]["x"], 300)

    def test_found_target_is_not_premature_completion(self):
        self.result["done"] = True
        response = self.call().json()
        self.assertFalse(response["done"])
        self.assertIsNotNone(response["target"])

    def test_ambiguous_or_warning_never_points(self):
        for changes in [{"confidence": .5}, {"warning": "Please handle this payment yourself."}]:
            with self.subTest(changes=changes):
                original = self.result.copy()
                self.result.update(changes)
                self.assertIsNone(self.call().json()["target"])
                self.result = original

    def test_invalid_image_never_reaches_provider(self):
        self.payload["screenshot"] = "not-an-image" * 8
        with patch.object(vision, "gemini_text", AsyncMock()) as provider:
            self.assertEqual(self.client.post("/screen-step", json=self.payload).status_code, 422)
            provider.assert_not_awaited()

    def test_outside_box_rejected(self):
        self.result["target"]["x"] = 990
        self.assertEqual(self.call().status_code, 503)

    def test_screenshot_is_inline_not_json_text(self):
        real_client = httpx.AsyncClient
        def handle(request):
            data = json.loads(request.content)
            parts = data["contents"][0]["parts"]
            self.assertNotIn(self.payload["screenshot"], parts[0]["text"])
            self.assertEqual(parts[1]["inline_data"]["data"], self.payload["screenshot"])
            self.assertEqual(parts[1]["inline_data"]["mime_type"], "image/png")
            return httpx.Response(200, json={"candidates":[{"content":{"parts":[{"text":json.dumps(self.result)}]}}]})
        with patch.object(main.httpx, "AsyncClient", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw)):
            self.assertEqual(self.client.post("/screen-step", json=self.payload).status_code, 200)

    def test_primary_monitor_coordinates_and_flight(self):
        self.assertEqual(target_rect({"x":250,"y":200,"width":100,"height":100}, (0,0,1920,1080)),
                         (480,216,192,108))
        self.assertEqual(flight_point((0,0),(500,500),0), (0,0))
        self.assertEqual(flight_point((0,0),(500,500),1), (500,500))
        self.assertLess(flight_point((0,0),(500,500),.5)[1], 250)
        with self.assertRaises(ValueError):
            target_rect({"x":999,"y":0,"width":10,"height":100}, (0,0,1920,1080))

if __name__ == "__main__":
    unittest.main()


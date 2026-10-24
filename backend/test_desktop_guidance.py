import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend import main, desktop_guidance
from desktop.interface import resolve_target
from desktop.screen import Capture, target_rect


class DesktopGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.payload = {'goal': 'Find Personalization', 'title': 'Settings',
                        'elements': [{'id': '42.1', 'name': 'Personalization',
                                      'role': 'Button', 'enabled': True}]}
        self.result = {'element_id': '42.1', 'instruction': 'Click Personalization.',
                       'instruction_local': 'Click Personalization.', 'icon': '🐾',
                       'warning': None, 'done': False}

    def call(self):
        with patch.dict(os.environ, {'PAWLY_MODE': 'gemini', 'GEMINI_API_KEY': 'test'}), \
             patch.object(desktop_guidance, 'gemini_text', AsyncMock(return_value=json.dumps(self.result))) as provider:
            response = self.client.post('/desktop-step', json=self.payload)
            if provider.called:
                self.assertNotIn('image', provider.call_args.kwargs)
            return response

    def test_text_only_guidance(self):
        self.assertEqual(self.call().json()['element_id'], '42.1')

    def test_english_guidance_request(self):
        self.payload['language'] = 'en'
        with patch.dict(os.environ, {'PAWLY_MODE': 'gemini', 'GEMINI_API_KEY': 'test'}), \
             patch.object(desktop_guidance, 'gemini_text', AsyncMock(return_value=json.dumps(self.result))) as provider:
            response = self.client.post('/desktop-step', json=self.payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(provider.call_args.args[0]['language'], 'en')

    def test_unknown_disabled_and_completed_targets_rejected(self):
        self.result['element_id'] = 'invented'
        self.assertEqual(self.call().status_code, 503)
        self.result['element_id'] = '42.1'
        self.payload['elements'][0]['enabled'] = False
        self.assertEqual(self.call().status_code, 503)
        self.payload['elements'][0]['enabled'] = True
        self.result['done'] = True
        self.assertEqual(self.call().status_code, 503)

    def test_warning_removes_target(self):
        self.result['warning'] = 'Handle this step yourself.'
        self.assertIsNone(self.call().json()['element_id'])

    def test_invalid_and_oversized_snapshot(self):
        self.assertEqual(self.client.post('/desktop-step', json={}).status_code, 422)
        self.assertEqual(self.client.post('/desktop-step', content=b'x' * 100001).status_code, 413)

    def test_target_resolved_from_current_controls(self):
        shot = Capture(None, (0, 0, 1920, 1080), 'Settings', 1)
        snapshot = {'elements': [dict(self.payload['elements'][0], rect=[480, 216, 192, 108])]}
        step = resolve_target(self.result, snapshot, shot)
        self.assertEqual(target_rect(step['target'], shot.bounds), (480, 216, 192, 108))
        with self.assertRaises(RuntimeError):
            resolve_target(self.result, {'elements': []}, shot)


if __name__ == '__main__':
    unittest.main()

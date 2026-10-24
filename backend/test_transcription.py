import base64
import json
import os
import queue
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend import main, transcription
from desktop.voice_input import VoiceInput, wav_bytes


class TranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.audio = base64.b64encode(wav_bytes(b'\0' * 32000)).decode()

    def test_malayalam_preserved_and_audio_is_inline(self):
        text = 'കെഎസ്ഇബിയിൽ പരാതി നൽകണം'
        with patch.dict(os.environ, {'PAWLY_MODE': 'gemini', 'GEMINI_API_KEY': 'test'}), \
             patch.object(transcription, 'gemini_text', AsyncMock(return_value=json.dumps({'text': text}))) as provider:
            result = self.client.post('/transcribe', json={'audio': self.audio, 'language': 'ml'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['text'], text)
            self.assertEqual(provider.call_args.kwargs['image'], ('audio/wav', self.audio))

    def test_invalid_audio_never_reaches_model(self):
        with patch.object(transcription, 'gemini_text', AsyncMock()) as provider:
            for audio in ['bad' * 30, base64.b64encode(wav_bytes(b'\0' * 100)).decode(),
                          base64.b64encode(wav_bytes(b'\0' * 32000, 8000)).decode()]:
                self.assertEqual(self.client.post('/transcribe', json={'audio': audio}).status_code, 422)
            provider.assert_not_awaited()

    def test_english_input_uses_english_transcription(self):
        with patch.dict(os.environ, {'PAWLY_MODE': 'gemini', 'GEMINI_API_KEY': 'test'}), \
             patch.object(transcription, 'gemini_text', AsyncMock(return_value='{"text":"Help me file a complaint."}')) as provider:
            result = self.client.post('/transcribe', json={'audio': self.audio, 'language': 'en'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['text'], 'Help me file a complaint.')
            self.assertEqual(provider.call_args.args[0]['language'], 'English')

    def test_oversized_audio_rejected(self):
        self.assertEqual(self.client.post('/transcribe', content=b'x' * 1_310_001).status_code, 413)

    def test_cancel_suppresses_late_results(self):
        events = queue.Queue()
        recorder = VoiceInput(events, 1)
        recorder.cancel()
        recorder.emit('VOICE_RESULT', text='late')
        self.assertTrue(events.empty())
        self.assertTrue(recorder.stopped.is_set())

    def test_truncated_wav_rejected(self):
        truncated = base64.b64encode(wav_bytes(b'\0' * 32000)[:-200]).decode()
        self.assertEqual(self.client.post('/transcribe', json={'audio': truncated}).status_code, 422)


if __name__ == '__main__':
    unittest.main()

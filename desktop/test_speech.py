import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop.speech_malayalam import speech_parts, synthesize


class SpeechTests(unittest.IsolatedAsyncioTestCase):
    def test_mixed_labels_preserved(self):
        text = 'ഇപ്പോൾ "Register Complaint" അമർത്തൂ. "Consumer Number" നൽകൂ.'
        parts = speech_parts(text)
        self.assertEqual(''.join(value for value, voice in parts), text)
        english = [value for value, voice in parts if voice.startswith('en-')]
        self.assertEqual(english, ['Register Complaint', 'Consumer Number'])

    def test_single_language(self):
        self.assertEqual(speech_parts('Search.'), [('Search.', 'en-IN-NeerjaNeural')])
        self.assertEqual(speech_parts('അമർത്തൂ.'), [('അമർത്തൂ.', 'ml-IN-SobhanaNeural')])

    async def test_audio_keeps_sentence_order(self):
        class FakeSpeech:
            def __init__(self, text, voice, **kwargs):
                self.text = text

            async def stream(self):
                yield {'type': 'audio', 'data': self.text.encode('utf-8')}
                yield {'type': 'WordBoundary'}

        text = 'ഇവിടെ Search അമർത്തൂ.'
        with tempfile.TemporaryDirectory() as folder, patch('desktop.speech_malayalam.edge_tts.Communicate', FakeSpeech):
            output = Path(folder) / 'voice.mp3'
            await synthesize(text, output)
            self.assertEqual(output.read_bytes().decode('utf-8'), text)


if __name__ == '__main__':
    unittest.main()

"""Short, explicitly started microphone recordings, held only in memory."""
import base64
import io
import threading
import wave

import httpx


def wav_bytes(pcm, sample_rate=16000):
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(pcm)
    return output.getvalue()


class VoiceInput:
    def __init__(self, events, epoch, language='ml'):
        self.events, self.epoch = events, epoch
        self.language = language
        self.stopped = threading.Event()
        self.cancelled = threading.Event()

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()

    def stop(self):
        self.stopped.set()

    def cancel(self):
        self.cancelled.set()
        self.stop()

    def emit(self, kind, **values):
        if not self.cancelled.is_set():
            self.events.put({'type': kind, 'epoch': self.epoch, **values})

    def run(self):
        import sounddevice as sd
        frames = bytearray()
        try:
            def receive(data, count, timing, status):
                remaining = 16000 * 2 * 30 - len(frames)
                if remaining > 0:
                    frames.extend(bytes(data)[:remaining])
                if len(frames) >= 16000 * 2 * 30:
                    self.stop()

            with sd.RawInputStream(samplerate=16000, channels=1, dtype='int16',
                                   blocksize=1600, callback=receive):
                self.emit('VOICE_LISTENING')
                self.stopped.wait(30)
            if self.cancelled.is_set():
                return
            if len(frames) < 16000:
                raise RuntimeError(self.message('Please speak a little longer and try again.', 'കുറച്ചുകൂടി നേരം സംസാരിക്കൂ. വീണ്ടും ശ്രമിക്കാം.'))
            self.emit('VOICE_TRANSCRIBING')
            payload = {'language': self.language, 'audio': base64.b64encode(wav_bytes(frames)).decode('ascii')}
            frames.clear()
            with httpx.Client(timeout=40, trust_env=False) as client:
                response = client.post('http://127.0.0.1:8000/transcribe', json=payload)
            if not response.is_success:
                raise RuntimeError(self.message('Could not transcribe. Check your internet connection and backend.', 'ശബ്ദം എഴുത്താക്കാൻ കഴിഞ്ഞില്ല. ഇന്റർനെറ്റും ബാക്കെൻഡും പരിശോധിക്കൂ.'))
            text = response.json()['text'].strip()
            if not text:
                raise RuntimeError(self.message('Speech was unclear. Please try again.', 'സംസാരം വ്യക്തമായില്ല. വീണ്ടും ശ്രമിക്കൂ.'))
            self.emit('VOICE_RESULT', text=text)
        except sd.PortAudioError:
            self.emit('VOICE_ERROR', message=self.message('Microphone unavailable. Check Windows microphone permission and your input device.', 'മൈക്രോഫോൺ ലഭ്യമല്ല. Windows മൈക്രോഫോൺ അനുമതിയും ഉപകരണവും പരിശോധിക്കൂ.'))
        except Exception as exc:
            self.emit('VOICE_ERROR', message=str(exc)[:300])
        finally:
            frames.clear()

    def message(self, english, malayalam):
        return english if self.language == 'en' else malayalam

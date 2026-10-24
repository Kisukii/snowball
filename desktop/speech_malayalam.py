"""Cancellable Malayalam speech worker using Edge's online speech service."""
import argparse
import asyncio
import base64
import ctypes
from pathlib import Path
import re
import time

import edge_tts


def speech_parts(text):
    """Keep English labels verbatim and route each language to its own voice."""
    parts = []

    def add(value, voice):
        if not value:
            return
        if not any(c.isalpha() for c in value) and parts:
            parts[-1] = (parts[-1][0] + value, parts[-1][1])
        elif value.strip():
            parts.append((value, voice))

    previous = 0
    for match in re.finditer(r"[A-Za-z][A-Za-z0-9]*(?:[ '\u2019/\-]+[A-Za-z0-9]+)*", text):
        add(text[previous:match.start()], 'ml-IN-SobhanaNeural')
        add(match.group(), 'en-IN-NeerjaNeural')
        previous = match.end()
    add(text[previous:], 'ml-IN-SobhanaNeural')
    return parts


async def synthesize(text, path):
    limit = asyncio.Semaphore(3)

    async def render(value, voice):
        async with limit:
            audio = bytearray()
            async for chunk in edge_tts.Communicate(value, voice, rate='-8%').stream():
                if chunk['type'] == 'audio':
                    audio.extend(chunk['data'])
            return bytes(audio)

    async with asyncio.timeout(60):
        clips = await asyncio.gather(*(render(value, voice) for value, voice in speech_parts(text)))
    # Edge returns the same MP3 encoding for both voices. Keep audio frames in
    # sentence order, excluding the service's word-boundary metadata.
    Path(path).write_bytes(b''.join(clips))


def play(path):
    send = ctypes.windll.winmm.mciSendStringW
    send.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
    send.restype = ctypes.c_uint

    def command(value):
        output = ctypes.create_unicode_buffer(256)
        error = send(value, output, len(output), None)
        if error:
            raise RuntimeError(f'Windows audio playback failed ({error})')
        return output.value

    command(f'open "{path}" type mpegvideo alias snowballvoice')
    try:
        command('play snowballvoice')
        while command('status snowballvoice mode') == 'playing':
            time.sleep(.05)
    finally:
        command('close snowballvoice')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--text', required=True)
    parser.add_argument('--audio', required=True)
    args = parser.parse_args()
    try:
        text = base64.b64decode(args.text).decode('utf-8')
        asyncio.run(synthesize(text, args.audio))
        play(args.audio)
    finally:
        Path(args.audio).unlink(missing_ok=True)


if __name__ == '__main__':
    main()

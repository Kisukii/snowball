import asyncio
import json
import re
import secrets
import threading
from concurrent.futures import Future

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

ORIGIN = re.compile(r"chrome-extension://[a-p]{32}\Z")


class Bridge:
    def __init__(self, token, events, port=8765):
        self.token = token
        self.events = events
        self.port = port
        self.client = None
        self.loop = None
        self.error = None
        self.ready = threading.Event()
        self.thread = None

    @property
    def connected(self):
        return self.client is not None

    def start(self):
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self.thread.start()
        self.ready.wait(3)

        if self.error:
            raise RuntimeError(
                "The companion port is busy. "
                "Close any other Snow Ball desktop app."
            ) from self.error

        if not self.ready.is_set():
            raise RuntimeError("Desktop bridge did not start.")

    def _run(self):
        try:
            asyncio.run(self._serve())
        except Exception as exc:
            self.error = exc
            self.ready.set()
            self.events.put({
                "type": "ERROR",
                "message": "Desktop connection stopped.",
            })

    async def _serve(self):
        self.loop = asyncio.get_running_loop()
        self.stop_event = asyncio.Event()

        async with serve(
            self._handle,
            "127.0.0.1",
            self.port,
            max_size=2048,
            max_queue=8,
            ping_interval=20,
        ):
            self.ready.set()
            await self.stop_event.wait()

    async def _handle(self, socket):
        origin = socket.request.headers.get("Origin", "")

        if not ORIGIN.fullmatch(origin):
            await socket.close(
                1008,
                "Extension origin required",
            )
            return

        try:
            raw = await asyncio.wait_for(socket.recv(), 3)
            auth = json.loads(raw)

            if not isinstance(auth, dict):
                await socket.close(
                    1008,
                    "Invalid pairing message",
                )
                return

            supplied = auth.get("token", "")

            if (
                auth.get("type") != "AUTH"
                or not isinstance(supplied, str)
                or not secrets.compare_digest(
                    supplied,
                    self.token,
                )
            ):
                await socket.close(1008, "Pairing required")
                return

            old = self.client
            self.client = socket

            if old is not None:
                await old.close(
                    1000,
                    "Connected in another browser",
                )

            await socket.send(
                json.dumps({"type": "READY"})
            )

            self.events.put({"type": "CONNECTED"})

            async for raw in socket:
                message = json.loads(raw)

                if not isinstance(message, dict):
                    continue

                if message.get("type") == "PING":
                    await socket.send('{"type":"PONG"}')

                elif message.get("type") == "STATE":
                    mode = message.get("mode")

                    if mode in {
                        "started",
                        "step",
                        "rest",
                        "error",
                        "done",
                    }:
                        text = str(
                            message.get("message", "")
                        )[:300]

                        self.events.put({
                            "type": "STATE",
                            "mode": mode,
                            "message": text,
                        })

        except (
            ConnectionClosed,
            TimeoutError,
            ValueError,
            TypeError,
        ):
            pass

        finally:
            if self.client is socket:
                self.client = None
                self.events.put({
                    "type": "DISCONNECTED"
                })

    def command(self, kind, **data):
        if not self.loop or not self.connected:
            return False

        message = json.dumps({
            "type": kind,
            **data,
        })

        future = asyncio.run_coroutine_threadsafe(
            self._send(message),
            self.loop,
        )

        future.add_done_callback(self._sent)
        return True

    def _sent(self, future: Future):
        if future.exception():
            self.events.put({
                "type": "STATE",
                "mode": "error",
                "message": (
                    "Chrome disconnected. Open a normal "
                    "website and try again."
                ),
            })

    async def _send(self, text):
        if self.client is None:
            raise ConnectionError("Not paired")

        await self.client.send(text)

    def close(self):
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(
                self.stop_event.set
            )

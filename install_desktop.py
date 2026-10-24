from pathlib import Path
from datetime import datetime
import re
import shutil

ROOT = Path(__file__).resolve().parent
EXT = ROOT / "extension"

if not (ROOT / "backend" / "main.py").exists() or not (
    EXT / "content.js"
).exists():
    raise SystemExit(
        "Save this installer inside your existing snowball folder, "
        "beside backend and extension."
    )

FILES = {
    "desktop/__init__.py": "",

    "desktop/requirements.txt": "websockets==15.0.1\n",

    "desktop/bridge.py": r'''
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
''',

    "desktop/app.py": r'''
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import queue
import secrets
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox

from desktop.bridge import Bridge

KEY = "#ff00ff"
PURPLE = "#af7ddd"
OUTLINE = "#563378"
PALE = "#ddc3f5"


def load_config():
    folder = (
        Path(os.getenv("LOCALAPPDATA", str(Path.home())))
        / "SnowBall"
    )
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "companion.json"

    if path.exists():
        config = json.loads(
            path.read_text(encoding="utf-8")
        )

        if (
            isinstance(config.get("token"), str)
            and len(config["token"]) >= 32
        ):
            return path, config

        raise ValueError(
            "Invalid companion settings. Rename "
            "companion.json and restart to re-pair."
        )

    config = {
        "token": secrets.token_urlsafe(32),
        "side": "right",
        "voice": True,
    }

    path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    return path, config


def taskbar_geometry(user32):
    user32.FindWindowW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
    ]
    user32.FindWindowW.restype = wintypes.HWND

    user32.GetWindowRect.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.RECT),
    ]
    user32.GetWindowRect.restype = wintypes.BOOL

    width = user32.GetSystemMetrics(0)
    height = user32.GetSystemMetrics(1)

    rect = wintypes.RECT()
    handle = user32.FindWindowW("Shell_TrayWnd", None)

    if handle and user32.GetWindowRect(
        handle,
        ctypes.byref(rect),
    ):
        if (
            rect.top > height // 2
            and rect.right - rect.left
            > rect.bottom - rect.top
        ):
            return width, height, rect.top

    return width, height, height - 48


class SnowBall:
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.user32.SetProcessDPIAware()

        self.path, self.config = load_config()
        self.events = queue.Queue()

        self.root = tk.Tk()
        self.root.title("Snow Ball")
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY)

        self.root.attributes("-transparentcolor", KEY)
        self.root.attributes("-topmost", True)
        self.root.attributes("-toolwindow", True)

        self.canvas = tk.Canvas(
            self.root,
            width=168,
            height=116,
            bg=KEY,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack()

        self.canvas.bind(
            "<Button-1>",
            lambda event: self.open_chat(),
        )
        self.canvas.bind(
            "<Button-3>",
            self.context_menu,
        )

        self.chat = None
        self.guiding = False
        self.frame = 0
        self.flight_started = None

        self.bridge = Bridge(
            self.config["token"],
            self.events,
        )
        self.bridge.start()

        self.position()
        self.animate()
        self.poll()

    def save(self):
        self.path.write_text(
            json.dumps(self.config),
            encoding="utf-8",
        )

    def position(self):
        width, height, edge = taskbar_geometry(
            self.user32
        )

        self.home_x = (
            28
            if self.config.get("side") == "left"
            else max(0, width - 340)
        )

        # The body rests on the taskbar edge.
        # The paws extend below it.
        self.home_y = max(0, edge - 84)

        self.root.geometry(
            f"168x116+{self.home_x}+{self.home_y}"
        )

    def draw(self, awake=False):
        canvas = self.canvas
        canvas.delete("all")

        wave = round(math.sin(self.frame / 12) * 8)
        tail_sway = round(wave * 0.6)
        breath = round(math.sin(self.frame / 18))

        def pixel(x, y, width, height, color):
            canvas.create_rectangle(
                x, y,
                x + width, y + height,
                fill=color,
                outline="",
            )

        points = [
            42, 78,
            26, 74,
            17, 60,
            15 + tail_sway, 34,
            22 + tail_sway, 25,
        ]

        canvas.create_line(
            *points,
            fill=OUTLINE,
            width=14,
            joinstyle="miter",
            capstyle="butt",
        )
        pixel(5 + tail_sway, 31, 16, 11, OUTLINE)
        pixel(10 + tail_sway, 22, 17, 12, OUTLINE)
        pixel(4 + tail_sway, 41, 16, 10, OUTLINE)
        pixel(17 + tail_sway, 16, 11, 10, OUTLINE)
        pixel(1 + tail_sway, 36, 10, 9, OUTLINE)
        canvas.create_line(
            *points,
            fill=PURPLE,
            width=7,
            joinstyle="miter",
            capstyle="butt",
        )
        pixel(8 + tail_sway, 33, 9, 6, PURPLE)
        pixel(13 + tail_sway, 24, 10, 7, PURPLE)
        pixel(7 + tail_sway, 43, 9, 5, PURPLE)
        pixel(19 + tail_sway, 18, 6, 6, PURPLE)
        pixel(3 + tail_sway, 38, 5, 5, PURPLE)

        pixel(38, 60 + breath, 92, 24, OUTLINE)
        pixel(46, 53 + breath, 68, 32, OUTLINE)
        pixel(44, 61 + breath, 82, 18, PURPLE)
        pixel(50, 57 + breath, 60, 23, PURPLE)
        pixel(54, 75, 66, 8, PALE)

        for x in (60, 113):
            pixel(x, 82, 16, 18, OUTLINE)
            pixel(x + 3, 83, 10, 14, PALE)
            pixel(x + 5, 94, 2, 3, PURPLE)

        head_y = 30 if awake else 35

        pixel(100, head_y, 52, 42, OUTLINE)
        pixel(100, head_y - 8, 12, 16, OUTLINE)
        pixel(140, head_y - 8, 12, 16, OUTLINE)
        pixel(104, head_y + 3, 44, 32, PURPLE)
        pixel(104, head_y - 4, 5, 12, "#e9a8d4")
        pixel(143, head_y - 4, 5, 12, "#e9a8d4")

        blink = awake and self.frame % 100 in range(90, 95)

        if awake and not blink:
            for x in (112, 135):
                pixel(x, head_y + 12, 5, 9, OUTLINE)
                pixel(x, head_y + 12, 2, 2, "white")
        else:
            pixel(110, head_y + 18, 10, 3, OUTLINE)
            pixel(133, head_y + 18, 10, 3, OUTLINE)

        pixel(124, head_y + 25, 6, 3, OUTLINE)

        if not awake:
            canvas.create_text(
                75,
                25 + breath,
                text="z z",
                fill="#9871bc",
                font=("Segoe UI", 12),
            )

    def animate(self):
        self.frame += 1

        self.draw(
            awake=self.guiding or self.chat is not None
        )

        if self.flight_started is not None:
            elapsed = (
                time.monotonic() - self.flight_started
            ) / 0.65

            if elapsed >= 1:
                self.flight_started = None
                self.root.withdraw()
            else:
                y = self.home_y - round(180 * elapsed)
                x = self.home_x - round(
                    35 * math.sin(elapsed * math.pi)
                )

                self.root.geometry(
                    f"168x116+{max(0, x)}+{max(0, y)}"
                )

        elif not self.guiding and self.frame % 30 == 0:
            self.position()

        self.root.after(40, self.animate)

    def show_pet(self):
        self.guiding = False
        self.flight_started = None

        self.position()
        self.root.deiconify()
        self.root.lift()

    def open_chat(self):
        if self.chat and self.chat.winfo_exists():
            self.chat.lift()
            return

        win = self.chat = tk.Toplevel(self.root)
        win.title("Snow Ball")
        win.configure(bg="#faf5ff")
        win.attributes("-topmost", True)
        win.geometry("360x490")
        win.resizable(False, False)

        win.protocol(
            "WM_DELETE_WINDOW",
            self.close_chat,
        )

        tk.Label(
            win,
            text="Hi, I'm Snow Ball",
            font=("Segoe UI", 18, "bold"),
            fg=OUTLINE,
            bg="#faf5ff",
        ).pack(pady=(18, 3))

        tk.Label(
            win,
            text="What would you like help with?",
            bg="#faf5ff",
            fg=OUTLINE,
        ).pack(pady=5)

        self.goal = tk.Text(
            win,
            height=5,
            width=36,
            font=("Segoe UI", 12),
            wrap="word",
        )
        self.goal.pack(padx=18, pady=8)

        tk.Label(
            win,
            text=(
                "Type here, or press Windows + H to dictate.\n"
                "Do not include passwords, OTPs or card details."
            ),
            bg="#faf5ff",
            fg="#776087",
            font=("Segoe UI", 9),
        ).pack()

        tk.Button(
            win,
            text="Navigate me →",
            command=self.navigate,
            bg="#7945ae",
            fg="white",
            font=("Segoe UI", 12, "bold"),
            relief="flat",
            padx=20,
            pady=9,
        ).pack(pady=12)

        row = tk.Frame(win, bg="#faf5ff")
        row.pack()

        tk.Button(
            row,
            text="Next step",
            command=lambda: self.bridge.command(
                "CONTINUE"
            ),
        ).pack(side="left", padx=4)

        tk.Button(
            row,
            text="Come back",
            command=self.rest,
        ).pack(side="left", padx=4)

        self.voice = tk.BooleanVar(
            value=self.config.get("voice", True)
        )

        tk.Checkbutton(
            win,
            text="Read instructions aloud (English)",
            variable=self.voice,
            command=self.settings,
            bg="#faf5ff",
            fg=OUTLINE,
        ).pack(pady=(12, 4))

        self.side = tk.StringVar(
            value=self.config.get("side", "right")
        )

        side_row = tk.Frame(win, bg="#faf5ff")
        side_row.pack()

        tk.Label(
            side_row,
            text="Taskbar side: ",
            bg="#faf5ff",
        ).pack(side="left")

        box = ttk.Combobox(
            side_row,
            textvariable=self.side,
            values=["left", "right"],
            state="readonly",
            width=8,
        )
        box.pack(side="left")

        box.bind(
            "<<ComboboxSelected>>",
            lambda event: self.settings(),
        )

        tk.Button(
            win,
            text="Copy Chrome pairing code",
            command=self.copy_pairing,
        ).pack(pady=10)

        self.status = tk.Label(
            win,
            text=self.connection_text(),
            wraplength=320,
            bg="#faf5ff",
            fg="#776087",
            font=("Segoe UI", 9),
        )
        self.status.pack(padx=12)
        self.goal.focus_set()

    def connection_text(self):
        if self.bridge.connected:
            return (
                "Chrome connected. Open your website, "
                "then Navigate me."
            )

        return (
            "Pair Chrome once: copy the code, open "
            "Snow Ball's Extension options, and paste it there."
        )

    def copy_pairing(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(
            self.config["token"]
        )

        self.status.configure(
            text=(
                "Pairing code copied. Paste it into "
                "Snow Ball's Extension options in Chrome."
            )
        )

    def settings(self):
        self.config.update(
            side=self.side.get(),
            voice=self.voice.get(),
        )
        self.save()

        if not self.guiding:
            self.position()

    def navigate(self):
        goal = self.goal.get(
            "1.0",
            "end",
        ).strip()

        if not goal or len(goal) > 300:
            self.status.configure(
                text=(
                    "Enter a goal between "
                    "1 and 300 characters."
                )
            )
            return

        sent = self.bridge.command(
            "NAVIGATE",
            goal=goal,
            voice=self.voice.get(),
        )

        if not sent:
            self.status.configure(
                text=(
                    "Chrome is not paired. Copy the pairing "
                    "code and open Extension options."
                )
            )
        else:
            self.status.configure(
                text="Sending your goal to Chrome…"
            )

    def rest(self):
        self.bridge.command("STOP")
        self.show_pet()

    def close_chat(self):
        if self.chat:
            self.chat.destroy()
            self.chat = None

        if not self.guiding:
            self.show_pet()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                text = self.connection_text()

                if event["type"] == "DISCONNECTED":
                    self.show_pet()
                    text = (
                        "Chrome disconnected. "
                        "Snow Ball is back on the taskbar."
                    )

                elif event["type"] == "STATE":
                    if event["mode"] == "started":
                        self.guiding = True
                        self.flight_started = (
                            time.monotonic()
                        )
                        text = (
                            event.get("message")
                            or (
                                "Snow Ball is guiding in Chrome. "
                                "Use Next step after entering a field."
                            )
                        )
                    elif event["mode"] == "step":
                        self.guiding = True
                        text = (
                            event.get("message")
                            or "Follow Snow Ball's highlighted step in Chrome."
                        )
                    else:
                        self.show_pet()
                        text = (
                            event.get("message")
                            or "Snow Ball is back on the taskbar."
                        )

                elif event["type"] == "ERROR":
                    text = event["message"]
                    self.show_pet()

                if (
                    self.chat
                    and self.chat.winfo_exists()
                ):
                    self.status.configure(text=text)

        except queue.Empty:
            pass

        self.root.after(100, self.poll)

    def context_menu(self, event):
        menu = tk.Menu(
            self.root,
            tearoff=False,
        )

        menu.add_command(
            label="Chat with Snow Ball",
            command=self.open_chat,
        )
        menu.add_command(
            label="Come back to taskbar",
            command=self.rest,
        )
        menu.add_separator()
        menu.add_command(
            label="Quit Snow Ball",
            command=self.quit,
        )

        menu.tk_popup(
            event.x_root,
            event.y_root,
        )

    def quit(self):
        self.bridge.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    if sys.platform != "win32":
        raise SystemExit(
            "The transparent taskbar companion "
            "requires Windows 10/11."
        )

    try:
        SnowBall().run()
    except Exception as exc:
        messagebox.showerror(
            "Snow Ball",
            str(exc),
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
''',

    "extension/manifest.json": r'''
{
  "manifest_version": 3,
  "name": "Snow Ball — your pixel cat guide",
  "version": "0.3.0",
  "minimum_chrome_version": "116",
  "description": "A purple pixel cat that helps you navigate websites.",
  "permissions": [
    "storage",
    "activeTab",
    "alarms"
  ],
  "host_permissions": [
    "http://localhost:8000/*",
    "http://127.0.0.1:8000/*",
    "http://127.0.0.1:8765/*"
  ],
  "optional_host_permissions": [
    "https://*/*"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "action": {
    "default_title": "Open Snow Ball"
  },
  "options_page": "options.html",
  "content_scripts": [
    {
      "matches": [
        "http://*/*",
        "https://*/*"
      ],
      "js": [
        "sprite.js",
        "pet.js",
        "content.js"
      ],
      "css": [
        "pet.css"
      ],
      "run_at": "document_idle"
    }
  ]
}
''',

    "extension/background.js": r'''
chrome.storage.session.setAccessLevel({
  accessLevel: 'TRUSTED_AND_UNTRUSTED_CONTEXTS'
});

chrome.action.onClicked.addListener(tab => {
  chrome.tabs.sendMessage(
    tab.id,
    { type: 'TOGGLE_WIDGET' }
  ).catch(() => {});
});

const jobs = new Map();

chrome.runtime.onMessage.addListener(
  (message, sender, respond) => {
    if (message.type === 'OPEN_PANEL' && sender.tab) {
      chrome.tabs.sendMessage(
        sender.tab.id,
        { type: 'TOGGLE_WIDGET' }
      ).catch(() => {});

      return;
    }

    if (message.type !== 'GUIDE') return;

    (async () => {
      const {
        backendUrl = 'http://localhost:8000'
      } = await chrome.storage.local.get('backendUrl');

      const url = new URL(backendUrl);

      const local =
        ['localhost', '127.0.0.1'].includes(url.hostname) &&
        url.protocol === 'http:';

      if (url.protocol !== 'https:' && !local) {
        throw new Error('Use HTTPS or a local backend');
      }

      const body = JSON.stringify(message.payload);

      if (new TextEncoder().encode(body).length > 5000) {
        throw new Error('Snapshot too large');
      }

      const key = sender.tab?.id ?? 'panel';

      jobs.get(key)?.abort();

      const controller = new AbortController();
      jobs.set(key, controller);

      const timeout = setTimeout(
        () => controller.abort(),
        12000
      );

      try {
        const response = await fetch(
          `${url.origin}/next-step`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body,
            signal: controller.signal,
            credentials: 'omit'
          }
        );

        if (!response.ok) {
          throw new Error(
            `Backend returned ${response.status}`
          );
        }

        return {
          ok: true,
          step: await response.json()
        };

      } finally {
        clearTimeout(timeout);

        if (jobs.get(key) === controller) {
          jobs.delete(key);
        }
      }
    })()
      .then(respond)
      .catch(() => respond({
        ok: false,
        error: 'Guidance unavailable'
      }));

    return true;
  }
);

chrome.runtime.onMessage.addListener(
  (message, sender, respond) => {
    if (message.type === 'TAB_ID') {
      respond(sender.tab?.id);
    }
  }
);

chrome.tabs.onRemoved.addListener(tabId => {
  chrome.storage.session.remove(`pawly-${tabId}`);
});

importScripts('companion.js');
''',

    "extension/companion.js": r'''
(() => {
  let socket;
  let retry;
  let heartbeat;
  let online = false;
  let guidingTab = null;
  let generation = 0;

  const setStatus = message =>
    chrome.storage.session.set({
      companionOnline: online,
      companionStatus: message
    });

  function broadcast() {
    chrome.tabs.query({}).then(tabs => {
      for (const tab of tabs) {
        chrome.tabs.sendMessage(
          tab.id,
          {
            type: 'COMPANION_PRESENCE',
            online
          }
        ).catch(() => {});
      }
    });
  }

  function state(mode, message = '') {
    if (
      online &&
      socket?.readyState === WebSocket.OPEN
    ) {
      socket.send(JSON.stringify({
        type: 'STATE',
        mode,
        message
      }));
    }
  }

  async function connect() {
    if (
      socket &&
      [
        WebSocket.OPEN,
        WebSocket.CONNECTING
      ].includes(socket.readyState)
    ) {
      return;
    }

    const { companionToken } =
      await chrome.storage.local.get(
        'companionToken'
      );

    if (!companionToken) {
      setStatus(
        'Paste your pairing code to connect.'
      );
      return;
    }

    const attempt = ++generation;

    const connection = new WebSocket(
      'ws://127.0.0.1:8765'
    );

    socket = connection;

    connection.onopen = () => {
      connection.send(JSON.stringify({
        type: 'AUTH',
        token: companionToken
      }));
    };

    connection.onmessage = async event => {
      if (attempt !== generation) return;

      let message;

      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }

      if (message.type === 'READY') {
        online = true;

        setStatus(
          'Connected to your desktop Snow Ball.'
        );

        broadcast();
        clearInterval(heartbeat);

        heartbeat = setInterval(() => {
          if (
            connection.readyState === WebSocket.OPEN
          ) {
            connection.send('{"type":"PING"}');
          }
        }, 20000);

        return;
      }

      if (!online || message.type === 'PONG') {
        return;
      }

      try {
        if (message.type === 'NAVIGATE') {
          if (
            typeof message.goal !== 'string' ||
            !message.goal.trim() ||
            message.goal.length > 300
          ) {
            return;
          }

          const [tab] = await chrome.tabs.query({
            active: true,
            lastFocusedWindow: true
          });

          if (!tab?.id) {
            throw new Error(
              'Open a normal website in Chrome first.'
            );
          }

          const { preferences = {} } =
            await chrome.storage.local.get(
              'preferences'
            );

          const updated = {
            ...preferences,
            language: 'en',
            voice: message.voice !== false
          };

          await chrome.storage.local.set({
            preferences: updated
          });

          await chrome.tabs.sendMessage(
            tab.id,
            {
              type: 'COMPANION_PRESENCE',
              online: true
            }
          );

          await chrome.tabs.sendMessage(
            tab.id,
            {
              type: 'SETTINGS',
              preferences: updated
            }
          );

          const response =
            await chrome.tabs.sendMessage(
              tab.id,
              {
                type: 'START',
                goal: message.goal.trim(),
                language: 'en'
              }
            );

          if (!response?.ok) {
            throw new Error(
              'Refresh your website and try again.'
            );
          }

          guidingTab = tab.id;
          state('started');

        } else if (
          [
            'CONTINUE',
            'STOP',
            'OPEN_CHAT'
          ].includes(message.type)
        ) {
          if (message.type === 'OPEN_CHAT') {
            const [tab] =
              await chrome.tabs.query({
                active: true,
                lastFocusedWindow: true
              });

            if (tab?.id) {
              await chrome.tabs.sendMessage(
                tab.id,
                { type: 'TOGGLE_WIDGET' }
              );
            }

          } else if (guidingTab !== null) {
            await chrome.tabs.sendMessage(
              guidingTab,
              { type: message.type }
            );

            if (message.type === 'STOP') {
              guidingTab = null;
              state('rest');
            }
          }
        }

      } catch (error) {
        guidingTab = null;

        state(
          'error',
          error instanceof Error
            ? error.message.slice(0, 300)
            : 'Open a normal website in Chrome, refresh it, then try again.'
        );
      }
    };

    connection.onclose = event => {
      if (attempt !== generation) return;

      online = false;
      guidingTab = null;
      clearInterval(heartbeat);

      setStatus(
        event.code === 1008
          ? 'Pairing failed. Copy a fresh code from the desktop app.'
          : 'Desktop app is not connected. Start it to reconnect.'
      );

      broadcast();
      clearTimeout(retry);

      retry = setTimeout(connect, 5000);
    };

    connection.onerror = () => {
      connection.close();
    };
  }

  chrome.runtime.onMessage.addListener(
    (message, sender, respond) => {
      if (message.type === 'COMPANION_STATUS') {
        respond({ online });
        return;
      }

      if (
        message.type === 'STEP_UPDATED' &&
        sender.tab
      ) {
        if (!online) return;

        if (
          guidingTab === null &&
          (message.step || message.error) &&
          !message.step?.done
        ) {
          guidingTab = sender.tab.id;
        }

        if (sender.tab.id !== guidingTab) return;

        if (message.error) {
          state('error', message.error);
          guidingTab = null;

        } else if (message.step?.done) {
          state(
            'done',
            message.step.instruction_local
          );
          guidingTab = null;

        } else if (message.step?.warning) {
          state('error', message.step.warning);
          guidingTab = null;

        } else if (message.step) {
          state(
            'step',
            message.step.instruction_local
          );
        }

      } else if (
        message.type === 'COMPANION_REST' &&
        sender.tab?.id === guidingTab
      ) {
        guidingTab = null;
        state('rest');
      }
    }
  );

  chrome.tabs.onRemoved.addListener(tabId => {
    if (tabId === guidingTab) {
      guidingTab = null;

      state(
        'rest',
        'The website tab was closed.'
      );
    }
  });

  chrome.storage.onChanged.addListener(
    (changes, area) => {
      if (
        area === 'local' &&
        changes.companionToken
      ) {
        generation++;
        clearTimeout(retry);
        clearInterval(heartbeat);

        socket?.close();
        socket = null;
        online = false;

        broadcast();
        connect();
      }
    }
  );

  chrome.alarms.create(
    'snowball-companion',
    { periodInMinutes: 0.5 }
  );

  chrome.alarms.onAlarm.addListener(alarm => {
    if (alarm.name === 'snowball-companion') {
      connect();
    }
  });

  connect();
})();
''',

    "extension/options.html": r'''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width,initial-scale=1"
  >
  <title>Snow Ball desktop pairing</title>
  <link rel="stylesheet" href="options.css">
</head>
<body>
  <main>
    <div id="cat"></div>
    <h1>Meet me on your taskbar.</h1>

    <p>
      Start the Snow Ball desktop app.
      Click the cat, then
      <strong>Copy Chrome pairing code</strong>.
      Paste that code here once.
    </p>

    <label for="token">Desktop pairing code</label>
    <input
      id="token"
      type="password"
      autocomplete="off"
      spellcheck="false"
    >

    <button id="pair">Connect to my cat</button>
    <button id="disconnect">Unpair</button>

    <p id="status" role="status">
      Not connected yet.
    </p>

    <p class="note">
      This code connects Chrome to your desktop pet.
      It is separate from your Claude API key.
      Never put an API key here.
    </p>

    <h2>When paired</h2>

    <p>
      Open your website, click the desktop cat,
      type a goal and press
      <strong>Navigate me</strong>.
      Use <strong>Come back</strong>
      to return to the taskbar.
    </p>
  </main>

  <script src="sprite.js"></script>
  <script src="options.js"></script>
</body>
</html>
''',

    "extension/options.css": r'''
:root {
  font: 18px/1.6 system-ui;
  color: #563378;
  background: #faf5ff;
}
main {
  max-width: 540px;
  margin: 50px auto;
  padding: 25px;
}
#cat {
  width: 150px;
  height: 120px;
}
svg {
  width: 100%;
  height: 100%;
  image-rendering: pixelated;
}
h1 {
  line-height: 1.2;
  font-size: 36px;
}
label {
  display: block;
  font-weight: 700;
}
input {
  display: block;
  width: 100%;
  box-sizing: border-box;
  padding: 14px;
  margin: 8px 0 18px;
  border: 2px solid #b99ad5;
  border-radius: 12px;
  font: inherit;
}
button {
  background: #7945ae;
  color: white;
  border: 0;
  border-radius: 12px;
  padding: 13px 18px;
  cursor: pointer;
  font: 600 16px system-ui;
}
#disconnect {
  background: #e9dbf5;
  color: #563378;
}
.note {
  font-size: 14px;
  color: #796387;
}
#status {
  font-weight: 700;
}
''',

    "extension/options.js": r'''
const $ = id => document.getElementById(id);

$('cat').innerHTML =
  window.SnowBallSprite('sleeping');

$('pair').onclick = async () => {
  const token = $('token').value.trim();

  if (!/^[A-Za-z0-9_-]{32,128}$/.test(token)) {
    $('status').textContent =
      'Copy the pairing code from your desktop cat first.';
    return;
  }

  await chrome.storage.local.set({
    companionToken: token
  });

  $('token').value = '';

  $('status').textContent =
    'Connecting to the desktop app…';
};

$('disconnect').onclick = async () => {
  await chrome.storage.local.remove(
    'companionToken'
  );

  $('status').textContent =
    'Unpaired. The browser cat can still work on its own.';
};

chrome.storage.session
  .get('companionStatus')
  .then(result => {
    if (result.companionStatus) {
      $('status').textContent =
        result.companionStatus;
    }
  });

chrome.storage.onChanged.addListener(
  (changes, area) => {
    if (
      area === 'session' &&
      changes.companionStatus
    ) {
      $('status').textContent =
        changes.companionStatus.newValue;
    }
  }
);
''',

    "extension/sprite.js": r'''
window.SnowBallSprite = (state = 'waking') => {
  const asleep = state === 'sleeping';

  const eyes = asleep
    ? '<g class="eyes"><path d="M24 15h3v1h-3zm7 0h3v1h-3z" fill="#38204f"/></g>'
    : '<g class="eyes eyes-open"><path d="M25 13h2v3h-2zm7 0h2v3h-2z" fill="#38204f"/><path d="M25 13h1v1h-1zm7 0h1v1h-1z" fill="white"/></g>';

  return `
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 40 32"
      shape-rendering="crispEdges"
      aria-hidden="true"
    >
      <g class="body">
        <path d="M12 17h15v2h5v7h-3v2H10v-2H8v-6h4z" fill="#593684"/>
        <path d="M13 18h13v2h4v5H11v-4h2z" fill="#a774dc"/>
        <path d="M13 23h15v3H13z" fill="#d8baf8"/>
      </g>
      <g class="tail">
        <path d="M15 22h-3v3H8v-2H5v-2H3v-3H1v-4H0v-4h2V7h2V4h4v2h4v3h-2v3H8v4h2v3h3v1h3z" fill="#593684"/>
        <path d="M11 21H8v2H6v-2H4v-3H2v-4H1v-4h2V8h2V6h3v2h2v2H8v3H6v3h2v2h3v1h3v2h-3z" fill="#bb8def"/>
        <path d="M3 10h2V8h2v2H5v2H3zm-1 4h2v3H2zm3 5h2v2H5z" fill="#d8baf8"/>
      </g>
      <g class="head">
        <path d="M21 6h4v3h8V6h4v13h-2v3H23v-3h-2z" fill="#593684"/>
        <path d="M22 8h2v3h10V8h2v10h-2v3H24v-3h-2z" fill="#bb8def"/>
        <path d="M23 9h1v3h-1zm11 0h1v3h-1z" fill="#f1b3e1"/>
        ${eyes}
        <path d="M28 17h3v1h-3zm0 2h1v1h-1zm3 0h1v1h-1z" fill="#593684"/>
        <path d="M23 17h2v1h-2zm10 0h2v1h-2z" fill="#f1b3e1"/>
      </g>
      <g class="paws">
        <path d="M13 26h5v4h-5zm11 0h5v4h-5z" fill="#593684"/>
        <path d="M14 26h3v3h-3zm11 0h3v3h-3z" fill="#d8baf8"/>
      </g>
      ${asleep ? '<text x="8" y="7" font-size="6" fill="#8662b0">z z</text>' : ''}
      ${state === 'confused' ? '<text x="7" y="10" font-size="9" fill="#593684">?</text>' : ''}
      ${state === 'celebrating' ? '<path d="M13 6h2V4h2v2h2v2h-2v2h-2V8h-2z" fill="#ef82c1"/>' : ''}
      ${state === 'sad' ? '<path d="M33 17h1v3h-1z" fill="#72bcec"/>' : ''}
    </svg>
  `;
};
''',

    "extension/pet.js": r'''
(() => {
  const host = document.createElement('div');
  host.id = 'pawly-root';

  const root = host.attachShadow({ mode: 'closed' });

  root.innerHTML = `<style>
    :host {
      all: initial;
      position: fixed;
      left: 0;
      top: 0;
      width: 128px;
      height: 96px;
      z-index: 2147483647;
      pointer-events: none;
      background: transparent !important;
      border: 0 !important;
      box-shadow: none !important;
      border-radius: 0 !important;
      outline: 0 !important;
      transition:
        left .85s cubic-bezier(.3,.1,.2,1),
        top .85s cubic-bezier(.3,.1,.2,1);
    }

    :host(.following) {
      transition:
        left .18s ease-out,
        top .18s ease-out;
    }

    * { box-sizing: border-box; }

    button, input, textarea, select {
      font: inherit;
    }

    button { cursor: pointer; }

    button:focus-visible,
    textarea:focus,
    select:focus {
      outline: 3px solid #c691ef;
      outline-offset: 3px;
    }

    #pose {
      background: transparent !important;
      border: 0 !important;
      box-shadow: none !important;
    }

    .cat {
      all: unset !important;
      display: block !important;
      position: absolute !important;
      inset: 0 !important;
      width: 128px !important;
      height: 96px !important;
      padding: 0 !important;
      margin: 0 !important;
      border: 0 !important;
      border-radius: 0 !important;
      background: transparent !important;
      box-shadow: none !important;
      outline: none !important;
      cursor: pointer !important;
      pointer-events: auto !important;
    }

    :host(.following) .cat {
      pointer-events: none !important;
    }

    .cat:focus-visible {
      outline: 2px dashed #a276c6 !important;
      outline-offset: 4px !important;
    }

    svg {
      width: 100%;
      height: 100%;
      image-rendering: pixelated;
    }

    .cat svg {
      display: block !important;
      width: 128px !important;
      height: 96px !important;
      background: transparent !important;
      pointer-events: none;
    }

    .tail {
      transform-box: fill-box;
      transform-origin: 90% 95%;
      animation: tail 2.8s ease-in-out infinite;
    }

    .body {
      transform-box: fill-box;
      transform-origin: bottom;
      animation: breathe 3s ease-in-out infinite;
    }

    .eyes-open {
      transform-box: fill-box;
      transform-origin: center;
      animation: blink 4s infinite;
    }

    .sleeping .head {
      transform: translateY(3px);
    }

    .sleeping .paws {
      transform-box: fill-box;
      transform-origin: top;
      animation: dangle 3s ease-in-out infinite;
    }

    .ledge {
      position: absolute;
      left: -90px;
      right: 0;
      top: 78px;
      height: 0;
      border-top: 2px solid #a68dbd;
      background: none;
      z-index: -1;
    }

    .ledge[hidden] {
      display: none;
    }

    .flying .cat {
      animation: fly .85s ease-in-out !important;
    }

    .celebrating .cat {
      animation: hop .45s 3 !important;
    }

    .confused .cat {
      animation: shake .25s 3 !important;
    }

    .flying:before {
      content: '✦';
      position: absolute;
      left: 8px;
      top: 40px;
      color: #c49be8;
      font: 24px system-ui;
      animation: spark .4s infinite;
    }

    .pointer {
      display: none;
      position: absolute;
      left: -26px;
      top: 40px;
      width: 48px;
      height: 28px;
    }

    .pointing:not(.flying) .pointer {
      display: block;
      transform-origin: right center;
      animation: reach .8s 3;
    }

    .left .pointer {
      left: auto;
      right: -26px;
      transform: scaleX(-1);
    }

    .scroll-down .pointer {
      rotate: -90deg;
      left: 30px;
      top: 74px;
    }

    .scroll-up .pointer {
      rotate: 90deg;
      left: 30px;
      top: 0;
    }

    .scroll-cue {
      position: absolute;
      top: 98px;
      left: -30px;
      width: 190px;
      text-align: center;
      color: #7945ae;
      font: 700 16px system-ui;
      animation: scroll-bounce 1s infinite;
    }

    .scroll-cue[hidden] {
      display: none;
    }

    .bubble {
      position: absolute;
      bottom: 100px;
      right: 0;
      width: 250px;
      max-width: calc(100vw - 24px);
      max-height: 170px;
      overflow: auto;
      padding: 12px 14px;
      border: 2px solid #a17bc5;
      border-radius: 16px;
      background: #fcf8ff;
      color: #38204f;
      font: 600 17px/1.5 system-ui;
      pointer-events: auto;
      box-shadow: 0 6px 22px #36204418;
    }

    .bubble[hidden],
    .menu[hidden],
    button[hidden] {
      display: none;
    }

    .below {
      top: 104px;
      bottom: auto;
    }

    .menu {
      position: fixed;
      width: 300px;
      max-width: calc(100vw - 24px);
      max-height: calc(100vh - 24px);
      overflow: auto;
      pointer-events: auto;
      background: #fcf8ff;
      color: #38204f;
      border: 2px solid #a17bc5;
      border-radius: 18px;
      padding: 16px;
      font: 15px/1.5 system-ui;
      box-shadow: 0 12px 40px #36204428;
    }

    .row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 10px 0;
    }

    .row > * { flex: 1; }

    .title {
      font-weight: 800;
      font-size: 18px;
    }

    .close {
      flex: 0 !important;
      padding: 4px 10px !important;
    }

    button {
      border: 1px solid #b996d6;
      border-radius: 9px;
      padding: 9px;
      background: #f0e3fc;
      color: #38204f;
      min-height: 40px;
    }

    .primary {
      background: #7945ae;
      color: white;
    }

    .small {
      font-size: 12px;
      color: #795c8e;
    }

    .menu textarea,
    .menu select {
      width: 100%;
      padding: 9px;
      border: 1px solid #b996d6;
      border-radius: 9px;
      background: white;
      color: #38204f;
    }

    .menu label {
      display: block;
      margin: 10px 0 5px;
    }

    .menu input[type=checkbox] {
      accent-color: #7945ae;
    }

    summary { cursor: pointer; }
    #status { color: #8b3154; }

    @keyframes tail {
      50% { transform: rotate(-13deg); }
    }

    @keyframes breathe {
      50% { transform: scaleY(.96); }
    }

    @keyframes blink {
      0%, 90%, 100% { transform: scaleY(1); }
      92%, 94% { transform: scaleY(.08); }
    }

    @keyframes fly {
      45% {
        transform: translateY(-22px) rotate(-9deg);
      }
      75% {
        transform: translateY(-8px) rotate(5deg);
      }
    }

    @keyframes hop {
      50% { transform: translateY(-14px); }
    }

    @keyframes shake {
      50% { transform: rotate(-7deg); }
    }

    @keyframes dangle {
      50% { transform: rotate(4deg); }
    }

    @keyframes spark {
      to {
        opacity: 0;
        transform: translate(-20px,10px) scale(.3);
      }
    }

    @keyframes reach {
      0%, 100% {
        scale: .35 1;
        translate: 10px 0;
      }
      50% {
        scale: 1 1;
        translate: -12px 0;
      }
    }

    @keyframes scroll-bounce {
      50% { translate: 0 5px; }
    }

    @media (prefers-reduced-motion: reduce) {
      :host, *,
      .flying .cat,
      .celebrating .cat,
      .confused .cat {
        animation: none !important;
        transition: none !important;
      }
    }
  </style>

  <div id="pose" class="sleeping">
    <div class="ledge"></div>

    <button
      class="cat"
      title="Click Snow Ball to chat"
      aria-label="Snow Ball — click to chat"
      aria-expanded="false"
    >
      ${window.SnowBallSprite('sleeping')}
    </button>

    <span class="pointer" aria-hidden="true">
      <svg
        viewBox="0 0 40 20"
        shape-rendering="crispEdges"
      >
        <path
          d="M38 7H14V4H7V2H3v4H0v8h3v3h11v-3h24z"
          fill="#593684"
        />
        <path
          d="M37 9H12V6H7V4H5v4H2v4h3v3h7v-3h25z"
          fill="#bb8def"
        />
        <path
          d="M5 9h2v2H5zm4-3h2v2H9zm0 6h2v2H9z"
          fill="#efb3df"
        />
      </svg>
    </span>

    <div class="bubble" role="status" hidden></div>
  </div>

  <section
    class="menu"
    role="dialog"
    aria-label="Snow Ball options"
    hidden
  >
    <div class="row">
      <span class="title">Snow Ball</span>
      <button class="close" aria-label="Close options">
        ×
      </button>
    </div>

    <div class="row">
      <button id="type">⌨ Type</button>
      <button id="talk">🎙 Talk</button>
    </div>

    <label for="goal">
      What would you like help with?
    </label>

    <textarea
      id="goal"
      rows="3"
      maxlength="300"
      placeholder="Help me book a train ticket"
    ></textarea>

    <p class="small">
      No passwords, OTPs or card details. During guidance, say
      “next”, “repeat”, or “stop”.
    </p>

    <div class="row">
      <button id="start" class="primary">
        Navigate me →
      </button>
      <button id="mic" hidden>🎙 Speak</button>
    </div>

    <div class="row">
      <button id="next">Next step</button>
      <button id="replay">Replay</button>
      <button id="stop">Rest</button>
    </div>

    <details>
      <summary>⚙ Settings</summary>

      <label for="language">Language</label>
      <select id="language">
        <option value="en">English</option>
      </select>

      <label>
        <input id="voice" type="checkbox" checked>
        Read instructions aloud
      </label>

      <label for="dock">Resting place</label>
      <select id="dock">
        <option value="bottom-right">Bottom right</option>
        <option value="bottom-left">Bottom left</option>
        <option value="top-right">Top right</option>
        <option value="top-left">Top left</option>
      </select>
    </details>

    <p id="status" role="status"></p>
  </section>`;

  const $ = selector => root.querySelector(selector);

  const pose = $('#pose');
  const cat = $('.cat');
  const menu = $('.menu');
  const bubble = $('.bubble');

  let companionMode = false;
  let current = 'sleeping';
  let dock = 'bottom-right';
  let inputMode = 'type';
  let flyTimer;
  let recognition;

  const api = {
    host,
    set,
    move,
    toggle,
    onAction: null,

    get companion() {
      return companionMode;
    },

    setCompanion(enabled) {
      companionMode = enabled;

      host.style.visibility =
        enabled && current === 'sleeping'
          ? 'hidden'
          : 'visible';

      if (enabled && current === 'sleeping') {
        toggle(false);
      }
    }
  };

  const emit = message => api.onAction?.(message);

  const clamp = (value, max) =>
    Math.max(12, Math.min(Math.max(12, max), value));

  function place(x, y) {
    host.style.left =
      `${clamp(x, innerWidth - 140)}px`;

    host.style.top =
      `${clamp(y, innerHeight - 108)}px`;

    bubble.classList.toggle(
      'below',
      parseFloat(host.style.top) < 190
    );

    const nearLeft =
      parseFloat(host.style.left) < 150;

    bubble.style.right = nearLeft ? 'auto' : '0';
    bubble.style.left = nearLeft ? '0' : 'auto';

    positionMenu();
  }

  function home() {
    place(
      dock.endsWith('left')
        ? 12
        : innerWidth - 148,
      dock.startsWith('top')
        ? 12
        : innerHeight - 108
    );
  }

  function positionMenu() {
    if (menu.hidden) return;

    const rect = host.getBoundingClientRect();
    const height = menu.offsetHeight;

    menu.style.left =
      `${clamp(rect.right - 300, innerWidth - 312)}px`;

    const above = rect.top - height - 12;

    menu.style.top = `${
      clamp(
        above >= 12 ? above : rect.bottom + 12,
        innerHeight - height - 12
      )
    }px`;
  }

  function toggle(force) {
    host.classList.remove('following');

    menu.hidden =
      force === undefined ? !menu.hidden : !force;

    cat.setAttribute(
      'aria-expanded',
      String(!menu.hidden)
    );

    host.style.visibility =
      menu.hidden &&
      companionMode &&
      current === 'sleeping'
        ? 'hidden'
        : 'visible';

    if (menu.hidden) {
      recognition?.stop();
      cat.focus({ preventScroll: true });

    } else {
      positionMenu();
      $('#goal').focus({ preventScroll: true });
    }
  }

  function set(state, text) {
    current = state;
    host.classList.remove('following');

    host.style.visibility =
      companionMode && state === 'sleeping'
        ? 'hidden'
        : 'visible';

    root.querySelector('.scroll-cue')
      ?.setAttribute('hidden', '');

    clearTimeout(flyTimer);

    pose.className = state;
    cat.innerHTML = window.SnowBallSprite(state);

    bubble.hidden =
      !text ||
      state === 'sleeping' ||
      state === 'waking';

    if (text) bubble.textContent = text;

    $('.ledge').hidden = state !== 'sleeping';

    if (state === 'sleeping') {
      home();
      toggle(false);
    }
  }

  function move(rect) {
    if (current !== 'pointing') return;

    let cue = root.querySelector('.scroll-cue');

    if (!cue) {
      cue = document.createElement('div');
      cue.className = 'scroll-cue';
      cue.setAttribute('role', 'status');
      pose.append(cue);
    }

    const direction =
      rect.top > innerHeight - 40
        ? 'down'
        : rect.bottom < 40
          ? 'up'
          : '';

    cue.hidden = !direction;

    cue.textContent = direction
      ? `Scroll ${direction} ${
          direction === 'down' ? '↓' : '↑'
        }`
      : '';

    pose.classList.toggle(
      'scroll-down',
      direction === 'down'
    );
    pose.classList.toggle(
      'scroll-up',
      direction === 'up'
    );

    const toLeft =
      !direction &&
      innerWidth - rect.right < 150 &&
      rect.left > 150;

    let x = toLeft
      ? rect.left - 155
      : rect.right + 24;

    let y =
      rect.top + rect.height / 2 - 48;

    if (direction) {
      x = innerWidth - 160;

      y = direction === 'down'
        ? innerHeight - 180
        : 70;

    } else if (
      innerWidth - rect.right < 150 &&
      rect.left < 150
    ) {
      x = rect.left;
      y = rect.bottom + 12;
    }

    const moved =
      Math.abs(
        parseFloat(host.style.left) -
        clamp(x, innerWidth - 140)
      ) > 4 ||
      Math.abs(
        parseFloat(host.style.top) -
        clamp(y, innerHeight - 108)
      ) > 4;

    pose.classList.toggle('left', toLeft);

    if (moved) {
      pose.classList.remove('flying');
      void pose.offsetWidth;
      pose.classList.add('flying');

      clearTimeout(flyTimer);

      flyTimer = setTimeout(
        () => pose.classList.remove('flying'),
        850
      );
    }

    place(x, y);
  }

  function mode(value) {
    inputMode = value;
    $('#mic').hidden = value !== 'talk';

    if (value === 'type') {
      recognition?.stop();
    }
  }

  async function preferences() {
    const value = {
      language: $('#language').value,
      voice: $('#voice').checked,
      dock,
      inputMode
    };

    await chrome.storage.local.set({
      preferences: value
    });

    emit({
      type: 'SETTINGS',
      preferences: value
    });
  }

  cat.addEventListener(
    'click',
    () => toggle()
  );

  $('.close').onclick = () => toggle(false);

  root.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      toggle(false);
      event.stopPropagation();
    }
  });

  $('#type').onclick = () => {
    mode('type');
    preferences();
    $('#goal').focus();
  };

  $('#talk').onclick = () => {
    mode('talk');
    preferences();
  };

  $('#start').onclick = () => {
    const goal = $('#goal').value.trim();

    if (!goal) {
      $('#status').textContent =
        'Type or speak your goal first.';
      return;
    }

    $('#status').textContent = '';

    emit({
      type: 'START',
      goal,
      language: $('#language').value
    });

    toggle(false);
  };

  $('#next').onclick = () =>
    emit({ type: 'CONTINUE' });

  $('#replay').onclick = () =>
    emit({ type: 'REPLAY' });

  $('#stop').onclick = () =>
    emit({ type: 'STOP' });

  $('#language').onchange = preferences;
  $('#voice').onchange = preferences;

  $('#dock').onchange = () => {
    dock = $('#dock').value;

    if (current === 'sleeping') {
      home();
    }

    preferences();
    positionMenu();
  };

  const Recognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;

  $('#mic').onclick = () => {
    if (!Recognition) {
      $('#status').textContent =
        'Mic unavailable here. Please type your goal.';
      return;
    }

    if (recognition) {
      recognition.stop();
      return;
    }

    recognition = new Recognition();
    recognition.lang = 'en-US';

    recognition.onresult = event => {
      const transcript =
        event.results[0][0].transcript.trim();

      const command = transcript
        .toLowerCase()
        .replace(/[.!?]/g, '')
        .replace(/\s+/g, ' ');

      const action = {
        next: ['next', 'next step', 'continue'],
        repeat: ['repeat', 'repeat that', 'again', 'replay'],
        stop: ['stop', 'stop guidance', 'cancel', 'rest']
      };

      const commandType = Object.entries(action)
        .find(([, phrases]) => phrases.includes(command))
        ?.[0];

      if (
        commandType &&
        !['sleeping', 'waking'].includes(current)
      ) {
        const messages = {
          next: 'CONTINUE',
          repeat: 'REPLAY',
          stop: 'STOP'
        };
        const statuses = {
          next: 'Moving to the next step…',
          repeat: 'Repeating the current step…',
          stop: 'Stopping guidance…'
        };

        $('#status').textContent = statuses[commandType];
        emit({ type: messages[commandType] });
        return;
      }

      $('#goal').value = transcript.slice(0, 300);

      $('#start').click();
    };

    recognition.onerror = () => {
      $('#status').textContent =
        'Microphone unavailable. You can still type.';
    };

    recognition.onend = () => {
      recognition = null;
      $('#mic').textContent = '🎙 Speak';
    };

    $('#mic').textContent = '⏹ Listening…';

    try {
      recognition.start();
    } catch {
      recognition = null;

      $('#status').textContent =
        'Please type your goal.';
    }
  };

  document.documentElement.append(host);
  window.PawlyPet = api;

  home();

  chrome.storage.local
    .get('preferences')
    .then(({ preferences: value }) => {
      if (!value) return;

      $('#language').value = 'en';
      $('#voice').checked = value.voice !== false;

      dock = [
        'bottom-right',
        'bottom-left',
        'top-right',
        'top-left'
      ].includes(value.dock)
        ? value.dock
        : 'bottom-right';

      $('#dock').value = dock;

      mode(
        value.inputMode === 'talk'
          ? 'talk'
          : 'type'
      );

      if (current === 'sleeping') {
        home();
      }
    });

  addEventListener('resize', () => {
    if (current === 'sleeping') {
      home();
    } else {
      place(
        parseFloat(host.style.left),
        parseFloat(host.style.top)
      );
    }
  });

  addEventListener(
    'pointermove',
    event => {
      if (
        event.pointerType !== 'mouse' ||
        current !== 'sleeping' ||
        !menu.hidden ||
        companionMode
      ) {
        return;
      }

      host.classList.add('following');

      const x = event.clientX > innerWidth - 170
        ? event.clientX - 152
        : event.clientX + 28;

      const y = event.clientY > innerHeight - 128
        ? event.clientY - 112
        : event.clientY + 24;

      place(x, y);
    },
    { passive: true }
  );
})();
''',

    "start_desktop.bat": r'''
@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m pip install -r desktop\requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m desktop.app
if errorlevel 1 goto failed
exit /b 0
:failed
echo Snow Ball could not start. Read the error above.
pause
exit /b 1
''',
}

# Update the existing page scanner without replacing your backend.

content = (EXT / "content.js").read_text(
    encoding="utf-8"
)

if "pet.onAction" not in content:
    content, count = re.subn(
        r"chrome\.runtime\.onMessage\.addListener\(\s*"
        r"\(message,\s*sender,\s*respond\)\s*=>\s*\{",
        "function handleMessage("
        "message, sender = {}, respond = () => {}) {\n"
        "if (message.type === 'TOGGLE_WIDGET') { "
        "pet.toggle(); respond({ok:true}); return; }",
        content,
        count=1,
    )

    if count != 1:
        raise SystemExit(
            "Unrecognized content.js. No files changed."
        )

    content, count = re.subn(
        r"\}\s*\);\s*(?=new MutationObserver)",
        "}\n"
        "pet.onAction = message => handleMessage(message);\n"
        "chrome.runtime.onMessage.addListener(handleMessage);\n",
        content,
        count=1,
    )

    if count != 1:
        raise SystemExit(
            "Unrecognized content.js ending. "
            "No files changed."
        )

if "COMPANION_PRESENCE" not in content:
    content = content.replace(
        "function handleMessage("
        "message, sender = {}, respond = () => {}) {",

        "function handleMessage("
        "message, sender = {}, respond = () => {}) {\n"
        "if (message.type === 'COMPANION_PRESENCE') { "
        "pet.setCompanion(message.online); "
        "respond({ok:true}); return; }",
    )

if "COMPANION_STATUS" not in content:
    index = content.rfind("})();")

    if index < 0:
        raise SystemExit(
            "Unrecognized content.js wrapper. "
            "No files changed."
        )

    content = (
        content[:index]
        + "chrome.runtime.sendMessage("
          "{type:'COMPANION_STATUS'}"
          ").then(r=>pet.setCompanion("
          "r?.online===true)).catch(()=>{});\n"
        + content[index:]
    )

if "COMPANION_REST" not in content:
    content = re.sub(
        r"pet\.set\(([\"'])sleeping\1,[\s\S]*?\);",
        lambda match: (
            match.group(0)
            + "\nchrome.runtime.sendMessage("
              "{type:'COMPANION_REST'}"
              ").catch(()=>{});"
        ),
        content,
    )

    content = re.sub(
        r"\}\s*(?=pet\.onAction)",
        "if (['CONTINUE','STOP','REPLAY','WAKE']"
        ".includes(message.type)) respond({ok:true});\n"
        "}\n",
        content,
        count=1,
    )

content = re.sub(
    r"language:\s*state\.language",
    "language: 'en'",
    content,
)

content = re.sub(
    r"language:\s*message\.language",
    "language: 'en'",
    content,
)

content = re.sub(
    r"const lang\s*=\s*[\s\S]*?;",
    "const lang = 'en-US';",
    content,
    count=1,
)

content = re.sub(
    r"const text = \(?\{\s*hi:"
    r"[\s\S]*?\}\)?\[state\.language\];",
    "const text = "
    "'Connection is slow. Please try again.';",
    content,
)

content = re.sub(
    r"target\.scrollIntoView\(\{[\s\S]*?\}\);",
    "",
    content,
)

content = content.replace(
    "अपना लक्ष्य बोलें।",
    "Tell me your goal.",
).replace(
    "Snow Ball सो रहा है 💤",
    "Snow Ball is resting.",
)

if "if (step.done) idleTimer" not in content:
    content = content.replace(
        "if (!replay) save();",
        "if (step.done) idleTimer = setTimeout("
        "() => pet.set('sleeping'), 2500);\n"
        "if (!replay) save();",
    )

FILES["extension/content.js"] = content

backup = ROOT / (
    ".snowball-backup-"
    + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
)

for name, text in FILES.items():
    target = ROOT / name

    if target.exists():
        saved = backup / name
        saved.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        shutil.copy2(target, saved)

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.write_text(
        text.lstrip("\n"),
        encoding="utf-8",
    )

print("Snow Ball desktop files installed.")
print("Existing files backed up in:", backup.name)
print("Next: reload the extension and start the desktop app.")

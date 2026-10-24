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
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from desktop.bridge import Bridge
from desktop.screen import target_rect, flight_point, Speaker
from desktop.interface import read_window, guide_interface, resolve_target
from desktop.voice_input import VoiceInput
from desktop import theme

KEY = "#ff00ff"
PURPLE = "#bf98e8"
OUTLINE = "#65447f"
PALE = "#ead5fa"


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
        self.user32.GetParent.argtypes = [wintypes.HWND]
        self.user32.GetParent.restype = wintypes.HWND
        self.user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]

        self.path, self.config = load_config()
        self.events = queue.Queue()

        self.root = tk.Tk()
        self.english_mode = tk.BooleanVar(value=self.config.get('language', 'ml') == 'en')
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

        self.close_button = tk.Button(
            self.root,
            text="×",
            command=self.quit,
            font=("Segoe UI", 12, "bold"),
            fg=OUTLINE,
            bg=KEY,
            activeforeground=PURPLE,
            activebackground=KEY,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        self.close_button.place(x=144, y=0, width=24, height=24)

        self.canvas.bind(
            "<Button-1>",
            self.start_drag,
        )
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.finish_drag)
        self.canvas.bind(
            "<Button-3>",
            self.context_menu,
        )

        self.chat = None
        self.guiding = False
        self.frame = 0
        self.flight_started = None
        self.drag_origin = None
        self.dragged = False
        self.custom_position = None
        self.screen_mode = False
        self.screen_pointing = False
        self.screen_epoch = 0
        self.screen_history = []
        self.screen_goal = ""
        self.screen_busy = False
        self.screen_overlay = None
        self.screen_card = None
        self.screen_flight = None
        self.screen_instruction = ""
        self.point_left = False
        self.speaker = Speaker()
        self.voice_input = None
        self.voice_epoch = 0
        self.voice_processing = False
        self.exit_started = None
        self.exit_origin = None

        self.bridge = Bridge(
            self.config["token"],
            self.events,
        )
        self.bridge.start()

        self.root.bind_all('<Escape>', lambda event: self.rest())
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

        if self.custom_position is not None:
            x, y = self.custom_position
            self.home_x = max(0, min(x, max(0, width - 168)))
            self.home_y = max(0, min(y, max(0, height - 116)))

        self.root.geometry(
            f"168x116+{self.home_x}+{self.home_y}"
        )

    def start_drag(self, event):
        self.drag_origin = (
            event.x_root, event.y_root,
            self.root.winfo_x(), self.root.winfo_y(),
        )
        self.dragged = False

    def drag(self, event):
        if self.drag_origin is None or self.guiding:
            return

        pointer_x, pointer_y, window_x, window_y = self.drag_origin
        dx = event.x_root - pointer_x
        dy = event.y_root - pointer_y
        if not self.dragged and max(abs(dx), abs(dy)) < 5:
            return

        self.dragged = True
        self.custom_position = (window_x + dx, window_y + dy)
        self.position()

    def finish_drag(self, event):
        if self.drag_origin is None:
            return
        self.drag(event)
        self.drag_origin = None
        if not self.dragged:
            self.open_chat()

    def draw(self, awake=False):
        canvas = self.canvas
        canvas.delete("all")

        wave = round(math.sin(self.frame / 12) * 8)
        tail_sway = round(wave * 0.6)
        breath = round(math.sin(self.frame / 18))
        standing = min(1, (time.monotonic() - self.exit_started) / .35) if self.exit_started is not None else 0

        def standing_y(y):
            return y - 14 * standing + max(0, y - 82) * 14 * standing / 18

        def pixel(x, y, width, height, color):
            canvas.create_rectangle(
                x, standing_y(y),
                x + width, standing_y(y + height),
                fill=color,
                outline="",
            )

        # A broad, curled tail behind the body, with room for its sway.
        tail = [
            43, 80, 26, 79, 14, 72, 7, 61,
            6, 45, 9, 30, 16, 17, 25, 7,
            35, 5, 44, 9, 49, 17, 48, 25,
            41, 36, 33, 48, 30, 60, 33, 68, 43, 70,
        ]
        swaying_tail = [
            value + tail_sway if index % 2 == 0 else value
            for index, value in enumerate(tail)
        ]
        canvas.create_polygon(
            *swaying_tail,
            fill=PURPLE,
            outline=OUTLINE,
            width=4,
            joinstyle="round",
            smooth=True,
            splinesteps=16,
        )
        if standing:
            canvas.move('all', 0, -8 * standing)

        pixel(38, 60 + breath, 92, 24, OUTLINE)
        pixel(46, 53 + breath, 68, 32, OUTLINE)
        pixel(44, 61 + breath, 82, 18, PURPLE)
        pixel(50, 57 + breath, 60, 23, PURPLE)
        pixel(54, 75, 66, 8, PALE)
        pixel(54, 58 + breath, 26, 4, PALE)

        for x in (60, 113):
            pixel(x, 82, 16, 18, OUTLINE)
            pixel(x + 3, 83, 10, 14, PALE)
            pixel(x + 5, 94, 2, 3, PURPLE)
            pixel(x + 8, 94, 2, 3, PURPLE)

        head_y = 30 if awake else 35

        pixel(100, head_y, 52, 42, OUTLINE)
        pixel(100, head_y - 8, 12, 16, OUTLINE)
        pixel(140, head_y - 8, 12, 16, OUTLINE)
        pixel(104, head_y + 3, 44, 32, PURPLE)
        pixel(104, head_y - 4, 5, 12, "#e9a8d4")
        pixel(143, head_y - 4, 5, 12, "#e9a8d4")
        pixel(117, head_y + 4, 18, 4, PALE)

        blink = awake and self.frame % 100 in range(90, 95)

        if awake and not blink:
            for x in (110, 134):
                pixel(x, head_y + 11, 8, 11, OUTLINE)
                pixel(x + 1, head_y + 11, 3, 4, "#fff7ff")
                pixel(x + 5, head_y + 18, 2, 2, PALE)
        else:
            for x in (109, 133):
                pixel(x, head_y + 16, 3, 3, OUTLINE)
                pixel(x + 3, head_y + 19, 6, 2, OUTLINE)
                pixel(x + 9, head_y + 16, 3, 3, OUTLINE)

        # A tiny purple nose, with no mouth underneath.
        pixel(123, head_y + 24, 6, 2, "#8b4db8")
        pixel(125, head_y + 26, 2, 2, "#8b4db8")

        # Rosy cheeks keep the face expressive without a mouth.
        for x in (106, 137):
            pixel(x, head_y + 25, 9, 4, "#efaed5")
            pixel(x + 2, head_y + 24, 5, 6, "#efaed5")

        if self.screen_pointing and self.screen_flight is None:
            # Short bent front leg, attached at the shoulder rather than the tail.
            canvas.create_line(126, 76, 143, 66, 154, 55,
                               fill=OUTLINE, width=12, joinstyle="round", capstyle="round")
            canvas.create_line(126, 76, 143, 66, 154, 55,
                               fill=PURPLE, width=7, joinstyle="round", capstyle="round")
            canvas.create_oval(148, 47, 162, 61, fill=PALE, outline=OUTLINE, width=2)
            # Face the whole cat toward the control; never draw an arm across its tail.
            if self.point_left:
                canvas.scale("all", 84, 58, -1, 1)

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

        if self.exit_started is not None:
            self.draw(awake=True)
            elapsed = time.monotonic() - self.exit_started
            if elapsed >= 1.25:
                self.finish_quit()
                return
            if elapsed > .4:
                t = (elapsed - .4) / .85
                x0, y0 = self.exit_origin
                # A small sideways hop, upward first and then beyond the bottom edge.
                end_y = self.user32.GetSystemMetrics(1) + 140
                x = round(x0 + self.exit_direction * 150 * t)
                y = round(y0 - 140 * math.sin(math.pi * t) + (end_y - y0) * t * t)
                # SetWindowPos uses actual signed coordinates; Tk's negative geometry
                # offsets would anchor to the opposite edge instead of moving offscreen.
                self.user32.SetWindowPos(self.exit_handle, None, x, y, 0, 0, 0x0015)
            self.root.after(16, self.animate)
            return

        self.draw(
            awake=self.guiding or self.chat is not None
        )

        if self.screen_flight is not None:
            start, end, began = self.screen_flight
            progress = (time.monotonic() - began) / 1.15
            x, y = flight_point(start, end, progress)
            self.root.geometry(f"168x116+{max(0, x)}+{max(0, y)}")
            if progress >= 1:
                self.screen_flight = None
        elif self.flight_started is not None:
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

        elif (
            not self.guiding
            and self.drag_origin is None
            and self.frame % 30 == 0
        ):
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
            self.chat.deiconify()
            self.chat.lift()
            return

        win = self.chat = tk.Toplevel(self.root)
        win.title("Snow Ball")
        win.configure(bg=theme.BG)
        win.attributes("-topmost", True)
        win.geometry("500x680")
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self.close_chat)
        self.voice = tk.BooleanVar(value=self.config.get("voice", True))
        self.side = tk.StringVar(value=self.config.get("side", "right"))

        header = tk.Frame(win, bg=theme.BG)
        header.pack(fill='x', padx=28, pady=(24, 18))
        tk.Label(header, text='SNOW BALL  /  YOUR DESKTOP GUIDE',
                 font=(theme.FONT, 9, 'bold'), bg=theme.BG, fg=theme.ACCENT,
                 anchor='w').pack(fill='x', pady=(0, 12))
        self.chat_heading, self.chat_subtitle = theme.heading(header,
            self.tr('How can I help?', 'ഞാൻ സഹായിക്കാം.'),
            self.tr('Tell me what you want to do. I’ll guide you.', 'മലയാളത്തിലോ English-ലോ പറയൂ. ഞാൻ വഴികാട്ടാം.'))
        field = tk.Frame(win, bg=theme.SURFACE, highlightthickness=1,
                         highlightbackground=theme.BORDER)
        field.pack(fill='x', padx=28)
        tk.Label(field, text='YOUR QUESTION', font=(theme.FONT, 9, 'bold'),
                 bg=theme.SURFACE, fg=theme.MUTED, anchor='w').pack(fill='x', padx=16, pady=(12, 4))
        self.goal = tk.Text(field, height=3, width=30, font=(theme.FONT, 13),
                            wrap='word', relief='flat', bd=0, padx=16, pady=8,
                            bg=theme.SURFACE, fg=theme.INK, insertbackground=theme.ACCENT,
                            selectbackground=theme.SOFT, selectforeground=theme.INK,
                            highlightthickness=0, spacing3=5)
        self.goal.pack(fill='x', pady=(0, 8))
        self.goal.bind('<FocusIn>', lambda event: field.configure(highlightbackground=theme.ACCENT))
        self.goal.bind('<FocusOut>', lambda event: field.configure(highlightbackground=theme.BORDER))
        actions = tk.Frame(win, bg=theme.BG)
        actions.pack(fill='x', padx=28, pady=(16, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.speak_button = theme.button(actions, 'Speak', self.dictate)
        self.speak_button.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        theme.button(actions, 'Help me  →', self.help_me, primary=True).grid(
            row=0, column=1, sticky='ew', padx=(6, 0))
        tk.Label(win, text='Speak → Stop → review → Help me', font=(theme.FONT, 9),
                 bg=theme.BG, fg=theme.MUTED).pack(pady=(8, 12))
        self.status = tk.Label(win, text=self.connection_text(),
                               font=(theme.FONT, 11), wraplength=390, justify='left',
                               anchor='w', bg=theme.BG, fg=theme.MUTED)
        self.status.pack(fill='x', padx=30)
        footer = tk.Frame(win, bg=theme.BG)
        footer.pack(side='bottom', fill='x', padx=22, pady=14)
        theme.button(footer, 'Settings', self.open_settings, quiet=True).pack(side='right')
        self.language_label = tk.Label(footer, text=self.tr('English', 'മലയാളം + English'), font=(theme.FONT, 10),
                 bg=theme.BG, fg=theme.MUTED)
        self.language_label.pack(side='left', padx=6)
        win.bind('<Control-Return>', lambda event: self.help_me())
        win.update_idletasks()
        win.geometry(f"500x{max(620, win.winfo_reqheight() + 16)}")
        self.goal.focus_set()

    def help_me(self):
        self.cancel_voice()
        self.start_screen()

    def open_settings(self):
        existing = getattr(self, "settings_window", None)
        if existing and existing.winfo_exists():
            existing.lift()
            return
        win = self.settings_window = tk.Toplevel(self.root)
        win.title("Snow Ball settings")
        win.configure(bg=theme.BG)
        win.attributes("-topmost", True)
        win.geometry("470x480")
        win.resizable(False, False)
        header = tk.Frame(win, bg=theme.BG)
        header.pack(fill='x', padx=28, pady=(24, 20))
        theme.heading(header, 'Settings', 'Make Snow Ball feel right for you.')
        panel = tk.Frame(win, bg=theme.SURFACE, padx=18, pady=16,
                         highlightthickness=1, highlightbackground=theme.BORDER)
        panel.pack(fill='x', padx=28)
        tk.Checkbutton(win, text="Read instructions aloud", variable=self.voice,
                       command=self.settings, font=(theme.FONT, 12), fg=theme.INK,
                       bg=theme.BG, activebackground=theme.BG, selectcolor=theme.SURFACE,
                       cursor='hand2').pack(anchor='w', padx=28, pady=(14, 8))
        tk.Label(panel, text='LANGUAGE & VOICE', font=(theme.FONT, 9, 'bold'),
                 bg=theme.SURFACE, fg=theme.ACCENT, anchor='w').pack(fill='x')
        self.language_toggle = theme.SlidingToggle(panel, 'Use English',
                                                  self.english_mode, self.settings)
        self.language_toggle.pack(fill='x', pady=(8, 4))
        self.language_hint = tk.Label(panel,
                 text=self.tr('English voice input, guidance and spoken replies.',
                              'മലയാളത്തിൽ സംസാരിക്കാം. English പേരുകൾ അതേപടി.'),
                 font=(theme.FONT, 11), bg=theme.SURFACE, fg=theme.MUTED,
                 anchor='w', justify='left', wraplength=360)
        self.language_hint.pack(fill='x')
        tk.Label(win, text='Voice needs internet. Recordings go to Google for transcription; speech text goes to Microsoft. Page text goes to your AI provider. No screenshots.',
                 wraplength=400, justify='left', bg=theme.BG, fg=theme.MUTED,
                 font=(theme.FONT, 10)).pack(fill='x', padx=30, pady=12)
        theme.button(win, 'Done', win.destroy, primary=True).pack(side='bottom', fill='x', padx=28, pady=20)
        win.update_idletasks()
        win.geometry(f"470x{max(480, win.winfo_reqheight() + 16)}")

    def connection_text(self):
        return self.tr('Open the website or app you need, then tell me what you want to do.',
                       'ആവശ്യമുള്ള വെബ്സൈറ്റോ ആപ്പോ തുറക്കൂ. എന്താണ് ചെയ്യേണ്ടതെന്ന് പറയൂ.')

    def tr(self, english, malayalam):
        return english if self.config.get('language', 'ml') == 'en' else malayalam

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
        language = 'en' if self.english_mode.get() else 'ml'
        language_changed = language != self.config.get('language', 'ml')
        if self.config.get("side", "right") != self.side.get():
            self.custom_position = None
        self.config.update(
            side=self.side.get(),
            voice=self.voice.get(),
            language=language,
        )
        self.save()

        if language_changed:
            self.cancel_voice()
            self.speaker.stop()
            if self.screen_mode:
                self.rest()
            self.screen_history = []
            self.screen_instruction = ''
            if self.chat and self.chat.winfo_exists():
                self.chat_heading.configure(text=self.tr('How can I help?', 'ഞാൻ സഹായിക്കാം.'))
                self.chat_subtitle.configure(text=self.tr('Tell me what you want to do. I’ll guide you.', 'മലയാളത്തിലോ English-ലോ പറയൂ. ഞാൻ വഴികാട്ടാം.'))
                self.language_label.configure(text=self.tr('English', 'മലയാളം + English'))
                self.status.configure(text=self.connection_text())
            hint = getattr(self, 'language_hint', None)
            if hint and hint.winfo_exists():
                hint.configure(text=self.tr('English voice input, guidance and spoken replies.', 'മലയാളത്തിൽ സംസാരിക്കാം. English പേരുകൾ അതേപടി.'))

        if not self.guiding:
            self.position()

    def navigate(self):
        if self.screen_mode:
            self.rest()
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
        if self.exit_started is not None:
            return
        self.cancel_voice()
        self.screen_epoch += 1
        self.screen_mode = False
        self.screen_pointing = False
        self.screen_busy = False
        self.screen_flight = None
        self.speaker.stop()
        self.clear_screen_widgets()
        self.bridge.command("STOP")
        self.custom_position = None
        self.show_pet()

    def close_chat(self):
        self.cancel_voice()
        if self.chat:
            self.chat.destroy()
            self.chat = None

        if not self.guiding:
            self.show_pet()

    def poll(self):
        if self.exit_started is not None:
            return
        try:
            while True:
                event = self.events.get_nowait()
                text = self.connection_text()

                if event['type'].startswith('VOICE_'):
                    if event['epoch'] != self.voice_epoch or not self.chat or not self.chat.winfo_exists():
                        continue
                    if event['type'] == 'VOICE_LISTENING':
                        self.status.configure(text=self.tr('Speak in English. Press Stop when finished. Audio is sent to Google.', 'മലയാളത്തിൽ സംസാരിക്കൂ. തീർന്നാൽ വീണ്ടും Speak അമർത്തൂ. ശബ്ദം Google-ലേക്ക് അയക്കും.'))
                    elif event['type'] == 'VOICE_TRANSCRIBING':
                        self.voice_processing = True
                        self.speak_button.configure(text=self.tr('Transcribing…', 'എഴുത്താക്കുന്നു…'), state='disabled')
                        self.status.configure(text=self.tr('Turning your speech into text…', 'ശബ്ദം എഴുത്താക്കുകയാണ്…'))
                    else:
                        self.voice_input = None
                        self.voice_processing = False
                        self.speak_button.configure(text='Speak', state='normal')
                        if event['type'] == 'VOICE_RESULT':
                            self.goal.delete('1.0', 'end')
                            self.goal.insert('1.0', event['text'])
                            self.status.configure(text=self.tr('Review the text, then press Help me.', 'എഴുതിയത് പരിശോധിച്ച ശേഷം Help me അമർത്തൂ.'))
                        else:
                            self.status.configure(text=event['message'])
                    continue

                if event["type"] == "SCREEN_CAPTURED":
                    if event["epoch"] == self.screen_epoch and self.screen_mode:
                        self.position()
                        self.root.deiconify()
                        self.screen_instruction = self.tr('Reading the window. Please wait.', 'പേജിലെ വിവരങ്ങൾ വായിക്കുകയാണ്. അൽപ്പം കാത്തിരിക്കൂ.')
                        self.show_screen_card(self.screen_instruction)
                    continue
                if event["type"] in {"SCREEN_RESULT", "SCREEN_ERROR"}:
                    if event["epoch"] != self.screen_epoch or not self.screen_mode:
                        continue
                    self.screen_busy = False
                    if event["type"] == "SCREEN_ERROR":
                        self.screen_instruction = event["message"]
                        self.show_screen_card(self.screen_instruction)
                        self.root.deiconify()
                    else:
                        self.present_screen(event["capture"], event["step"])
                    continue

                if self.screen_mode and event["type"] in {"STATE", "DISCONNECTED"}:
                    continue
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

    def dictate(self):
        if self.voice_processing:
            return
        if self.voice_input:
            self.voice_processing = True
            self.voice_input.stop()
            self.speak_button.configure(text=self.tr('Transcribing…', 'എഴുത്താക്കുന്നു…'), state='disabled')
            return
        self.speaker.stop()
        self.voice_epoch += 1
        self.voice_input = VoiceInput(self.events, self.voice_epoch, language=self.config.get('language', 'ml'))
        self.speak_button.configure(text=self.tr('Stop recording', 'നിർത്തുക / Stop'))
        self.status.configure(text=self.tr('Opening microphone… Record up to 30 seconds.', 'മൈക്രോഫോൺ തുറക്കുന്നു… പരമാവധി 30 സെക്കൻഡ്.'))
        self.voice_input.start()

    def cancel_voice(self):
        self.voice_epoch += 1
        if self.voice_input:
            self.voice_input.cancel()
            self.voice_input = None
        self.voice_processing = False
        button = getattr(self, 'speak_button', None)
        if button and button.winfo_exists():
            button.configure(text='Speak', state='normal')

    def continue_step(self):
        if self.screen_mode:
            self.request_screen()
        else:
            self.bridge.command("CONTINUE")

    def repeat(self):
        if self.screen_mode:
            if self.voice.get() and self.screen_instruction:
                self.speaker.say(self.screen_instruction, language=self.config.get('language', 'ml'))
        else:
            self.bridge.command("REPLAY")

    def clear_screen_widgets(self):
        for name in ("screen_overlay", "screen_card"):
            widget = getattr(self, name, None)
            if widget and widget.winfo_exists():
                widget.destroy()
            setattr(self, name, None)

    def start_screen(self):
        goal = self.goal.get("1.0", "end").strip()
        if not goal or len(goal) > 300:
            self.status.configure(text="Describe what you want to find, in 1–300 characters.")
            return
        self.bridge.command("STOP")
        self.screen_epoch += 1
        self.screen_mode = True
        self.screen_busy = False
        self.guiding = True
        self.flight_started = None
        self.screen_goal = goal
        self.screen_history = []
        self.request_screen()

    def request_screen(self):
        if self.screen_busy:
            return
        self.screen_busy = True
        self.screen_pointing = False
        self.screen_epoch += 1
        epoch = self.screen_epoch
        self.speaker.stop()
        self.clear_screen_widgets()
        self.screen_flight = None
        self.root.withdraw()
        if self.chat:
            self.chat.withdraw()
        settings = getattr(self, 'settings_window', None)
        if settings and settings.winfo_exists():
            settings.withdraw()
        # Countdown gives the person time to bring the intended window to the front.
        card = self.screen_card = tk.Toplevel(self.root)
        card.overrideredirect(True)
        card.attributes("-topmost", True)
        card.geometry("440x150+30+30")
        card.configure(bg=theme.SURFACE, highlightthickness=1, highlightbackground=theme.BORDER)
        label = tk.Label(card, text=self.tr('Open the window you need. Reading in 3…', 'ആവശ്യമുള്ള വിൻഡോ തുറക്കൂ. 3 സെക്കൻഡിൽ വായിക്കും…'),
                         font=(theme.FONT, 12), fg=theme.INK, bg=theme.SURFACE, wraplength=390)
        label.pack(padx=20, pady=(18, 8))
        theme.button(card, 'Cancel', self.rest).pack(pady=(0, 12))

        def countdown(left):
            if epoch != self.screen_epoch or not self.screen_mode:
                return
            if left:
                label.configure(text=self.tr(f'Open the window you need. Reading in {left}…', f'ആവശ്യമുള്ള വിൻഡോ തുറക്കൂ. {left} സെക്കൻഡിൽ വായിക്കും…'))
                self.root.after(1000, lambda: countdown(left - 1))
                return
            self.clear_screen_widgets()
            self.root.after(150, capture)

        def capture():
            if epoch != self.screen_epoch or not self.screen_mode:
                return
            goal, history = self.screen_goal, list(self.screen_history)
            language = self.config.get('language', 'ml')
            def work():
                try:
                    snapshot, shot = read_window(self.user32)
                    self.events.put({'type':'SCREEN_CAPTURED', 'epoch':epoch})
                    step = guide_interface(snapshot, goal, history, language=language)
                    if step.get('element_id'):
                        # Re-read after the model reply: controls may have moved or vanished.
                        fresh, shot = read_window(self.user32, shot.window)
                        if fresh['title'] != snapshot['title']:
                            raise RuntimeError('The page changed. Choose Next to read it again.')
                        step = resolve_target(step, fresh, shot)
                    self.events.put({"type": "SCREEN_RESULT", "epoch": epoch,
                                     "capture": shot, "step": step})
                except Exception as exc:
                    self.events.put({"type": "SCREEN_ERROR", "epoch": epoch,
                                     "message": str(exc)[:300]})
            threading.Thread(target=work, daemon=True).start()
        countdown(3)

    def show_screen_card(self, text):
        if self.screen_card and self.screen_card.winfo_exists():
            self.screen_card.destroy()
        card = self.screen_card = tk.Toplevel(self.root)
        card.overrideredirect(True)
        card.attributes("-topmost", True)
        card.configure(bg=theme.SURFACE, highlightthickness=1, highlightbackground=theme.BORDER)
        tk.Frame(card, bg=theme.ACCENT, height=4).pack(fill='x')
        tk.Label(card, text='SNOW BALL  /  NEXT STEP', font=(theme.FONT, 9, 'bold'),
                 fg=theme.ACCENT, bg=theme.SURFACE, anchor='w').pack(fill='x', padx=20, pady=(16, 4))
        tk.Label(card, text=text, font=(theme.FONT, 13), wraplength=398,
                 justify='left', anchor='w', fg=theme.INK,
                 bg=theme.SURFACE).pack(fill='x', padx=20, pady=(4, 18))
        row = tk.Frame(card, bg=theme.SURFACE)
        row.pack(fill='x', padx=16, pady=(0, 16))
        for index, (label, action) in enumerate([
                (self.tr('Next', 'അടുത്തത്'), self.continue_step),
                (self.tr('Repeat', 'വീണ്ടും'), self.repeat),
                (self.tr('Stop', 'നിർത്തുക'), self.rest)]):
            row.columnconfigure(index, weight=1, uniform='actions')
            theme.button(row, label, action, primary=index == 0, quiet=index == 2).grid(
                row=0, column=index, sticky='ew', padx=3)
        card.update_idletasks()
        # Keep instructions near the cat and away from the target.
        width = 440
        x = max(12, min(self.root.winfo_x() - 100, self.user32.GetSystemMetrics(0) - width - 12))
        y = self.root.winfo_y() + 120
        height = max(190, card.winfo_reqheight())
        if y + height > self.user32.GetSystemMetrics(1):
            y = max(12, self.root.winfo_y() - height - 10)
        card.geometry(f"{width}x{height}+{x}+{y}")

    def present_screen(self, capture, step):
        self.screen_instruction = step["instruction_local"]
        if step.get("warning"):
            self.screen_instruction += " " + step["warning"]
        self.screen_history.append({"step": len(self.screen_history) + 1,
                                    "instruction": step["instruction"][:160], "element_id": None})
        self.screen_history = self.screen_history[-4:]
        self.position()
        self.root.deiconify()
        self.screen_pointing = bool(step.get("target"))
        if step.get("target"):
            x, y, width, height = target_rect(step["target"], capture.bounds)
            halo = self.screen_overlay = tk.Toplevel(self.root)
            halo.overrideredirect(True)
            halo.configure(bg=KEY)
            halo.attributes("-transparentcolor", KEY)
            halo.attributes("-topmost", True)
            halo.geometry(f"{width + 16}x{height + 16}+{max(0, x - 8)}+{max(0, y - 8)}")
            canvas = tk.Canvas(halo, bg=KEY, highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            canvas.create_rectangle(4, 4, width + 12, height + 12, outline="#a46be0", width=5)
            halo.update_idletasks()
            # Click-through decoration; never consumes a click on the real control.
            handle = self.user32.GetParent(halo.winfo_id())
            self.user32.SetWindowLongW(handle, -20, self.user32.GetWindowLongW(handle, -20) | 0x20 | 0x80)
            screen_width, screen_height = capture.bounds[2:]
            self.point_left = x > screen_width / 2
            end_x = x + width + 15 if self.point_left else x - 183
            end_y = y + height // 2 - 55
            end = (max(0, min(end_x, screen_width - 168)),
                   max(0, min(end_y, screen_height - 116)))
            self.screen_flight = ((self.root.winfo_x(), self.root.winfo_y()), end, time.monotonic())
            # Place the instruction card after the cat arrives.
            epoch = self.screen_epoch
            self.root.after(1200, lambda: self.show_screen_card(self.screen_instruction)
                            if epoch == self.screen_epoch and self.screen_mode else None)
        else:
            self.show_screen_card(self.screen_instruction)
        if self.voice.get():
            self.speaker.say(self.screen_instruction, language=self.config.get('language', 'ml'))

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
        if self.exit_started is not None:
            return
        self.cancel_voice()
        self.screen_epoch += 1
        self.screen_mode = False
        self.screen_pointing = False
        self.screen_flight = None
        self.flight_started = None
        self.speaker.stop()
        self.clear_screen_widgets()
        for window in (self.chat, getattr(self, 'settings_window', None)):
            if window and window.winfo_exists():
                window.withdraw()
        self.close_button.place_forget()
        self.canvas.unbind('<Button-1>')
        self.canvas.unbind('<B1-Motion>')
        self.canvas.unbind('<ButtonRelease-1>')
        self.canvas.unbind('<Button-3>')
        if not self.root.winfo_viewable():
            self.position()
        self.root.deiconify()
        self.root.lift()
        self.root.update_idletasks()
        self.exit_origin = (self.root.winfo_x(), self.root.winfo_y())
        self.exit_direction = -1 if self.exit_origin[0] > self.user32.GetSystemMetrics(0) / 2 else 1
        self.exit_handle = self.user32.GetParent(self.root.winfo_id())
        self.user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        self.user32.SetWindowPos.restype = wintypes.BOOL
        self.exit_started = time.monotonic()

    def finish_quit(self):
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
        pet = SnowBall()
        if "--open-chat" in sys.argv:
            pet.open_chat()
        pet.run()
    except Exception as exc:
        messagebox.showerror(
            "Snow Ball",
            str(exc),
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Shared, keyboard-accessible styling for Snow Ball's native windows."""
import tkinter as tk
import time

BG = '#F5F3FA'
SURFACE = '#FFFFFF'
INK = '#30243F'
MUTED = '#756985'
ACCENT = '#7545AC'
SOFT = '#EDE5F7'
BORDER = '#DDD4E8'
FONT = 'Nirmala UI'


class SlidingToggle(tk.Frame):
    """Animated switch with keyboard controls and an explicit On/Off label."""
    def __init__(self, parent, text, variable, command):
        super().__init__(parent, bg=SURFACE)
        self.variable, self.command = variable, command
        self.position = float(variable.get())
        self.timer = None
        title = tk.Label(self, text=text, bg=SURFACE, fg=INK,
                         font=(FONT, 14, 'bold'), cursor='hand2')
        title.pack(side='left')
        self.track = tk.Canvas(self, width=58, height=32, bg=SURFACE,
                               highlightthickness=2, highlightbackground=SURFACE,
                               highlightcolor=ACCENT, takefocus=True, cursor='hand2')
        self.track.pack(side='right')
        self.state_label = tk.Label(self, bg=SURFACE, fg=MUTED, font=(FONT, 10))
        self.state_label.pack(side='right', padx=10)
        for widget in (title, self.track, self.state_label):
            widget.bind('<Button-1>', self.toggle)
        self.track.bind('<space>', self.toggle)
        self.track.bind('<Return>', self.toggle)
        self.track.bind('<Left>', lambda event: self.choose(False))
        self.track.bind('<Right>', lambda event: self.choose(True))
        self.trace = variable.trace_add('write', self.slide)
        self.bind('<Destroy>', self.cleanup)
        self.draw()

    def choose(self, enabled):
        self.track.focus_set()
        if bool(self.variable.get()) != enabled:
            self.variable.set(enabled)
            self.command()
        return 'break'

    def toggle(self, event=None):
        return self.choose(not self.variable.get())

    def draw(self):
        self.track.delete('all')
        color = ACCENT if self.variable.get() else BORDER
        self.track.create_oval(2, 3, 28, 29, fill=color, outline='')
        self.track.create_oval(30, 3, 56, 29, fill=color, outline='')
        self.track.create_rectangle(15, 3, 43, 29, fill=color, outline='')
        x = 5 + 28 * self.position
        self.track.create_oval(x, 6, x + 20, 26, fill=SURFACE, outline='')
        self.state_label.configure(text='On' if self.variable.get() else 'Off')

    def slide(self, *args):
        if self.timer:
            self.after_cancel(self.timer)
        start, target, began = self.position, float(self.variable.get()), time.monotonic()

        def tick():
            t = min(1, (time.monotonic() - began) / .16)
            self.position = start + (target - start) * (t * t * (3 - 2 * t))
            self.draw()
            self.timer = self.after(16, tick) if t < 1 else None
        tick()

    def cleanup(self, event):
        if event.widget is self:
            if self.timer:
                self.after_cancel(self.timer)
            self.variable.trace_remove('write', self.trace)


def button(parent, text, command, primary=False, quiet=False, **kwargs):
    background = ACCENT if primary else BG if quiet else SOFT
    foreground = '#FFFFFF' if primary else INK
    hover = '#633696' if primary else '#E3D8F0'
    widget = tk.Button(
        parent, text=text, command=command, font=(FONT, 11, 'bold'),
        bg=background, fg=foreground, activebackground=hover,
        activeforeground=foreground, disabledforeground='#9C91A7',
        relief='flat', bd=0, cursor='hand2', padx=18, pady=10,
        highlightthickness=2, highlightbackground=background,
        highlightcolor=ACCENT, takefocus=True, **kwargs)
    widget.bind('<Enter>', lambda event: widget.configure(bg=hover)
                if str(widget.cget('state')) != 'disabled' else None)
    widget.bind('<Leave>', lambda event: widget.configure(bg=background))
    return widget


def heading(parent, title, subtitle=None):
    title_label = tk.Label(parent, text=title, font=(FONT, 20, 'bold'),
             bg=BG, fg=INK, anchor='w', justify='left', wraplength=410)
    title_label.pack(fill='x')
    subtitle_label = None
    if subtitle:
        subtitle_label = tk.Label(parent, text=subtitle, font=(FONT, 11), bg=BG,
                 fg=MUTED, anchor='w', justify='left', wraplength=390)
        subtitle_label.pack(fill='x', pady=(5, 0))
    return title_label, subtitle_label

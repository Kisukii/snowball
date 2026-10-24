"""Native Windows smoke test using synthetic state, without screenshots or API calls."""
import json
from pathlib import Path
import time
from unittest.mock import Mock, patch
from PIL import Image, ImageGrab
from desktop.app import SnowBall
from desktop.screen import Capture

def main():
    folder = Path(__file__).resolve().parents[1] / ".runtime"
    folder.mkdir(exist_ok=True)
    with patch("desktop.app.load_config", return_value=(folder / "smoke-config.json",
               {"token":"test-token-that-is-not-a-real-pairing-token", "side":"right", "voice":False})), \
         patch("desktop.app.Bridge") as bridge:
        bridge.return_value.connected = False
        pet = SnowBall()
        errors = []
        pet.root.report_callback_exception = lambda *args: errors.append(str(args[1]))
        try:
            pet.open_chat()
            pet.voice.set(False)
            pet.root.update()
            assert pet.chat.winfo_ismapped()
            assert pet.chat.winfo_height() <= 850
            import tkinter as tk
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            buttons = [w.cget('text') for w in descendants(pet.chat) if isinstance(w, tk.Button)]
            assert buttons == ['Speak', 'Help me  →', 'Settings'], buttons
            assert all(w.winfo_ismapped() for w in descendants(pet.chat) if isinstance(w, tk.Button))
            for widget in descendants(pet.chat):
                if widget.winfo_ismapped():
                    assert widget.winfo_rooty() + widget.winfo_height() <= pet.chat.winfo_rooty() + pet.chat.winfo_height(), widget
            pet.chat.lift()
            pet.root.update()
            pet.root.after(200)
            x, y = pet.chat.winfo_rootx(), pet.chat.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + pet.chat.winfo_width(), y + pet.chat.winfo_height())).save(folder / 'ui-chat.png')
            with patch('desktop.app.VoiceInput') as recorder:
                pet.dictate()
                recorder.return_value.start.assert_called_once()
                pet.dictate()
                recorder.return_value.stop.assert_called_once()
                pet.cancel_voice()
                recorder.return_value.cancel.assert_called_once()
                assert pet.speak_button.cget('state') == 'normal'
            with patch.object(pet, "navigate") as navigate, patch.object(pet, "start_screen") as screenshot:
                pet.bridge.connected = True
                pet.help_me()
                navigate.assert_not_called()
                screenshot.assert_called_once()
                pet.bridge.connected = False
                pet.help_me()
                self_calls = screenshot.call_count
                assert self_calls == 2
            pet.chat.withdraw()
            pet.screen_mode = True
            pet.guiding = True
            step = {"instruction":"Click Track application.","instruction_local":"Click Track application.",
                    "target_label":"Track application","target":{"x":400,"y":300,"width":200,"height":100},
                    "warning":None,"confidence":.95,"done":False}
            width,height=pet.user32.GetSystemMetrics(0),pet.user32.GetSystemMetrics(1)
            pet.present_screen(Capture(Image.new("RGB",(800,450)),(0,0,width,height),"Synthetic test",0),step)
            end = time.monotonic()+1.5
            while time.monotonic()<end:
                pet.root.update()
                time.sleep(.02)
            assert pet.screen_flight is None
            assert pet.screen_overlay.winfo_ismapped()
            assert pet.screen_card.winfo_ismapped()
            for widget in descendants(pet.screen_card):
                if isinstance(widget, tk.Button):
                    assert widget.winfo_ismapped()
                    assert widget.winfo_rootx() + widget.winfo_width() <= pet.screen_card.winfo_rootx() + pet.screen_card.winfo_width()
            pet.screen_card.lift()
            pet.root.update()
            pet.root.after(200)
            x, y = pet.screen_card.winfo_rootx(), pet.screen_card.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + pet.screen_card.winfo_width(), y + pet.screen_card.winfo_height())).save(folder / 'ui-guidance.png')
            pet.rest()
            pet.root.update()
            assert not pet.screen_mode
            assert pet.screen_overlay is None
            pet.open_settings()
            pet.root.update()
            pet.language_toggle.choose(True)
            toggle_end = time.monotonic() + .25
            while time.monotonic() < toggle_end:
                pet.root.update()
                time.sleep(.01)
            assert pet.language_toggle.position == 1
            assert pet.language_toggle.state_label.cget('text') == 'On'
            assert pet.config['language'] == 'en'
            assert json.loads((folder / 'smoke-config.json').read_text())['language'] == 'en'
            assert pet.chat_heading.cget('text') == 'How can I help?'
            with patch('desktop.app.VoiceInput') as recorder:
                pet.dictate()
                assert recorder.call_args.kwargs['language'] == 'en'
                pet.cancel_voice()
            pet.screen_mode = True
            pet.screen_instruction = 'Click Search.'
            pet.voice.set(True)
            with patch.object(pet.speaker, 'say') as say:
                pet.repeat()
                say.assert_called_once_with('Click Search.', language='en')
            pet.language_toggle.choose(False)
            toggle_end = time.monotonic() + .25
            while time.monotonic() < toggle_end:
                pet.root.update()
                time.sleep(.01)
            assert pet.language_toggle.position == 0
            assert pet.language_toggle.state_label.cget('text') == 'Off'
            pet.voice.set(False)
            assert pet.config['language'] == 'ml'
            assert not pet.screen_mode
            assert all(w.winfo_ismapped() for w in descendants(pet.settings_window) if isinstance(w, tk.Button))
            pet.settings_window.lift()
            pet.root.update()
            pet.root.after(200)
            x, y = pet.settings_window.winfo_rootx(), pet.settings_window.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + pet.settings_window.winfo_width(), y + pet.settings_window.winfo_height())).save(folder / 'ui-settings.png')
            # Exercise the close button without terminating the test process.
            with patch.object(pet, 'finish_quit') as finished:
                pet.close_button.invoke()
                began = pet.exit_started
                assert began is not None
                pet.quit()  # Repeated close requests must not restart the animation.
                assert pet.exit_started == began
                end = time.monotonic() + 2
                while not finished.called and time.monotonic() < end:
                    pet.root.update()
                    time.sleep(.01)
                finished.assert_called_once()
                assert pet.root.winfo_y() > pet.user32.GetSystemMetrics(1)
            assert not errors, errors
            print(json.dumps({"passed":True,"checks":["chat layout","native cat flight","target highlight",
                  "instruction card","stop and return", "sliding language toggle", "jump off screen on close"],"callback_errors":errors}))
        finally:
            pet.root.destroy()

if __name__ == "__main__":
    main()


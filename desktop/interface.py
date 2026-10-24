"""Read Windows accessibility controls locally; no extension or screenshots."""
import json
import os
from pathlib import Path
import subprocess

import httpx

from desktop.screen import Capture


def read_window(user32, window=0):
    script = Path(__file__).with_name('read_interface.ps1')
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive',
             '-ExecutionPolicy', 'Bypass', '-File', str(script),
             '-WindowHandle', str(window)],
            capture_output=True, timeout=12, creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('This app took too long to expose its controls. Try again.') from exc
    if result.returncode:
        raise RuntimeError('Could not read this window. Bring the app to the front and try again.')
    # Windows PowerShell redirects JSON using the system code page unless overridden.
    snapshot = json.loads(result.stdout.decode('utf-8-sig'))
    if snapshot['process_id'] == os.getpid():
        raise RuntimeError('Bring the window you need to the front, then choose Next.')
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    snapshot['elements'] = [e for e in snapshot['elements']
                            if e['rect'][0] >= 0 and e['rect'][1] >= 0
                            and e['rect'][0] + e['rect'][2] <= width
                            and e['rect'][1] + e['rect'][3] <= height]
    if not snapshot['elements']:
        raise RuntimeError('This window exposes no readable controls on the main display. '
                           'Try another page or app. No screenshot was taken.')
    return snapshot, Capture(None, (0, 0, width, height), snapshot['title'][:160], snapshot['window'])


def guide_interface(snapshot, goal, history, backend_url='http://127.0.0.1:8000', language='ml'):
    payload = {'goal': goal, 'language': language, 'title': snapshot['title'][:160],
               'truncated': snapshot['truncated'], 'history': history[-4:],
               'elements': [{k: e[k] for k in ('id', 'name', 'role', 'enabled')}
                            for e in snapshot['elements']]}
    try:
        with httpx.Client(timeout=40, trust_env=False) as client:
            response = client.post(backend_url + '/desktop-step', json=payload)
        if not response.is_success:
            detail = response.json().get('detail', 'Interface guidance unavailable')
            raise RuntimeError(str(detail)[:300])
        return response.json()
    except httpx.RequestError as exc:
        raise RuntimeError('Start the updated Snow Ball backend, then try again.') from exc


def resolve_target(step, snapshot, capture):
    """Resolve an observed ID locally; never accept model-generated coordinates."""
    step = dict(step, target=None)
    selected = step.get('element_id')
    if not selected:
        return step
    element = next((e for e in snapshot['elements'] if e['id'] == selected), None)
    if element is None or not element['enabled']:
        raise RuntimeError('The control changed. Choose Next to read the window again.')
    x, y, width, height = element['rect']
    sw, sh = capture.bounds[2:]
    left, top = int(x * 1000 / sw), int(y * 1000 / sh)
    right, bottom = min(1000, round((x + width) * 1000 / sw)), min(1000, round((y + height) * 1000 / sh))
    step['target'] = {'x': left, 'y': top, 'width': max(1, right - left),
                      'height': max(1, bottom - top)}
    return step

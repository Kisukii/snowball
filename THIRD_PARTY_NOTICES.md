# Third-party code
Snowball retains its own purple cat and Windows Tkinter shell.

## Clicky for Windows
The smoothstep quadratic Bezier flight in desktop/screen.py is adapted from
_begin_flight and _tick in Bitshank-2338/clicky-windows/ui/overlay.py,
revision c00831a545cdfc695559ce3a6ebe77547f19e352.

Copyright (c) 2026 Shashank Singh. MIT License.
The full license and upstream Clicky copyright notice are retained at:
- research/reuse-candidates/clicky-windows/LICENSE
- research/reuse-candidates/clicky-windows/UPSTREAM-CLICKY-LICENSE

Source: https://github.com/Bitshank-2338/clicky-windows

Only platform-independent flight mathematics was adapted. Snowball does not import
PyQt6 or the upstream application.

## Other researched projects
Nanobrowser's observe/revalidate/dispatch approach informed the small Snowball DOM
adapter in extension/controls.js. The complete Nanobrowser engine has not been
integrated. Its Apache-2.0 source study samples and license remain in research/.

ClickyX and Coopanion were architectural references; their applications, assets and
source have not been incorporated into the running app.


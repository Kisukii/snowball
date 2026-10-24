# Snow Ball for Windows

The existing purple cat now supports two guidance paths.

## Start
Run launch_snowball.ps1 from this folder. It starts the local backend if needed and opens the cat's controls.
First installation: run start_desktop.bat and install backend/requirements.txt in the same .venv.
Keep GEMINI_API_KEY in the local .env or backend environment, never in the extension.
The current configured default is gemini-3.5-flash-lite.

## Guide a website
Pair the existing Chrome extension using Copy Chrome pairing code and Extension options.
After updating files, reload Snow Ball at chrome://extensions and refresh the website.
Press Help me. Connected Chrome is used automatically; no screenshot is needed. Snow Ball reads accessible labels, headings, control roles and surrounding context.
The browser cat flies beside the selected control, stretches a paw toward it, highlights it and explains the next step.
Speech input is available through Talk in the browser cat; Windows dictation is also available in the desktop goal field.
Use Next step after filling a field, Repeat to hear it again, or Stop/Come back to end guidance.
Click for me performs one eligible website action after checking its current name, context, enabled state and occlusion.
Payments, passwords, OTPs, final submission and destructive actions remain manual. No automatic typing or action sequence is enabled.

## Guide this screen
When Chrome is not connected, Help me uses screenshot guidance for the primary monitor.
During the three-second countdown, bring the target window onto your PRIMARY monitor.
Snow Ball hides its own controls, captures that monitor, sends a resized JPEG to the local backend, and the backend passes it to Gemini.
Screenshots are not written to disk by this path. Visible information in the screenshot is sent to Google.
The desktop cat flies to the returned control, raises a paw and draws a click-through outline.
The instruction card offers Next screen, Repeat and Stop.
Next screen captures fresh context; the app does not continuously watch the desktop.
Screenshot mode points only. Browser mode offers the optional one-button click helper.
Secondary monitor capture and native desktop clicking are not implemented.

## Verification
- .venv\Scripts\python.exe -m unittest backend.test_main backend.test_vision -v
- .venv\Scripts\python.exe -m desktop.smoke_test
- .venv\Scripts\python.exe -m backend.check_gemini
- node extension/test_controls.cjs (requires Playwright and installed Chrome)

The live Gemini diagnostic sends only generated demo data and makes two API requests.
On 25 October 2026 both checks passed: control-list selection in 3.53 seconds and image target selection in 6.74 seconds.
These timings are a small smoke test, not a reliability or speed guarantee.
The browser checks use synthetic pages; the native smoke test exercises the real Windows Tkinter widgets with synthetic target data.
Specific government workflows and Instagram still need website-by-website acceptance testing.

## Reuse
See THIRD_PARTY_NOTICES.md. The desktop flight math is adapted from the MIT Windows Clicky port.
Nanobrowser informed the observation/actionability design; its entire extension is not imported.
ClickyX and Coopanion were references, not wholesale dependencies. The cat and existing Windows shell are preserved.
Gemini handles both screen understanding and browser-control selection. Groq and xAI's Grok are separate optional providers;
neither is required by this version.

## Troubleshooting
Runtime launch logs are in .runtime (ignored by Git).
A backend running older code must be stopped before starting the updated one.
Backend health: http://127.0.0.1:8000/health.
The response should include screen-guidance, mode gemini, and configured true.
That health response alone does not verify the API key: run the synthetic Gemini diagnostic to do that.
For dictation, press Speak (Win + H); Windows controls microphone setup and permissions.


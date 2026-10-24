# Gemini guidance

1. Create a key at https://aistudio.google.com/apikey using a free-tier project.
2. Stop the old backend in its terminal with Ctrl+C (including mock mode).
3. Double-click `start_backend.bat` in the Snowball folder.
4. Paste your key into the hidden prompt. It stays in the backend process environment and is not saved to a file.
5. Keep that terminal open. Start the desktop cat, pair the Chrome extension, and refresh your website.
6. Enter a goal such as "Show me the sign in button" and select Navigate me.

The default provider is Gemini and the default model is `gemini-3.5-flash-lite`.
Alternatively, copy `.env.example` to `.env` in the Snowball folder and replace the placeholder key locally. The backend loads it on startup; existing terminal environment variables take precedence. Restart the backend after edits. Never commit `.env`.
Free-tier access and quotas depend on your Google account, region, and model availability.
Only use a model with a free tier in your project if you want to avoid paid usage.
Set `GEMINI_MODEL` before launching to choose another supported text model.
Your goal and the extension's page snapshot are sent to Google to select the next control.

Check http://127.0.0.1:8000/health: `mode` should be `gemini` and `configured` should be true.
This check confirms local configuration, not that Google accepted the key.
Keep API keys out of chat, source files, and extension settings.

For manual startup, install `backend/requirements.txt` and run
`python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` with `GEMINI_API_KEY` in the process environment.
Claude is still supported with `PAWLY_MODE=claude` and `ANTHROPIC_API_KEY`.
`PAWLY_MODE=mock` only shows a demo warning and does not choose controls.

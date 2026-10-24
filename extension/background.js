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

      if (new TextEncoder().encode(body).length > 24000) {
        throw new Error('Snapshot too large');
      }

      const key = sender.tab?.id ?? 'panel';

      jobs.get(key)?.abort();

      const controller = new AbortController();
      jobs.set(key, controller);

      const timeout = setTimeout(
        () => controller.abort(),
        28000
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
          let detail = `Backend returned ${response.status}`;

          try {
            const body = await response.json();

            if (typeof body.detail === 'string') {
              detail = body.detail.slice(0, 240);
            }
          } catch {
            // Keep the HTTP status when the backend has no JSON error body.
          }

          throw new Error(detail);
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
      .catch(error => respond({
        ok: false,
        error: error instanceof Error
          ? error.message
          : 'Guidance unavailable'
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

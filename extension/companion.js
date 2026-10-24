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
            'REPLAY',
            'CLICK_TARGET',
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

  // Older loaded manifests may not expose alarms until Chrome reloads them.
  // The initial pairing must still run when this optional wake-up is absent.
  if (chrome.alarms?.create && chrome.alarms?.onAlarm) {
    chrome.alarms.create(
      'snowball-companion',
      { periodInMinutes: 0.5 }
    );

    chrome.alarms.onAlarm.addListener(alarm => {
      if (alarm.name === 'snowball-companion') connect();
    });
  }

  connect();
})();

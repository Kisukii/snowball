(() => {
  const controls = window.SnowBallControls;
  const selector = controls.selector;

  const pet = window.PawlyPet;
  const ids = new WeakMap();

  // Reloading the extension invalidates content scripts on already-open pages.
  // Convert synchronous Chrome API errors to rejected promises for callers.
  function send(message) {
    try {
      if (!chrome.runtime?.id) throw new Error('Refresh this website to reconnect Snow Ball.');
      return Promise.resolve(chrome.runtime.sendMessage(message));
    } catch (error) {
      return Promise.reject(error);
    }
  }

  let voiceEnabled = true;

  chrome.storage.local
    .get("preferences")
    .then(({ preferences }) => {
      voiceEnabled = preferences?.voice !== false;
    }).catch(() => {});

  let serial = 0;
  let elements = [];
  let target = null;
  let state = null;
  let busy = false;
  let clickBusy = false;

  let idleTimer;
  let mutationTimer;
  let tabKey;
  let lastUrl = location.href;
  let epoch = 0;

  const clean = (value, max = 40) =>
    String(value || "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, max);

  const visible = controls.visible;
  const safeText = controls.safeText;
  let targetProof = null;
  function scan() {
    elements = [];

    const goalWords = (state?.goal || '').toLowerCase().split(/\W+/).filter(w => w.length > 2);
    const candidates = controls.collect().filter(el => !pet.host.contains(el) && visible(el));
    const score = el => goalWords.reduce((sum, word) => sum + (controls.name(el).toLowerCase().includes(word) ? 10 : 0), 0) +
      (el.getBoundingClientRect().bottom > 0 && el.getBoundingClientRect().top < innerHeight ? 2 : 0);
    candidates.sort((a, b) => score(b) - score(a));
    for (const el of candidates) {
      if (elements.length === 100) break;

      if (pet.host.contains(el) || !visible(el)) {
        continue;
      }

      if (!ids.has(el)) {
        ids.set(el, `p${++serial}`);
      }

      const id = ids.get(el);
      el.dataset.pawlyId = id;

      const rect = el.getBoundingClientRect();

      const label = controls.name(el);
      // Do not read form values or contenteditable contents.
      const isField =
        ["INPUT", "TEXTAREA", "SELECT"].includes(
          el.tagName
        ) || el.isContentEditable;

      elements.push({
        id,
        tag: el.tagName.toLowerCase(),
        type: clean(el.getAttribute("type"), 24),
        text: isField ? "" : clean(safeText(el), 80),
        label: clean(label, 80),
        role: controls.role(el),
        context: controls.context(el),
        expanded: clean(el.getAttribute("aria-expanded"), 8),
        position:
          `${rect.top < innerHeight / 2 ? "top" : "bottom"}-` +
          `${rect.left < innerWidth / 2 ? "left" : "right"}`
      });
    }

    return elements;
  }

  function speak(text) {
    speechSynthesis.cancel();

    if (!voiceEnabled) return;

    const lang = 'en-US';

    const voices = speechSynthesis.getVoices().filter(candidate => candidate.lang.toLowerCase().startsWith('en'));
    const voice = voices.find(candidate => /jenny|aria|zira|samantha|victoria|female/i.test(candidate.name))
      || voices.find(candidate => candidate.lang === lang) || voices[0];

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    if (voice) utterance.voice = voice;
    utterance.rate = 0.88;
    utterance.pitch = 1.18;
    utterance.volume = 0.9;

    speechSynthesis.speak(utterance);
  }

  function clearTarget() {
    clearTimeout(idleTimer);
    target?.removeAttribute("data-pawly-target");
    target = null;
    targetProof = null;
  }

  async function save() {
    if (tabKey && chrome.runtime?.id) {
      try {
        await chrome.storage.session.set({ [tabKey]: state });
      } catch {
        // A page refresh is required if the extension was reloaded.
      }
    }
  }

  function show(step, replay = false) {
    clearTarget();

    const text =
      `${step.icon} ${step.instruction_local}` +
      (step.warning ? ` ⚠ ${step.warning}` : "");

    pet.set(
      step.done ? "celebrating" : "pointing",
      text
    );

    speak(text);
    state.current = step;

    if (step.element_id) {
      target = [
        ...controls.collect()
      ].find(
        el =>
          el.dataset.pawlyId === step.element_id &&
          visible(el)
      );

      if (target) {
        targetProof = controls.proof(target);
        target.setAttribute("data-pawly-target", "");

        

        setTimeout(() => {
          if (target) {
            pet.move(target.getBoundingClientRect());
          }
        }, 650);
      }
    }

    if (!step.done && target) {
      idleTimer = setTimeout(() => {
        pet.set("pointing", text);
        speak(text);

        idleTimer = setTimeout(
          () => show(step, true),
          10000
        );
      }, 10000);
    }

    if (step.done) idleTimer = setTimeout(() => pet.set('sleeping'), 2500);
if (!replay) save();

    send({
        type: "STEP_UPDATED",
        step,
        number: state.step
      })
      .catch(() => {});
  }

  async function guide(event, clicked = null) {
    if (!state || busy) return;

    busy = true;

    const currentEpoch = epoch;
    clearTimeout(idleTimer);

    try {
      scan();

      const signature = JSON.stringify(elements);
      const url = new URL(location.href);

      url.search = "";
      url.hash = "";
      url.username = "";
      url.password = "";

      const payload = {
        session_id: state.sessionId,
        goal: state.goal,
        language: 'en',
        page: {
          url: url.href.slice(0, 300),
          title: clean(document.title, 80),
          context: [...document.querySelectorAll('h1,h2,h3,[role="heading"],[role="alert"]')]
            .slice(0, 10).map(el => clean(safeText(el), 80)).join(' | ').slice(0, 600),
          elements: [...elements]
        },
        history: state.history.slice(-2),
        event
      };

      if (event === "wrong_click") {
        payload.wrong_click = {
          clicked_element_id: clicked,
          expected_element_id: state.current.element_id
        };
      }

      const size = () =>
        new TextEncoder().encode(
          JSON.stringify(payload)
        ).length;

      while (
        size() > 23500 &&
        payload.history.length
      ) {
        payload.history.shift();
      }

      while (
        size() > 23500 &&
        payload.page.elements.length
      ) {
        payload.page.elements.pop();
      }

      if (size() > 24000) {
        throw new Error("Goal too long");
      }

      const result = await send({
        type: "GUIDE",
        payload
      });

      if (currentEpoch !== epoch) return;

      if (!result?.ok) {
        throw new Error(result?.error || 'Snow Ball did not receive a backend response. Refresh this website and try again.');
      }

      scan();

      // The page may have changed while the API was responding.
      if (JSON.stringify(elements) !== signature) {
        setTimeout(() => guide("stuck"), 0);
        return;
      }

      const step = result.step;

      if (
        step.element_id &&
        !payload.page.elements.some(
          el => el.id === step.element_id
        )
      ) {
        throw new Error("Unknown target");
      }

      if (
        event === "start" ||
        event === "clicked_target"
      ) {
        state.step++;
      }

      if (
        event !== "wrong_click" &&
        event !== "stuck"
      ) {
        state.history.push({
          step: state.step,
          instruction: step.instruction.slice(0, 160),
          element_id: step.element_id
        });
      }

      state.history = state.history.slice(-2);
      show(step);

    } catch (error) {
      if (currentEpoch !== epoch) return;

      clearTarget();

      const text = error instanceof Error
        ? error.message
        : 'Guidance unavailable. Please try again.';

      pet.set("sad", text);
      speak(text);

      send({
          type: "STEP_UPDATED",
          error: text
        })
        .catch(() => {});

    } finally {
      if (currentEpoch === epoch) busy = false;
    }
  }

  document.addEventListener(
    "click",
    event => {
      if (
        !target ||
        !state ||
        busy ||
        event.composedPath().includes(pet.host)
      ) {
        return;
      }

      const expected = target;

      const clickedTarget =
        event.composedPath().includes(expected) ||
        event.target.closest?.("label")?.control ===
          expected;

      if (clickedTarget) {
        const needsExplicitContinue =
          ["INPUT", "TEXTAREA", "SELECT"].includes(
            expected.tagName
          ) &&
          ![
            "submit",
            "button",
            "checkbox",
            "radio"
          ].includes(expected.type);

        if (needsExplicitContinue) return;

        clearTarget();
        pet.set("celebrating", "😻");

        state.pendingNavigation = true;
        save();

        setTimeout(() => {
          if (!state) return;

          state.pendingNavigation = false;
          save();
          guide("clicked_target");
        }, 900);

      } else {
        pet.set("confused");

        const clicked =
          event.target.closest?.(selector);

        guide(
          "wrong_click",
          clicked ? ids.get(clicked) || null : null
        );
      }
    },
    true
  );

  function handleMessage(
    message,
    sender = {},
    respond = () => {}
  ) {
    if (message.type === 'COMPANION_PRESENCE') {
      pet.setCompanion(message.online === true);
      respond({ ok: true });
      return;
    }

    if (message.type === "TOGGLE_WIDGET") {
      pet.toggle();
      respond({ ok: true });
      return;
    }

    if (message.type === "SETTINGS") {
      voiceEnabled =
        message.preferences.voice !== false;

      if (!voiceEnabled) {
        speechSynthesis.cancel();
      }

      if (
        state &&
        state.language !== message.preferences.language
      ) {
        state.language =
          message.preferences.language;

        epoch++;
        busy = false;
        save();
        guide("stuck");
      }

      respond({ ok: true });

    } else if (message.type === "START") {
      epoch++;
      busy = false;
      clearTarget();

      state = {
        sessionId: crypto.randomUUID?.() || [...crypto.getRandomValues(new Uint8Array(16))].map(n => n.toString(16).padStart(2, '0')).join(''),
        goal: message.goal.slice(0, 300),
        language: 'en',
        history: [],
        step: 0,
        current: null
      };

      pet.set("waking");
      save();
      guide("start");
      respond({ ok: true });

    } else if (
      message.type === "REPLAY" &&
      state?.current
    ) {
      show(state.current, true);

    } else if (
      message.type === "CONTINUE" &&
      state
    ) {
      guide("clicked_target");

    } else if (message.type === "CLICK_TARGET") {
      const selected = target, proof = targetProof, actionEpoch = epoch;
      if (!selected || busy || clickBusy) {
        pet.set("sad", "Ask me to find a button first.");
      } else {
        clickBusy = true;
        controls.click(selected, proof, () => epoch !== actionEpoch || state == null)
          .catch(error => {
            if (epoch === actionEpoch) {
              pet.set("sad", error.message);
              speak(error.message);
            }
          }).finally(() => { clickBusy = false; });
      }

    } else if (message.type === "WAKE") {
      pet.set("waking", "Tell me your goal.");

    } else if (message.type === "STOP") {
      epoch++;
      state = null;
      clearTarget();
      speechSynthesis.cancel();

      if (tabKey) {
        chrome.storage.session.remove(tabKey);
      }

      pet.set(
        "sleeping",
        "Snow Ball is resting."
      );

    } else if (message.type === "STATUS") {
      respond({
        step: state?.current,
        number: state?.step || 0
      });
    }
  if (['CONTINUE','STOP','REPLAY','WAKE','CLICK_TARGET'].includes(message.type)) respond({ok:true});
}
addEventListener('keydown', event => {
    if (event.key === 'Escape' && state) handleMessage({type:'STOP'});
  }, true);
pet.onAction = message => handleMessage(message);
  chrome.runtime.onMessage.addListener(handleMessage);

  new MutationObserver(records => {
    const changed = records.some(
      record =>
        record.type === "childList" ||
        (
          record.type === "attributes" &&
          !record.attributeName.startsWith("data-pawly")
        )
    );

    if (!changed) return;

    clearTimeout(mutationTimer);

    mutationTimer = setTimeout(() => {
      scan();

      if (target && (!visible(target) || controls.proof(target) !== targetProof)) {
        clearTarget();
        guide("stuck");
      }
    }, 350);
  }).observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: [
      "hidden",
      "disabled",
      "aria-hidden", "aria-label", "aria-labelledby", "aria-disabled", "aria-expanded"
    ]
  });

  setInterval(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      clearTarget();
      scan();

      if (state) guide("stuck");
    }
  }, 700);

  addEventListener(
    "scroll",
    () => {
      if (target) {
        pet.move(target.getBoundingClientRect());
      }
    },
    { passive: true }
  );

  send({ type: "TAB_ID" })
    .then(async id => {
      tabKey = `pawly-${id}`;

      const stored = (
        await chrome.storage.session.get(tabKey)
      )[tabKey];

      scan();

      if (stored) {
        state = stored;

        const pending = state.pendingNavigation;
        state.pendingNavigation = false;

        guide(
          pending ? "clicked_target" : "stuck"
        );
      }
    }).catch(() => {
      pet.set('sad', 'Refresh this website to reconnect Snow Ball.');
    });
send({type:'COMPANION_STATUS'}).then(r=>pet.setCompanion(r?.online===true)).catch(()=>{});
})();

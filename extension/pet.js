(() => {
  const host = document.createElement('div');
  host.id = 'pawly-root';

  const root = host.attachShadow({ mode: 'closed' });

  root.innerHTML = `<style>
    :host {
      all: initial;
      position: fixed;
      left: 0;
      top: 0;
      width: 128px;
      height: 96px;
      z-index: 2147483647;
      pointer-events: none;
      background: transparent !important;
      border: 0 !important;
      box-shadow: none !important;
      border-radius: 0 !important;
      outline: 0 !important;
      transition:
        left .85s cubic-bezier(.3,.1,.2,1),
        top .85s cubic-bezier(.3,.1,.2,1);
    }

    :host(.following) {
      transition:
        left .18s ease-out,
        top .18s ease-out;
    }

    * { box-sizing: border-box; }

    button, input, textarea, select {
      font: inherit;
    }

    button { cursor: pointer; }

    button:focus-visible,
    textarea:focus,
    select:focus {
      outline: 3px solid #c691ef;
      outline-offset: 3px;
    }

    #pose {
      background: transparent !important;
      border: 0 !important;
      box-shadow: none !important;
    }

    .cat {
      all: unset !important;
      display: block !important;
      position: absolute !important;
      inset: 0 !important;
      width: 128px !important;
      height: 96px !important;
      padding: 0 !important;
      margin: 0 !important;
      border: 0 !important;
      border-radius: 0 !important;
      background: transparent !important;
      box-shadow: none !important;
      outline: none !important;
      cursor: pointer !important;
      pointer-events: auto !important;
    }

    :host(.following) .cat {
      pointer-events: none !important;
    }

    .cat:focus-visible {
      outline: 2px dashed #a276c6 !important;
      outline-offset: 4px !important;
    }

    svg {
      width: 100%;
      height: 100%;
      image-rendering: pixelated;
    }

    .cat svg {
      display: block !important;
      width: 128px !important;
      height: 96px !important;
      background: transparent !important;
      pointer-events: none;
    }

    .tail {
      transform-box: fill-box;
      transform-origin: 90% 95%;
      animation: tail 2.8s ease-in-out infinite;
    }

    .body {
      transform-box: fill-box;
      transform-origin: bottom;
      animation: breathe 3s ease-in-out infinite;
    }

    .eyes-open {
      transform-box: fill-box;
      transform-origin: center;
      animation: blink 4s infinite;
    }

    .sleeping .head {
      transform: translateY(3px);
    }

    .sleeping .paws {
      transform-box: fill-box;
      transform-origin: top;
      animation: dangle 3s ease-in-out infinite;
    }

    .ledge {
      position: absolute;
      left: -90px;
      right: 0;
      top: 78px;
      height: 0;
      border-top: 2px solid #a68dbd;
      background: none;
      z-index: -1;
    }

    .ledge[hidden] {
      display: none;
    }

    .flying .cat {
      animation: fly .85s ease-in-out !important;
    }

    .celebrating .cat {
      animation: hop .45s 3 !important;
    }

    .confused .cat {
      animation: shake .25s 3 !important;
    }

    .flying:before {
      content: '✦';
      position: absolute;
      left: 8px;
      top: 40px;
      color: #c49be8;
      font: 24px system-ui;
      animation: spark .4s infinite;
    }

    .pointer {
      display: none;
      position: absolute;
      left: 0;
      top: 46px;
      width: 36px;
      height: 36px;
    }

    .pointing:not(.flying) .pointer {
      display: block;
      transform-origin: right center;
      animation: none;
    }

    .pointing:not(.left) .cat svg { transform: scaleX(-1); }

    .left .pointer {
      left: auto;
      right: 0;
      transform: scaleX(-1);
    }

    .scroll-down .pointer {
      rotate: -90deg;
      left: 30px;
      top: 74px;
    }

    .scroll-up .pointer {
      rotate: 90deg;
      left: 30px;
      top: 0;
    }

    .scroll-cue {
      position: absolute;
      top: 98px;
      left: -30px;
      width: 190px;
      text-align: center;
      color: #7945ae;
      font: 700 16px system-ui;
      animation: scroll-bounce 1s infinite;
    }

    .scroll-cue[hidden] {
      display: none;
    }

    .bubble {
      position: absolute;
      bottom: 100px;
      right: 0;
      width: 250px;
      max-width: calc(100vw - 24px);
      max-height: 170px;
      overflow: auto;
      padding: 12px 14px;
      border: 2px solid #a17bc5;
      border-radius: 16px;
      background: #fcf8ff;
      color: #38204f;
      font: 600 17px/1.5 system-ui;
      pointer-events: auto;
      box-shadow: 0 6px 22px #36204418;
    }

    .bubble[hidden],
    .menu[hidden],
    button[hidden] {
      display: none;
    }

    .below {
      top: 104px;
      bottom: auto;
    }

    .menu {
      position: fixed;
      width: 300px;
      max-width: calc(100vw - 24px);
      max-height: calc(100vh - 24px);
      overflow: auto;
      pointer-events: auto;
      background: #fcf8ff;
      color: #38204f;
      border: 2px solid #a17bc5;
      border-radius: 18px;
      padding: 16px;
      font: 15px/1.5 system-ui;
      box-shadow: 0 12px 40px #36204428;
    }

    .row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 10px 0;
    }

    .row > * { flex: 1; }

    .title {
      font-weight: 800;
      font-size: 18px;
    }

    .close {
      flex: 0 !important;
      padding: 4px 10px !important;
    }

    button {
      border: 1px solid #b996d6;
      border-radius: 9px;
      padding: 9px;
      background: #f0e3fc;
      color: #38204f;
      min-height: 40px;
    }

    .primary {
      background: #7945ae;
      color: white;
    }

    .small {
      font-size: 12px;
      color: #795c8e;
    }

    .menu textarea,
    .menu select {
      width: 100%;
      padding: 9px;
      border: 1px solid #b996d6;
      border-radius: 9px;
      background: white;
      color: #38204f;
    }

    .menu label {
      display: block;
      margin: 10px 0 5px;
    }

    .menu input[type=checkbox] {
      accent-color: #7945ae;
    }

    summary { cursor: pointer; }
    #status { color: #8b3154; }

    @keyframes tail {
      50% { transform: rotate(-13deg); }
    }

    @keyframes breathe {
      50% { transform: scaleY(.96); }
    }

    @keyframes blink {
      0%, 90%, 100% { transform: scaleY(1); }
      92%, 94% { transform: scaleY(.08); }
    }

    @keyframes fly {
      45% {
        transform: translateY(-22px) rotate(-9deg);
      }
      75% {
        transform: translateY(-8px) rotate(5deg);
      }
    }

    @keyframes hop {
      50% { transform: translateY(-14px); }
    }

    @keyframes shake {
      50% { transform: rotate(-7deg); }
    }

    @keyframes dangle {
      50% { transform: rotate(4deg); }
    }

    @keyframes spark {
      to {
        opacity: 0;
        transform: translate(-20px,10px) scale(.3);
      }
    }

    @keyframes reach {
      0%, 100% {
        scale: .35 1;
        translate: 10px 0;
      }
      50% {
        scale: 1 1;
        translate: -12px 0;
      }
    }

    @keyframes scroll-bounce {
      50% { translate: 0 5px; }
    }

    @media (prefers-reduced-motion: reduce) {
      :host, *,
      .flying .cat,
      .celebrating .cat,
      .confused .cat {
        animation: none !important;
        transition: none !important;
      }
    }
  </style>

  <div id="pose" class="sleeping">
    <div class="ledge"></div>

    <button
      class="cat"
      title="Click Snow Ball to chat"
      aria-label="Snow Ball — click to chat"
      aria-expanded="false"
    >
      ${window.SnowBallSprite('sleeping')}
    </button>

    <span class="pointer" aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        shape-rendering="crispEdges"
      >
        <path d="M22 21L14 16L7 7" fill="none" stroke="#593684"
          stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M22 21L14 16L7 7" fill="none" stroke="#bb8def"
          stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
        <ellipse cx="6" cy="6" rx="5" ry="5" fill="#d8baf8"
          stroke="#593684" stroke-width="1.5"/>
      </svg>
    </span>

    <div class="bubble" role="status" hidden></div>
  </div>

  <section
    class="menu"
    role="dialog"
    aria-label="Snow Ball options"
    hidden
  >
    <div class="row">
      <span class="title">Snow Ball</span>
      <button class="close" aria-label="Close options">
        ×
      </button>
    </div>

    <div class="row">
      <button id="type">⌨ Type</button>
      <button id="talk">🎙 Talk</button>
    </div>

    <label for="goal">
      What would you like help with?
    </label>

    <textarea
      id="goal"
      rows="3"
      maxlength="300"
      placeholder="Help me book a train ticket"
    ></textarea>

    <p class="small">
      No passwords, OTPs or card details. During guidance, say
      “next”, “repeat”, or “stop”.
    </p>

    <div class="row">
      <button id="start" class="primary">
        Navigate me →
      </button>
      <button id="mic" hidden>🎙 Speak</button>
    </div>

    <div class="row">
      <button id="next">Next step</button>
      <button id="click-target">Click for me</button>
      <button id="replay">Replay</button>
      <button id="stop">Rest</button>
    </div>

    <details>
      <summary>⚙ Settings</summary>

      <label for="language">Language</label>
      <select id="language">
        <option value="en">English</option>
      </select>

      <label>
        <input id="voice" type="checkbox" checked>
        Read instructions aloud
      </label>

      <label for="dock">Resting place</label>
      <select id="dock">
        <option value="bottom-right">Bottom right</option>
        <option value="bottom-left">Bottom left</option>
        <option value="top-right">Top right</option>
        <option value="top-left">Top left</option>
      </select>
    </details>

    <p id="status" role="status"></p>
  </section>`;

  const $ = selector => root.querySelector(selector);

  const pose = $('#pose');
  const cat = $('.cat');
  const menu = $('.menu');
  const bubble = $('.bubble');

  let companionMode = false;
  let current = 'sleeping';
  let dock = 'bottom-right';
  let inputMode = 'type';
  let flyTimer;
  let recognition;

  const api = {
    host,
    set,
    move,
    toggle,
    onAction: null,

    get companion() {
      return companionMode;
    },

    setCompanion(enabled) {
      companionMode = enabled;

      host.style.visibility =
        enabled && current === 'sleeping'
          ? 'hidden'
          : 'visible';

      if (enabled && current === 'sleeping') {
        toggle(false);
      }
    }
  };

  function connected() {
    if (chrome.runtime?.id) return true;
    const text = 'Snow Ball was updated. Refresh this website to reconnect, then try Navigate me again.';
    $('#status').textContent = text;
    set('sad', text);
    return false;
  }

  const emit = message => {
    if (!connected()) return false;
    return api.onAction?.(message);
  };

  const clamp = (value, max) =>
    Math.max(12, Math.min(Math.max(12, max), value));

  function place(x, y) {
    host.style.left =
      `${clamp(x, innerWidth - 140)}px`;

    host.style.top =
      `${clamp(y, innerHeight - 108)}px`;

    bubble.classList.toggle(
      'below',
      parseFloat(host.style.top) < 190
    );

    const nearLeft =
      parseFloat(host.style.left) < 150;

    bubble.style.right = nearLeft ? 'auto' : '0';
    bubble.style.left = nearLeft ? '0' : 'auto';

    positionMenu();
  }

  function home() {
    place(
      dock.endsWith('left')
        ? 12
        : innerWidth - 148,
      dock.startsWith('top')
        ? 12
        : innerHeight - 108
    );
  }

  function positionMenu() {
    if (menu.hidden) return;

    const rect = host.getBoundingClientRect();
    const height = menu.offsetHeight;

    menu.style.left =
      `${clamp(rect.right - 300, innerWidth - 312)}px`;

    const above = rect.top - height - 12;

    menu.style.top = `${
      clamp(
        above >= 12 ? above : rect.bottom + 12,
        innerHeight - height - 12
      )
    }px`;
  }

  function toggle(force) {
    host.classList.remove('following');

    menu.hidden =
      force === undefined ? !menu.hidden : !force;

    cat.setAttribute(
      'aria-expanded',
      String(!menu.hidden)
    );

    host.style.visibility =
      menu.hidden &&
      companionMode &&
      current === 'sleeping'
        ? 'hidden'
        : 'visible';

    if (menu.hidden) {
      recognition?.stop();
      cat.focus({ preventScroll: true });

    } else {
      positionMenu();
      $('#goal').focus({ preventScroll: true });
    }
  }

  function set(state, text) {
    current = state;
    host.classList.remove('following');

    host.style.visibility =
      companionMode && state === 'sleeping'
        ? 'hidden'
        : 'visible';

    root.querySelector('.scroll-cue')
      ?.setAttribute('hidden', '');

    clearTimeout(flyTimer);

    pose.className = state;
    cat.innerHTML = window.SnowBallSprite(state);

    bubble.hidden =
      !text ||
      state === 'sleeping' ||
      state === 'waking';

    if (text) bubble.textContent = text;

    $('.ledge').hidden = state !== 'sleeping';

    if (state === 'sleeping') {
      home();
      toggle(false);
    }
  }

  function move(rect) {
    if (!rect) return;
    if (current !== 'pointing') return;

    let cue = root.querySelector('.scroll-cue');

    if (!cue) {
      cue = document.createElement('div');
      cue.className = 'scroll-cue';
      cue.setAttribute('role', 'status');
      pose.append(cue);
    }

    const direction =
      rect.top > innerHeight - 40
        ? 'down'
        : rect.bottom < 40
          ? 'up'
          : '';

    cue.hidden = !direction;

    cue.textContent = direction
      ? `Scroll ${direction} ${
          direction === 'down' ? '↓' : '↑'
        }`
      : '';

    pose.classList.toggle(
      'scroll-down',
      direction === 'down'
    );
    pose.classList.toggle(
      'scroll-up',
      direction === 'up'
    );

    const toLeft =
      !direction &&
      innerWidth - rect.right < 150 &&
      rect.left > 150;

    let x = toLeft
      ? rect.left - 155
      : rect.right + 24;

    let y =
      rect.top + rect.height / 2 - 48;

    if (direction) {
      x = innerWidth - 160;

      y = direction === 'down'
        ? innerHeight - 180
        : 70;

    } else if (
      innerWidth - rect.right < 150 &&
      rect.left < 150
    ) {
      x = rect.left;
      y = rect.bottom + 12;
    }

    const moved =
      Math.abs(
        parseFloat(host.style.left) -
        clamp(x, innerWidth - 140)
      ) > 4 ||
      Math.abs(
        parseFloat(host.style.top) -
        clamp(y, innerHeight - 108)
      ) > 4;

    pose.classList.toggle('left', toLeft);

    if (moved) {
      pose.classList.remove('flying');
      void pose.offsetWidth;
      pose.classList.add('flying');

      clearTimeout(flyTimer);

      flyTimer = setTimeout(
        () => pose.classList.remove('flying'),
        850
      );
    }

    place(x, y);
  }

  function mode(value) {
    inputMode = value;
    $('#mic').hidden = value !== 'talk';

    if (value === 'type') {
      recognition?.stop();
    }
  }

  async function preferences() {
    if (!connected()) return;
    const value = {
      language: $('#language').value,
      voice: $('#voice').checked,
      dock,
      inputMode
    };

    try {
      await chrome.storage.local.set({ preferences: value });
    } catch {
      $('#status').textContent = 'Refresh this website to reconnect Snow Ball.';
      return;
    }

    emit({
      type: 'SETTINGS',
      preferences: value
    });
  }

  cat.addEventListener(
    'click',
    () => toggle()
  );

  $('.close').onclick = () => toggle(false);

  root.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      emit({type:'STOP'});
      toggle(false);
      event.stopPropagation();
    }
  });

  $('#type').onclick = () => {
    mode('type');
    preferences();
    $('#goal').focus();
  };

  $('#talk').onclick = () => {
    mode('talk');
    preferences();
  };

  $('#start').onclick = () => {
    const goal = $('#goal').value.trim();

    if (!goal) {
      $('#status').textContent =
        'Type or speak your goal first.';
      return;
    }

    $('#status').textContent = '';

    const sent = emit({
      type: 'START',
      goal,
      language: $('#language').value
    });

    if (sent !== false) toggle(false);
  };

  $('#click-target').onclick = () => emit({ type: 'CLICK_TARGET' });

  $('#next').onclick = () =>
    emit({ type: 'CONTINUE' });

  $('#replay').onclick = () =>
    emit({ type: 'REPLAY' });

  $('#stop').onclick = () =>
    emit({ type: 'STOP' });

  $('#language').onchange = preferences;
  $('#voice').onchange = preferences;

  $('#dock').onchange = () => {
    dock = $('#dock').value;

    if (current === 'sleeping') {
      home();
    }

    preferences();
    positionMenu();
  };

  const Recognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;

  $('#mic').onclick = () => {
    if (!Recognition) {
      $('#status').textContent =
        'Mic unavailable here. Please type your goal.';
      return;
    }

    if (recognition) {
      recognition.stop();
      return;
    }

    recognition = new Recognition();
    recognition.lang = 'en-US';

    recognition.onresult = event => {
      const transcript =
        event.results[0][0].transcript.trim();

      const command = transcript
        .toLowerCase()
        .replace(/[.!?]/g, '')
        .replace(/\s+/g, ' ');

      const action = {
        next: ['next', 'next step', 'continue'],
        repeat: ['repeat', 'repeat that', 'again', 'replay'],
        stop: ['stop', 'stop guidance', 'cancel', 'rest']
      };

      const commandType = Object.entries(action)
        .find(([, phrases]) => phrases.includes(command))
        ?.[0];

      if (
        commandType &&
        !['sleeping', 'waking'].includes(current)
      ) {
        const messages = {
          next: 'CONTINUE',
          repeat: 'REPLAY',
          stop: 'STOP'
        };
        const statuses = {
          next: 'Moving to the next step…',
          repeat: 'Repeating the current step…',
          stop: 'Stopping guidance…'
        };

        $('#status').textContent = statuses[commandType];
        emit({ type: messages[commandType] });
        return;
      }

      $('#goal').value = transcript.slice(0, 300);

      $('#start').click();
    };

    recognition.onerror = () => {
      $('#status').textContent =
        'Microphone unavailable. You can still type.';
    };

    recognition.onend = () => {
      recognition = null;
      $('#mic').textContent = '🎙 Speak';
    };

    $('#mic').textContent = '⏹ Listening…';

    try {
      recognition.start();
    } catch {
      recognition = null;

      $('#status').textContent =
        'Please type your goal.';
    }
  };

  document.documentElement.append(host);
  window.PawlyPet = api;

  home();

  chrome.storage.local
    .get('preferences')
    .then(({ preferences: value }) => {
      if (!value) return;

      $('#language').value = 'en';
      $('#voice').checked = value.voice !== false;

      dock = [
        'bottom-right',
        'bottom-left',
        'top-right',
        'top-left'
      ].includes(value.dock)
        ? value.dock
        : 'bottom-right';

      $('#dock').value = dock;

      mode(
        value.inputMode === 'talk'
          ? 'talk'
          : 'type'
      );

      if (current === 'sleeping') {
        home();
      }
    }).catch(() => {
      $('#status').textContent = 'Refresh this website to reconnect Snow Ball.';
    });

  addEventListener('resize', () => {
    if (current === 'sleeping') {
      home();
    } else {
      place(
        parseFloat(host.style.left),
        parseFloat(host.style.top)
      );
    }
  });

  addEventListener(
    'pointermove',
    event => {
      if (
        event.pointerType !== 'mouse' ||
        current !== 'sleeping' ||
        !menu.hidden ||
        companionMode
      ) {
        return;
      }

      host.classList.add('following');

      const x = event.clientX > innerWidth - 170
        ? event.clientX - 152
        : event.clientX + 28;

      const y = event.clientY > innerHeight - 128
        ? event.clientY - 112
        : event.clientY + 24;

      place(x, y);
    },
    { passive: true }
  );
})();

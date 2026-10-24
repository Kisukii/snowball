const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function loadContent({ stale = false } = {}) {
  let listener;
  const poses = [];
  const presence = [];
  const moves = [];
  const target = {
    dataset: {}, tagName: 'BUTTON', isConnected: true,
    getBoundingClientRect: () => ({ top: 20, left: 20, width: 80, height: 30 }),
    getAttribute: name => name === 'aria-label' ? 'Sign in' : null,
    setAttribute() {}, removeAttribute() {},
  };
  const pet = {
    host: { contains: () => false },
    set: (...args) => poses.push(args),
    setCompanion: value => presence.push(value),
    move: rect => moves.push(rect), toggle() {},
  };
  const context = {
    window: { PawlyPet: pet },
    chrome: {
      runtime: {
        id: stale ? undefined : 'test-extension',
        onMessage: { addListener: fn => { listener = fn; } },
        sendMessage: async message => {
          if (stale) throw new Error('Extension context invalidated.');
          if (message.type === 'TAB_ID') return 1;
          if (message.type === 'COMPANION_STATUS') return { online: false };
          if (message.type === 'GUIDE') return { ok: true, step: {
            element_id: 'p1', instruction: 'Click Sign in.',
            instruction_local: 'Click Sign in.', icon: 'paw', done: false,
          } };
        },
      },
      storage: {
        local: { get: async () => ({}) },
        session: { get: async () => ({}), set: async () => {}, remove() {} },
      },
    },
    document: {
      title: 'Example', body: {}, addEventListener() {},
      querySelectorAll: () => [target],
      createTreeWalker: () => ({ nextNode: () => null }),
    },
    location: { href: 'https://example.com' },
    getComputedStyle: () => ({ visibility: 'visible', display: 'block' }),
    NodeFilter: { SHOW_TEXT: 4 }, innerHeight: 800, innerWidth: 1200,
    MutationObserver: class { observe() {} },
    addEventListener() {}, setInterval() {}, clearTimeout() {},
    setTimeout: (fn, delay) => { if (delay === 650) fn(); },
    speechSynthesis: { cancel() {}, getVoices: () => [] },
    crypto: { randomUUID: () => 'test-session' },
    URL, TextEncoder, console,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'content.js'), 'utf8'), context);
  return { pet, poses, presence, moves, message: message => listener(message, {}, () => {}) };
}

const settle = () => new Promise(resolve => setImmediate(resolve));

test('desktop presence updates after the page has loaded', async () => {
  const page = loadContent();
  await settle();
  page.message({ type: 'COMPANION_PRESENCE', online: true });
  page.message({ type: 'COMPANION_PRESENCE', online: false });
  assert.deepEqual(page.presence, [false, true, false]);
});

test('Navigate me selects the returned control and moves the cat', async () => {
  const page = loadContent();
  await settle();
  page.pet.onAction({ type: 'START', goal: 'Show sign in' });
  await settle();
  assert.ok(page.poses.some(([pose]) => pose === 'pointing'));
  assert.equal(page.moves.length, 1);
});

test('invalidated extension shows refresh guidance without an unhandled error', async () => {
  const page = loadContent({ stale: true });
  await settle();
  page.pet.onAction({ type: 'START', goal: 'Show sign in' });
  await settle();
  assert.ok(page.poses.some(([pose, text]) => pose === 'sad' && text.includes('Refresh')));
  assert.equal(page.moves.length, 0);
});

test('missing alarms API does not prevent desktop pairing from starting', async () => {
  let pairingRequested = false;
  const context = {
    chrome: {
      runtime: { onMessage: { addListener() {} } },
      tabs: { onRemoved: { addListener() {} } },
      storage: {
        local: { get: async () => { pairingRequested = true; return {}; } },
        session: { set: async () => {} },
        onChanged: { addListener() {} },
      },
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'companion.js'), 'utf8'), context);
  await settle();
  assert.equal(pairingRequested, true);
});

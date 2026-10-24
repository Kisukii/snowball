const $ = id => document.getElementById(id);

$('cat').innerHTML =
  window.SnowBallSprite('sleeping');

$('pair').onclick = async () => {
  const token = $('token').value.trim();

  if (!/^[A-Za-z0-9_-]{32,128}$/.test(token)) {
    $('status').textContent =
      'Copy the pairing code from your desktop cat first.';
    return;
  }

  await chrome.storage.local.set({
    companionToken: token
  });

  $('token').value = '';

  $('status').textContent =
    'Connecting to the desktop app…';
};

$('disconnect').onclick = async () => {
  await chrome.storage.local.remove(
    'companionToken'
  );

  $('status').textContent =
    'Unpaired. The browser cat can still work on its own.';
};

chrome.storage.session
  .get('companionStatus')
  .then(result => {
    if (result.companionStatus) {
      $('status').textContent =
        result.companionStatus;
    }
  });

chrome.storage.onChanged.addListener(
  (changes, area) => {
    if (
      area === 'session' &&
      changes.companionStatus
    ) {
      $('status').textContent =
        changes.companionStatus.newValue;
    }
  }
);

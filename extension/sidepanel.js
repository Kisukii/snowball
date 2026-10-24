const $ = id => document.getElementById(id);

let tabId;

async function activeTab() {
  const [tab] = await chrome.tabs.query({
    active: true,
    currentWindow: true
  });

  tabId = tab?.id;

  if (!tabId) {
    throw new Error("Open a normal website first.");
  }

  return tabId;
}

async function send(message) {
  try {
    return await chrome.tabs.sendMessage(
      await activeTab(),
      message
    );
  } catch {
    $("status").textContent =
      "Snow Ball is unavailable here. Open a normal " +
      "website and refresh the page.";
  }
}

function render(message) {
  if (message.error) {
    $("status").textContent = message.error;
    return;
  }

  if (!message.step) return;

  $("status").textContent = "";

  $("progress").textContent =
    `Step ${message.number || 1}` +
    (message.step.done ? " · Complete 🎉" : "");

  $("instruction").textContent =
    `${message.step.icon} ` +
    message.step.instruction_local;

  $("warning").textContent =
    message.step.warning || "";
}

$("start").onclick = () => {
  const goal = $("goal").value.trim();

  if (!goal) {
    $("status").textContent =
      "Please type or speak your goal first.";
    return;
  }

  send({
    type: "START",
    goal,
    language: $("language").value
  });
};

$("replay").onclick = () =>
  send({ type: "REPLAY" });

$("continue").onclick = () =>
  send({ type: "CONTINUE" });

$("stop").onclick = () => {
  send({ type: "STOP" });

  $("instruction").textContent =
    "💤 Snow Ball is resting.";
};

$("save").onclick = async () => {
  try {
    const url = new URL($("backend").value);

    const localBackend =
      url.protocol === "http:" &&
      ["localhost", "127.0.0.1"].includes(url.hostname);

    if (
      url.protocol !== "https:" &&
      !localBackend
    ) {
      throw new Error(
        "Use HTTPS or a local backend."
      );
    }

    if (url.username || url.password) {
      throw new Error(
        "Do not put credentials in the URL."
      );
    }

    if (url.protocol === "https:") {
      const allowed =
        await chrome.permissions.request({
          origins: [`${url.origin}/*`]
        });

      if (!allowed) {
        throw new Error(
          "Backend access was not granted."
        );
      }
    }

    await chrome.storage.local.set({
      backendUrl: url.origin
    });

    $("status").textContent = "Connection saved.";

  } catch (error) {
    $("status").textContent = error.message;
  }
};

const Recognition =
  window.SpeechRecognition ||
  window.webkitSpeechRecognition;

if (!Recognition) {
  $("mic").disabled = true;
  $("mic").textContent = "Mic unavailable";

} else {
  let recognition;

  $("mic").onclick = () => {
    if (recognition) {
      recognition.stop();
      return;
    }

    recognition = new Recognition();

    recognition.lang = {
      hi: "hi-IN",
      en: "en-IN",
      ta: "ta-IN"
    }[$("language").value];

    recognition.interimResults = false;

    recognition.onresult = event => {
      $("goal").value =
        event.results[0][0].transcript.slice(0, 300);

      $("start").click();
    };

    recognition.onerror = () => {
      $("status").textContent =
        "Microphone unavailable. Please type your goal.";
    };

    recognition.onend = () => {
      recognition = null;
      localize();
    };

    $("mic").textContent = "⏹ Listening…";

    send({ type: "WAKE" });

    try {
      recognition.start();
    } catch {
      recognition = null;

      $("status").textContent =
        "Please type your goal.";
    }
  };
}

chrome.runtime.onMessage.addListener(
  (message, sender) => {
    if (
      message.type === "STEP_UPDATED" &&
      sender.tab?.id === tabId
    ) {
      render(message);
    }
  }
);

async function refresh() {
  render(
    await send({ type: "STATUS" }) || {}
  );
}

chrome.tabs.onActivated.addListener(refresh);

chrome.storage.local
  .get("backendUrl")
  .then(result => {
    if (result.backendUrl) {
      $("backend").value = result.backendUrl;
    }
  });

$("cat").innerHTML = window.SnowBallSprite();

function inputMode(mode) {
  $("input-mode").value = mode;

  $("type").setAttribute(
    "aria-pressed",
    String(mode === "type")
  );

  $("talk").setAttribute(
    "aria-pressed",
    String(mode === "talk")
  );

  $("mic").hidden = mode === "type";

  $("input-hint").textContent =
    mode === "type"
      ? "Type your goal below. No microphone needed. / अपना लक्ष्य लिखें।"
      : "Press the mic to speak, or type below. / बोलें या लिखें।";
}

async function savePreferences() {
  const preferences = {
    language: $("language").value,
    voice: $("voice").checked,
    inputMode: $("input-mode").value
  };

  await chrome.storage.local.set({
    preferences
  });

  document.documentElement.lang =
    preferences.language;

  await send({
    type: "SETTINGS",
    preferences
  });
}

$("type").onclick = () => {
  inputMode("type");
  savePreferences();
  $("goal").focus();
};

$("talk").onclick = () => {
  inputMode("talk");
  savePreferences();
};

$("input-mode").onchange = () => {
  inputMode($("input-mode").value);
  savePreferences();
};

$("voice").onchange = savePreferences;

function localize() {
  const translations = {
    hi: [
      "आप क्या करना चाहते हैं?",
      "साथ चलें →",
      "🔊 फिर सुनें",
      "अगला कदम →",
      "रोकें",
      "🎙 बोलें",
      "आप करें, Snow Ball साथ चले।",
      "मुझे दिल्ली से मुंबई का टिकट बुक करना है"
    ],

    en: [
      "What would you like to do?",
      "Guide me →",
      "🔊 Replay",
      "Next step →",
      "Stop",
      "🎙 Speak",
      "You take the steps. Snow Ball stays beside you.",
      "Help me book a train ticket"
    ],

    ta: [
      "நீங்கள் என்ன செய்ய விரும்புகிறீர்கள்?",
      "வழிகாட்டு →",
      "🔊 மீண்டும் கேள்",
      "அடுத்த படி →",
      "நிறுத்து",
      "🎙 பேசு",
      "நீங்கள் செய்யுங்கள். Snow Ball துணை நிற்கும்.",
      "ரயில் டிக்கெட் பதிவு செய்ய உதவுங்கள்"
    ]
  };

  const text =
    translations[$("language").value] ||
    translations.hi;

  document.querySelector(
    'label[for="goal"]'
  ).textContent = text[0];

  [
    "start",
    "replay",
    "continue",
    "stop",
    "mic"
  ].forEach((id, index) => {
    $(id).textContent = text[index + 1];
  });

  document.querySelector(
    "header p:last-child"
  ).textContent = text[6];

  $("goal").placeholder = text[7];
}

$("language").onchange = () => {
  localize();
  savePreferences();
};

inputMode("type");

chrome.storage.local
  .get("preferences")
  .then(({ preferences }) => {
    if (preferences) {
      $("language").value =
        ["hi", "en", "ta"].includes(
          preferences.language
        )
          ? preferences.language
          : "hi";

      $("voice").checked =
        preferences.voice !== false;

      inputMode(
        preferences.inputMode === "talk"
          ? "talk"
          : "type"
      );
    }

    document.documentElement.lang =
      $("language").value;

    localize();
  });

refresh();
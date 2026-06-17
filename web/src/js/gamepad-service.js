import { signal } from "@preact/signals";
import {
  wsConnected,
  connect as wsConnect,
  send as wsSend,
  disconnect as wsDisconnect,
} from "./ws-client.js";

export { wsConnected };

export const leftStick = signal({ x: 0, y: 0 });
export const rightStick = signal({ x: 0, y: 0 });
export const leftTrigger = signal(0);
export const rightTrigger = signal(0);
// Monotonically increasing counter incremented on every Start-button press
export const startPressed = signal(0);
export const telemetry = signal(null);
export const orientation = signal(null);
export const connected = signal(false);
export const consoleEntries = signal([]);
export const config = signal(null);

const DEADZONE = 0.1;
const POLL_INTERVAL_MS = 50;
const STICK_SEND_INTERVAL_MS = 10;
const CONSOLE_BUFFER_LIMIT = 100_000;

const BUTTON_NAMES = {
  0: "A",
  1: "B",
  2: "X",
  3: "Y",
  4: "Left Bumper",
  5: "Right Bumper",
  6: "Left Trigger",
  7: "Right Trigger",
  8: "Back / Select",
  9: "Start",
  10: "Left Stick",
  11: "Right Stick",
  12: "D-Pad Up",
  13: "D-Pad Down",
  14: "D-Pad Left",
  15: "D-Pad Right",
  16: "Home / Xbox",
};

let gamepadIndex = null;
let previousButtons = [];
let pollInterval = null;
let lastGamepadJSON = "";

let lastStickSent = null;
let lastLeftStickActive = false;
let lastRightStickActive = false;
let lastLeftTriggerActive = false;
let lastRightTriggerActive = false;

function handleWsMessage(data) {
  if (data.name === "STAT") {
    updateStatusDisplay(data);
  } else if (data.name === "ORI") {
    orientation.value = data;
  } else if (data.name === "CONSOLE") {
    console.info(data.line);
    logConsole(data.level, data.line);
  } else if (data.name === "CONFIG") {
    console.info(data.config);
    config.value = data.config;
    logConsole(data.name, JSON.stringify(data.config));
  } else if (data.name === "PONG") {
    // silent heartbeat
  } else {
    const msg = data.name || JSON.stringify(data);
    if (msg && msg !== "{}") {
      logConsole(data.name || "?", JSON.stringify(data));
    }
  }
}

function logConsole(label, message) {
  const timestamp = new Date().toISOString();
  const entries = consoleEntries.value;

  entries.push({ ts: timestamp, label, message });
  while (entries.length > CONSOLE_BUFFER_LIMIT) {
    entries.shift();
  }
  consoleEntries.value = entries.slice();
}

function downloadConsole() {
  const entries = consoleEntries.value;
  if (!entries.length) return;

  const lines = entries.map((e) => `${e.ts} [${e.label}] ${e.message}`);
  const text = `--- Console Log (${new Date().toISOString()}) ---\n\n${lines.join("\n")}\n`;

  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `console-${Date.now()}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  consoleEntries.value = [];
}

function checkForGamepads() {
  const gamepads = navigator.getGamepads();
  for (let i = 0; i < gamepads.length; i++) {
    if (gamepads[i]) {
      gamepadIndex = i;
      connected.value = true;
      return true;
    }
  }
  connected.value = false;
  return false;
}

function start() {
  if (pollInterval || gamepadIndex === null) {
    if (gamepadIndex === null && checkForGamepads()) {
      start();
    }
    return;
  }
  pollInterval = setInterval(updateGamepadState, POLL_INTERVAL_MS);
}

function stop() {
  if (wsConnected.value) {
    wsSend({ type: "stop" });
  }
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

function updateGamepadState() {
  if (gamepadIndex === null) return;

  const gamepads = navigator.getGamepads();
  const gamepad = gamepads[gamepadIndex];

  if (!gamepad) {
    stop();
    return;
  }

  const gamepadJSON = JSON.stringify(gamepad);
  if (gamepadJSON !== lastGamepadJSON) {
    lastGamepadJSON = gamepadJSON;
    wsSend({ type: "gamepad_state", gamepad: JSON.parse(gamepadJSON) });
  }

  gamepad.buttons.forEach((button, index) => {
    const wasPressed = previousButtons[index] || false;
    const isPressed = button.pressed;
    if (!wasPressed && isPressed) onButtonPress(index, button.value);
    else if (wasPressed && !isPressed) onButtonRelease(index, button.value);
  });

  previousButtons = gamepad.buttons.map((b) => b.pressed);

  updateAnalogSticks(gamepad.axes);
  updateAnalogTriggers(gamepad.buttons, gamepad.axes);
}

function onButtonPress(buttonIndex, value) {
  const buttonName = BUTTON_NAMES[buttonIndex] || `Button ${buttonIndex}`;
  wsSend({
    type: "button_press",
    button_index: buttonIndex,
    button_name: buttonName,
    value,
    timestamp: Date.now(),
  });
  if (buttonIndex === 9) {
    startPressed.value = startPressed.value + 1;
  }
  logConsole("BTN", buttonName);
}

function onButtonRelease(buttonIndex, value) {
  const buttonName = BUTTON_NAMES[buttonIndex] || `Button ${buttonIndex}`;
  wsSend({
    type: "button_release",
    button_index: buttonIndex,
    button_name: buttonName,
    value,
    timestamp: Date.now(),
  });
}

function updateAnalogSticks(axes) {
  if (axes.length < 4) return;

  leftStick.value = { x: axes[0], y: axes[1] };
  rightStick.value = { x: axes[2], y: axes[3] };

  if (!lastStickSent || Date.now() - lastStickSent > STICK_SEND_INTERVAL_MS) {
    sendStick("left", axes[0], axes[1]);
    sendStick("right", axes[2], axes[3]);
    lastStickSent = Date.now();
  }
}

function sendStick(name, x, y) {
  const wasActive =
    name === "left" ? lastLeftStickActive : lastRightStickActive;
  const active = Math.abs(x) >= DEADZONE || Math.abs(y) >= DEADZONE;

  if (active) {
    wsSend({ type: "analog_stick", stick: name, x, y, timestamp: Date.now() });
  } else if (wasActive) {
    wsSend({
      type: "analog_stick",
      stick: name,
      x: 0,
      y: 0,
      timestamp: Date.now(),
    });
  }

  if (name === "left") lastLeftStickActive = active;
  else lastRightStickActive = active;
}

function updateAnalogTriggers(buttons, axes) {
  if (buttons.length < 8) return;

  const ltFromBtn = buttons[6].value;
  const rtFromBtn = buttons[7].value;

  const normalizeAxis = (v) => (v + 1) / 2;
  const ltFromAxis = axes.length >= 6 ? normalizeAxis(axes[4]) : 0;
  const rtFromAxis = axes.length >= 6 ? normalizeAxis(axes[5]) : 0;

  const ltVal = ltFromBtn !== 0 ? ltFromBtn : ltFromAxis;
  const rtVal = rtFromBtn !== 0 ? rtFromBtn : rtFromAxis;

  leftTrigger.value = ltVal;
  rightTrigger.value = rtVal;

  sendTrigger("left", ltVal);
  sendTrigger("right", rtVal);
}

function sendTrigger(name, value) {
  const wasActive =
    name === "left" ? lastLeftTriggerActive : lastRightTriggerActive;
  const active = Math.abs(value) >= DEADZONE;

  if (active) {
    wsSend({
      type: "analog_trigger",
      trigger: name,
      value,
      timestamp: Date.now(),
    });
  } else if (wasActive) {
    wsSend({
      type: "analog_trigger",
      trigger: name,
      value: 0,
      timestamp: Date.now(),
    });
  }

  if (name === "left") lastLeftTriggerActive = active;
  else lastRightTriggerActive = active;
}

function updateStatusDisplay(state) {
  telemetry.value = state;
}

function init() {
  bindEvents();
  const socket = wsConnect();
  if (socket) {
    socket.onmessage = (event) => handleWsMessage(JSON.parse(event.data));
  }
  checkForGamepads();
}

function destroy() {
  stop();
  wsDisconnect();
}

function bindEvents() {
  window.addEventListener("gamepadconnected", (e) => {
    console.log("Gamepad connected:", e.gamepad.id);
    gamepadIndex = e.gamepad.index;
    connected.value = true;
    wsSend({
      type: "gamepad_connected",
      gamepad_id: e.gamepad.id,
      index: e.gamepad.index,
    });
    start();
  });

  window.addEventListener("gamepaddisconnected", (e) => {
    console.log("Gamepad disconnected:", e.gamepad.id);
    connected.value = false;
    wsSend({ type: "gamepad_disconnected", gamepad_id: e.gamepad.id });
    stop();
    gamepadIndex = null;
  });
}

function sendConsoleCommand(text) {
  wsSend({ type: "console_command", text });
}

const gamepadService = {
  init,
  destroy,
  downloadConsole,
  sendWebSocketData: wsSend,
  sendConsoleCommand,
};
export default gamepadService;

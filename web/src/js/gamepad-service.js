import { signal } from "@preact/signals";

// ── Reactive signals ────────────────────────────────────────────────
export const leftStick = signal({ x: 0, y: 0 });
export const rightStick = signal({ x: 0, y: 0 });
export const leftTrigger = signal(0);
export const rightTrigger = signal(0);
export const lastButton = signal("None");
export const telemetry = signal(null);
export const connected = signal(false);
export const wsConnected = signal(false);

// ── Service singleton ───────────────────────────────────────────────
class GamepadService {
  constructor() {
    this.gamepadIndex = null;
    this.previousButtons = [];
    this.isRunning = false;
    this.websocket = null;
    this.objectGamepadState = "";

    this.consoleBufferLimit = 100_000;
    this.domBufferLimit = 1_500;
    this.consoleHistory = [];

    // Heavy-weight visualizers — set once by the App component after mount
    this.submarine3D = null;
    this.artificialHorizon = null;

    this.buttonNames = {
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

    this.lastStickSent = null;
    this.lastLeftStickSent = false;
    this.lastRightStickSent = false;
    this.lastLeftTriggerSent = false;
    this.lastRightTriggerSent = false;

    this.firmwareConfig = null;
  }

  // ── Init & lifecycle ──────────────────────────────────────────────
  init(consoleHistoryRef) {
    this._consoleHistoryRef = consoleHistoryRef;
    this.bindEvents();
    this.initWebSocket();
    this.checkForGamepads();
  }

  destroy() {
    this.stop();
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
  }

  // ── Gamepad events ────────────────────────────────────────────────
  bindEvents() {
    window.addEventListener("gamepadconnected", (e) => {
      console.log("Gamepad connected:", e.gamepad.id);
      this.gamepadIndex = e.gamepad.index;
      connected.value = true;
      // Update connection status with gamepad id — handled by signal
      this._updateConnectionDisplay(e.gamepad.id);
      this.sendWebSocketData({
        type: "gamepad_connected",
        gamepad_id: e.gamepad.id,
        index: e.gamepad.index,
      });
      this.start();
    });

    window.addEventListener("gamepaddisconnected", (e) => {
      console.log("Gamepad disconnected:", e.gamepad.id);
      connected.value = false;
      this._updateConnectionDisplay("");
      this.sendWebSocketData({
        type: "gamepad_disconnected",
        gamepad_id: e.gamepad.id,
      });
      this.stop();
      this.gamepadIndex = null;
    });
  }

  checkForGamepads() {
    const gamepads = navigator.getGamepads();
    for (let i = 0; i < gamepads.length; i++) {
      if (gamepads[i]) {
        this.gamepadIndex = i;
        connected.value = true;
        this._updateConnectionDisplay(gamepads[i].id);
        return true;
      }
    }
    connected.value = false;
    this._updateConnectionDisplay("");
    return false;
  }

  _updateConnectionDisplay(gamepadId) {
    // The App component renders the connection status from signals,
    // but we also expose the raw gamepad id for display
    if (this._onConnectionChange) {
      this._onConnectionChange(gamepadId);
    }
  }

  start() {
    if (!this.isRunning && this.gamepadIndex !== null) {
      this.isRunning = true;
      this.loop();
    } else if (this.gamepadIndex === null) {
      if (this.checkForGamepads()) {
        this.start();
      }
    }
  }

  stop() {
    if (wsConnected.value) {
      this.sendWebSocketData({ type: "stop" });
    }
    this.isRunning = false;
  }

  loop() {
    if (!this.isRunning) return;
    this.updateGamepadState();
    setTimeout(() => this.loop(), 50);
  }

  // ── Gamepad state polling ─────────────────────────────────────────
  gamepadToObject(obj) {
    if (obj === null || typeof obj !== "object") return obj;
    if (Array.isArray(obj))
      return obj.map((item) => this.gamepadToObject(item));
    const result = {};
    for (let prop in obj) {
      const value = obj[prop];
      if (typeof value !== "function") {
        result[prop] = this.gamepadToObject(value);
      }
    }
    return result;
  }

  // Native deep equality — replaces lodash _.isEqual
  _deepEqual(a, b) {
    if (a === b) return true;
    if (typeof a !== typeof b) return false;
    if (a === null || b === null) return false;
    if (Array.isArray(a)) {
      if (!Array.isArray(b)) return false;
      if (a.length !== b.length) return false;
      return a.every((val, i) => this._deepEqual(val, b[i]));
    }
    if (typeof a === "object") {
      const keysA = Object.keys(a);
      const keysB = Object.keys(b);
      if (keysA.length !== keysB.length) return false;
      return keysA.every((key) => this._deepEqual(a[key], b[key]));
    }
    return false;
  }

  updateGamepadState() {
    const gamepads = navigator.getGamepads();
    const gamepad = gamepads[this.gamepadIndex];

    if (!gamepad) {
      this.stop();
      return;
    }

    const gamepadObj = this.gamepadToObject(gamepad);
    if (!this._deepEqual(gamepadObj, this.objectGamepadState)) {
      this.objectGamepadState = gamepadObj;
      this.sendWebSocketData({
        type: "gamepad_state",
        gamepad: gamepadObj,
      });
    }

    // Check buttons
    gamepad.buttons.forEach((button, index) => {
      const wasPressed = this.previousButtons[index] || false;
      const isPressed = button.pressed;

      if (!wasPressed && isPressed) {
        this.onButtonPress(index, button.value);
      } else if (wasPressed && !isPressed) {
        this.onButtonRelease(index, button.value);
      }
    });

    // Update analog sticks
    this.updateAnalogSticks(gamepad.axes);
    this.updateAnalogTriggers(gamepad.buttons);

    // Store current button state for next frame
    this.previousButtons = gamepad.buttons.map((button) => button.pressed);
  }

  onButtonRelease(buttonIndex, value) {
    const buttonName = this.buttonNames[buttonIndex] || `Button ${buttonIndex}`;
    this.sendWebSocketData({
      type: "button_release",
      button_index: buttonIndex,
      button_name: buttonName,
      value,
      timestamp: Date.now(),
    });
  }

  onButtonPress(buttonIndex, value) {
    const buttonName = this.buttonNames[buttonIndex] || `Button ${buttonIndex}`;

    this.sendWebSocketData({
      type: "button_press",
      button_index: buttonIndex,
      button_name: buttonName,
      value,
      timestamp: Date.now(),
    });

    // Update signal instead of DOM
    lastButton.value = buttonName;
    this.logConsole("BTN", buttonName);
  }

  updateAnalogSticks(axes) {
    if (axes.length < 4) return;

    // Left stick
    leftStick.value = { x: axes[0], y: axes[1] };
    // Right stick
    rightStick.value = { x: axes[2], y: axes[3] };

    // Send via WebSocket (throttled + deadzone)
    if (!this.lastStickSent || Date.now() - this.lastStickSent > 10) {
      const deadzone = 0.1;

      if (Math.abs(axes[0]) >= deadzone || Math.abs(axes[1]) >= deadzone) {
        this.sendWebSocketData({
          type: "analog_stick",
          stick: "left",
          x: axes[0],
          y: axes[1],
          timestamp: Date.now(),
        });
        this.lastLeftStickSent = true;
      } else if (this.lastLeftStickSent) {
        this.sendWebSocketData({
          type: "analog_stick",
          stick: "left",
          x: 0.0,
          y: 0.0,
          timestamp: Date.now(),
        });
        this.lastLeftStickSent = false;
      }

      if (Math.abs(axes[2]) >= deadzone || Math.abs(axes[3]) >= deadzone) {
        this.sendWebSocketData({
          type: "analog_stick",
          stick: "right",
          x: axes[2],
          y: axes[3],
          timestamp: Date.now(),
        });
        this.lastRightStickSent = true;
      } else if (this.lastRightStickSent) {
        this.sendWebSocketData({
          type: "analog_stick",
          stick: "right",
          x: 0.0,
          y: 0.0,
          timestamp: Date.now(),
        });
        this.lastRightStickSent = false;
      }

      this.lastStickSent = Date.now();
    }
  }

  updateAnalogTriggers(buttons) {
    if (buttons.length < 8) return;

    leftTrigger.value = buttons[6].value;
    rightTrigger.value = buttons[7].value;

    const deadzone = 0.1;
    const now = Date.now();

    if (Math.abs(buttons[6].value) >= deadzone) {
      this.sendWebSocketData({
        type: "analog_trigger",
        trigger: "left",
        value: buttons[6].value,
        timestamp: now,
      });
      this.lastLeftTriggerSent = true;
    }
    if (Math.abs(buttons[6].value) < deadzone && this.lastLeftTriggerSent) {
      this.sendWebSocketData({
        type: "analog_trigger",
        trigger: "left",
        value: 0,
        timestamp: now,
      });
      this.lastLeftTriggerSent = false;
    }

    if (Math.abs(buttons[7].value) >= deadzone) {
      this.sendWebSocketData({
        type: "analog_trigger",
        trigger: "right",
        value: buttons[7].value,
        timestamp: now,
      });
      this.lastRightTriggerSent = true;
    }
    if (Math.abs(buttons[7].value) < deadzone && this.lastRightTriggerSent) {
      this.sendWebSocketData({
        type: "analog_trigger",
        trigger: "right",
        value: 0,
        timestamp: now,
      });
      this.lastRightTriggerSent = false;
    }
  }

  // ── Telemetry / status display ────────────────────────────────────
  updateStatusDisplay(state) {
    telemetry.value = state;

    if (this.submarine3D && state.gyro) {
      let gyroData;
      if (typeof state.gyro === "string") {
        const matches = state.gyro.match(/\(([-\d.]+),([-\d.]+),([-\d.]+)\)/);
        if (matches) {
          gyroData = {
            x: parseFloat(matches[1]),
            y: parseFloat(matches[2]),
            z: parseFloat(matches[3]),
          };
        }
      } else if (Array.isArray(state.gyro)) {
        gyroData = {
          x: state.gyro[0],
          y: state.gyro[1],
          z: state.gyro[2],
        };
      } else if (typeof state.gyro === "object") {
        gyroData = state.gyro;
      }

      if (gyroData) {
        this.submarine3D.updateOrientation(gyroData);
        this.artificialHorizon?.updateOrientation(gyroData);
      }
    }
  }

  // ── WebSocket ─────────────────────────────────────────────────────
  initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/gamepad`;

    try {
      this.websocket = new WebSocket(wsUrl);

      this.websocket.onopen = () => {
        console.log("WebSocket connected");
        wsConnected.value = true;
        this.sendWebSocketData({
          type: "console_command",
          text: "GET_CONFIG",
        });
      };

      this.websocket.onclose = () => {
        console.log("WebSocket disconnected");
        wsConnected.value = false;
        setTimeout(() => this.initWebSocket(), 3000);
      };

      this.websocket.onerror = () => {
        wsConnected.value = false;
      };

      this.websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.name === "STAT") {
          this.updateStatusDisplay(data);
          // only log the raw serial line when it actually has content
          if (data.raw) {
            this.logConsole("DEBUG", data.raw);
          }
        } else if (data.name === "CONSOLE") {
          console.info(data.line);
          this.logConsole(data.level, data.line);
        } else if (data.name === "CONFIG") {
          console.info(data.config);
          this.logConsole(data.name, JSON.stringify(data.config));
          this.firmwareConfig = data.config;
        } else if (data.name === "PONG") {
          // silent — heartbeat acknowledgement, nothing to show
        } else {
          // only log unhandled messages that actually carry content
          const msg = data.name || JSON.stringify(data);
          if (msg && msg !== "{}") {
            this.logConsole(data.name || "?", JSON.stringify(data));
          }
        }
      };
    } catch (error) {
      console.error("Failed to create WebSocket:", error);
      wsConnected.value = false;
    }
  }

  sendWebSocketData(data) {
    if (
      this.websocket &&
      wsConnected.value &&
      this.websocket.readyState === WebSocket.OPEN
    ) {
      this.websocket.send(JSON.stringify(data));
    }
  }

  // ── Console (direct DOM — too large for virtual DOM diffing) ──────
  logConsole(label, message) {
    const timestamp = new Date().toISOString();
    this.consoleHistory.push({ ts: timestamp, label, message });

    while (this.consoleHistory.length > this.consoleBufferLimit) {
      this.consoleHistory.shift();
    }

    const historyEl = this._consoleHistoryRef;
    if (!historyEl) return;

    const ph = historyEl.querySelector(".history-placeholder");
    if (ph) ph.remove();

    const item = document.createElement("div");
    item.className = "history-item";

    const tsSpan = document.createElement("span");
    tsSpan.className = "timestamp";
    tsSpan.textContent = new Date(timestamp).toLocaleTimeString();

    const labelSpan = document.createElement("span");
    labelSpan.className = "button-name";
    labelSpan.textContent = `[${label}]`;

    const valueSpan = document.createElement("span");
    valueSpan.className = "button-value";
    valueSpan.textContent = message;

    item.appendChild(tsSpan);
    item.appendChild(labelSpan);
    item.appendChild(valueSpan);

    historyEl.appendChild(item);
    historyEl.scrollTop = historyEl.scrollHeight;

    while (
      historyEl.querySelectorAll(".history-item").length > this.domBufferLimit
    ) {
      const first = historyEl.querySelector(
        ":scope > .history-item:first-child",
      );
      if (first) first.remove();
    }
  }

  downloadConsole(historyRef) {
    if (!this.consoleHistory.length) return;

    const lines = this.consoleHistory.map(
      (e) => `${e.ts} [${e.label}] ${e.message}`,
    );
    const text =
      `--- Console Log (${new Date().toISOString()}) ---\n\n` +
      lines.join("\n") +
      "\n";

    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `console-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    this.consoleHistory.length = 0;
    if (historyRef) {
      historyRef.innerHTML =
        '<div class="history-placeholder">No messages...</div>';
    }
  }

  // ── 3D / horizon init helpers (called by App component) ───────────
  initSubmarine3D(containerId, modelPath) {
    const initSub = () => {
      if (
        typeof THREE !== "undefined" &&
        typeof OBJLoader !== "undefined" &&
        typeof Submarine3D !== "undefined"
      ) {
        this.submarine3D = new Submarine3D(containerId, modelPath);
        console.log("3D submarine visualization initialized");
      } else {
        console.warn("THREE, Submarine3D class or OBJLoader not found");
      }
    };

    if (typeof THREE !== "undefined" && typeof OBJLoader !== "undefined") {
      initSub();
    } else {
      window.addEventListener("objloader-ready", initSub, { once: true });
    }
  }

  initArtificialHorizon(canvasId) {
    if (typeof ArtificialHorizon !== "undefined") {
      this.artificialHorizon = new ArtificialHorizon(canvasId);
      console.log("Artificial horizon initialized");
    } else {
      console.warn("ArtificialHorizon class not found");
    }
  }

  // ── Testing button handler ────────────────────────────────────────
  handleTestButton() {
    this.onButtonPress(8, 1.0);
  }
}

// Singleton instance
const gamepadService = new GamepadService();
export default gamepadService;

import { render, Fragment } from "preact";
import { useState, useEffect, useRef } from "preact/hooks";

import gamepadService, {
  leftStick,
  rightStick,
  leftTrigger,
  rightTrigger,
  lastButton,
  telemetry,
  connected,
  wsConnected,
} from "./gamepad-service.js";

// ── Stick Display ───────────────────────────────────────────────────
function StickDisplay({ stick }) {
  const x = stick.value.x;
  const y = stick.value.y;

  // Apply deadzone for visual display
  const adjustedX = Math.abs(x) < 0.1 ? 0 : x;
  const adjustedY = Math.abs(y) < 0.1 ? 0 : y;

  // Calculate indicator position (80px container)
  const center = 40;
  const maxRadius = 30;
  const visualX = center + adjustedX * maxRadius;
  const visualY = center + adjustedY * maxRadius;

  return (
    <div>
      <div class="stick-container-overlay">
        <div
          class="stick-indicator"
          style={{ left: `${visualX}px`, top: `${visualY}px` }}
        />
        <div class="stick-center" />
      </div>
      <div class="stick-values-overlay">
        X: {x.toFixed(3)}, Y: {y.toFixed(3)}
      </div>
    </div>
  );
}

// ── Trigger Display ─────────────────────────────────────────────────
function TriggerDisplay({ label, trigger }) {
  const value = trigger.value;
  return (
    <div class="trigger-values-overlay">
      {label}: {value.toFixed(3)}
    </div>
  );
}

// ── Last Button Display ─────────────────────────────────────────────
function LastButtonDisplay() {
  const btn = lastButton.value;
  return (
    <div class="overlay-button-display">
      <div class="overlay-label">Last Button</div>
      <div class="button-display-overlay">
        <span class="button-name">{btn}</span>
      </div>
    </div>
  );
}

// ── Telemetry Readout ───────────────────────────────────────────────
const TELEMETRY_FIELDS = [
  ["bat", "Battery"],
  ["depth", "Depth"],
  ["acc", "Accel"],
  ["gyro", "Gyro"],
  ["temp", "Temp"],
  ["hum", "Humidity"],
  ["mcu", "MCU Temp"],
  ["pi", "Pi Temp"],
  ["ia", "IA"],
  ["ib", "IB"],
  ["fm", "FM"],
  ["fj", "FJ"],
  ["td", "TD"],
  ["br", "BR"],
];

function TelemetryReadout() {
  const state = telemetry.value;

  return (
    <div class="overlay-status-left">
      <div class="stick-values-overlay status-values">
        {!state ? (
          "Waiting for telemetry"
        ) : (
          <>
            {TELEMETRY_FIELDS.map(([key, label]) => {
              const val = state[key];
              if (val == null) return null;
              return (
                <div key={key}>
                  {label}: {Array.isArray(val) ? val.join(", ") : val}
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}

// ── Connection Status ───────────────────────────────────────────────
function ConnectionStatus() {
  const isConn = connected.value;
  const isWs = wsConnected.value;

  return (
    <div class="gamepad-status">
      <div class="status-item">
        <label>Controller:</label>
        <span class={isConn ? "status-connected" : "status-disconnected"}>
          {isConn ? "Connected" : "Disconnected"}
        </span>
      </div>
      <div class="status-item">
        <label>Drone:</label>
        <span class={isWs ? "status-connected" : "status-disconnected"}>
          {isWs ? "Connected" : "Connecting..."}
        </span>
      </div>
    </div>
  );
}

// ── Submarine 3D Container ──────────────────────────────────────────
function Submarine3DContainer() {
  useEffect(() => {
    gamepadService.initSubmarine3D(
      "submarine-3d-container",
      "/static/subsanwich.obj",
    );
  }, []);

  return (
    <div class="overlay-submarine-3d">
      <div id="submarine-3d-container" class="submarine-3d-container" />
    </div>
  );
}

// ── Artificial Horizon Canvas ───────────────────────────────────────
function ArtificialHorizonCanvas() {
  useEffect(() => {
    gamepadService.initArtificialHorizon("artificial-horizon");
  }, []);

  return (
    <div class="overlay-artificial-horizon">
      <canvas id="artificial-horizon" width="200" height="200" />
    </div>
  );
}

// ── Console Panel ───────────────────────────────────────────────────
function ConsolePanel({ historyRef }) {
  const [collapsed, setCollapsed] = useState(true);
  const inputRef = useRef(null);

  const handleDownload = () => {
    gamepadService.downloadConsole(historyRef.current);
  };

  const handleConsoleInput = (e) => {
    if (e.key === "Enter" && inputRef.current?.value.trim()) {
      gamepadService.sendWebSocketData({
        type: "console_command",
        text: inputRef.current.value.trim(),
      });
      inputRef.current.value = "";
    }
  };

  return (
    <>
      <div class="console-controls">
        <button
          id="download-console"
          onClick={handleDownload}
          title="Download &amp; clear"
        >
          ⬇ Download Console
        </button>
        <label
          for="console-collapsed"
          id="collapse-console"
          title="Toggle console"
          onClick={() => setCollapsed(!collapsed)}
        >
          ☰ {collapsed ? "Show Console" : "Hide Console"}
        </label>
      </div>

      <div
        class="console-section"
        style={{ display: collapsed ? "none" : "flex" }}
      >
        <div class="console-body">
          <div id="console-history" ref={historyRef} class="console-buffer">
            <div class="history-placeholder">No messages...</div>
          </div>
          <div class="console-input-row">
            <input
              type="text"
              ref={inputRef}
              class="console-input"
              placeholder="Send command..."
              autocomplete="off"
              onKeyDown={handleConsoleInput}
            />
          </div>
        </div>
      </div>
    </>
  );
}

// ── Video Stream ────────────────────────────────────────────────────
function VideoStream() {
  const iframeRef = useRef(null);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    function hideControls() {
      try {
        const doc = iframe.contentDocument || iframe.contentWindow?.document;
        if (!doc) return;
        const video = doc.querySelector("video");
        if (video) {
          video.removeAttribute("controls");
          video.style.pointerEvents = "none";
        }
      } catch (_) {}
    }

    iframe.addEventListener("load", hideControls);
    setTimeout(hideControls, 500);
    setTimeout(hideControls, 1500);
  }, []);

  return (
    <iframe
      ref={iframeRef}
      src="/cam"
      title="Camera Feed"
      class="video-stream"
    />
  );
}

// ── App (Root) ──────────────────────────────────────────────────────
function App() {
  const consoleHistoryRef = useRef(null);

  useEffect(() => {
    gamepadService.init(consoleHistoryRef.current);
    return () => gamepadService.destroy();
  }, []);

  return (
    <div class="container">
      <div class="gamepad-section">
        <div class="video-stream-container">
          <div class="video-overlay-wrapper">
            <VideoStream />

            {/* Gamepad Overlay */}
            <div class="gamepad-overlay">
              <LastButtonDisplay />
              <TelemetryReadout />
              <Submarine3DContainer />
              <ArtificialHorizonCanvas />

              <div class="overlay-stick-left">
                <StickDisplay stick={leftStick} />
              </div>

              <div class="overlay-stick-right">
                <StickDisplay stick={rightStick} />
              </div>

              <div class="overlay-trigger-left">
                <TriggerDisplay label="LT" trigger={leftTrigger} />
              </div>

              <div class="overlay-trigger-right">
                <TriggerDisplay label="RT" trigger={rightTrigger} />
              </div>
            </div>
          </div>
        </div>

        <button
          id="testing-btn"
          onClick={() => gamepadService.handleTestButton()}
        >
          reset
        </button>

        <ConnectionStatus />
      </div>

      <ConsolePanel historyRef={consoleHistoryRef} />
    </div>
  );
}

// ── Mount ───────────────────────────────────────────────────────────
const root = document.getElementById("app");
if (root) {
  render(<App />, root);
} else {
  console.error("#app mount point not found!");
}

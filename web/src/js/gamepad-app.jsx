import { render, Fragment } from "preact";
import { useState, useEffect, useRef } from "preact/hooks";
import ArtificialHorizon from "./artificial-horizon.jsx";
import Submarine3D from "./submarine-3d.jsx";

import gamepadService, {
  leftStick,
  rightStick,
  leftTrigger,
  rightTrigger,
  lastButton,
  telemetry,
  connected,
  wsConnected,
  consoleEntries,
} from "./gamepad-service.js";

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

function TriggerDisplay({ label, trigger }) {
  const value = trigger.value;
  return (
    <div class="trigger-values-overlay">
      {label}: {value.toFixed(3)}
    </div>
  );
}

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

function Submarine3DContainer() {
  const gyro = telemetry.value?.gyro;
  let gyroData = null;
  if (gyro) {
    if (typeof gyro === "string") {
      const matches = gyro.match(/\(([-\d.]+),([-\d.]+),([-\d.]+)\)/);
      if (matches) {
        gyroData = {
          x: parseFloat(matches[1]),
          y: parseFloat(matches[2]),
          z: parseFloat(matches[3]),
        };
      }
    } else if (Array.isArray(gyro)) {
      gyroData = { x: gyro[0], y: gyro[1], z: gyro[2] };
    } else if (typeof gyro === "object") {
      gyroData = gyro;
    }
  }

  return (
    <div class="overlay-submarine-3d">
      <Submarine3D modelPath="/static/subsanwich.obj" gyro={gyroData} />
    </div>
  );
}

function ArtificialHorizonCanvas() {
  const gyro = telemetry.value?.gyro;
  const pitch = Array.isArray(gyro) ? gyro[1] : gyro?.y || 0;
  const roll = Array.isArray(gyro) ? gyro[0] : gyro?.x || 0;

  return (
    <div class="overlay-artificial-horizon">
      <ArtificialHorizon pitch={pitch} roll={roll} />
    </div>
  );
}

function ConsolePanel() {
  const [collapsed, setCollapsed] = useState(true);
  const inputRef = useRef(null);
  const historyRef = useRef(null);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    const el = historyRef.current;
    if (el && !collapsed) {
      el.scrollTop = el.scrollHeight;
    }
  });

  const handleDownload = () => {
    gamepadService.downloadConsole();
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

  const entries = consoleEntries.value;
  const displayEntries = entries.slice(-1500);

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
            {displayEntries.length === 0 ? (
              <div class="history-placeholder">No messages...</div>
            ) : (
              displayEntries.map((entry, i) => (
                <div class="history-item" key={i}>
                  <span class="timestamp">
                    {new Date(entry.ts).toLocaleTimeString()}
                  </span>
                  <span class="button-name">[{entry.label}]</span>
                  <span class="button-value">{entry.message}</span>
                </div>
              ))
            )}
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

function App() {
  useEffect(() => {
    gamepadService.init();
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

        <ConnectionStatus />
      </div>

      <ConsolePanel />
    </div>
  );
}

const root = document.getElementById("app");
if (root) {
  render(<App />, root);
} else {
  console.error("#app mount point not found!");
}

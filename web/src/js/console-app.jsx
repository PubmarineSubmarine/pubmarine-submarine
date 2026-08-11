import { render } from "preact";
import { useEffect, useRef, useState } from "preact/hooks";

import gamepadService, {
  consoleEntries,
  config,
  heartbeatEnabled,
  wsConnected,
} from "./gamepad-service.js";

import { TelemetryReadout } from "./components/telemetry.jsx";
import { Submarine3DContainer } from "./components/submarine-3d-container.jsx";

function ConfigEditor() {
  const inputRef = useRef(null);
  const cfg = config.value;
  const ws = wsConnected.value;

  // Pretty-print the received config; track whether the textarea is dirty
  // so an incoming CONFIG doesn't clobber the user's in-progress edits.
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState("");

  const formatted = cfg ? JSON.stringify(cfg, null, 2) : "";

  useEffect(() => {
    if (!dirty && inputRef.current) {
      inputRef.current.value = formatted;
    }
  }, [formatted, dirty]);

  // Request the config whenever the websocket connects (and again any
  // time it transitions from disconnected → connected).
  useEffect(() => {
    if (!ws) return;
    gamepadService.sendConsoleCommand("GET_CONFIG");
  }, [ws]);

  const handleChange = () => {
    setDirty(true);
    setStatus("");
  };

  const handleSubmit = () => {
    const raw = inputRef.current?.value ?? "";
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      setStatus(`Invalid JSON: ${e.message}`);
      return;
    }
    try {
      gamepadService.sendConsoleCommand(`SET_CONFIG ${JSON.stringify(parsed)}`);
      setStatus("Sent SET_CONFIG — updating when drone responds…");
    } catch (e) {
      setStatus(`Send failed: ${e.message}`);
    }
  };

  return (
    <div class="config-editor">
      <div class="config-editor-header">
        <span class="config-editor-label">Config</span>
        {status && <span class="config-editor-status">{status}</span>}
      </div>
      <textarea
        ref={inputRef}
        class="config-editor-textarea"
        placeholder={ws ? "Loading config..." : "Waiting for drone connection..."}
        spellcheck={false}
        onInput={handleChange}
        disabled={!ws}
      />
      <div class="config-editor-actions">
        <button
          class="config-editor-reload"
          onClick={() => {
            setDirty(false);
            gamepadService.sendConsoleCommand("GET_CONFIG");
          }}
          disabled={!ws}
          title="Re-fetch config from drone"
        >
          ↻ Reload
        </button>
        <button
          class="config-editor-submit"
          onClick={handleSubmit}
          disabled={!ws || dirty === false && cfg == null}
          title="Send SET_CONFIG"
        >
          ✓ Save
        </button>
      </div>
    </div>
  );
}

function FullscreenConsole() {
  const historyRef = useRef(null);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    const el = historyRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  });

  const handleDownload = () => {
    gamepadService.downloadConsole();
  };

  const handleCalibrate = () => {
    gamepadService.sendConsoleCommand("CAL");
  };

  const handleToggleHeartbeat = () => {
    gamepadService.setHeartbeatEnabled(!heartbeatEnabled.value);
  };

  const entries = consoleEntries.value;
  const displayEntries = entries.slice(-1500);

  return (
    <div class="fullscreen-console">
      <div class="fullscreen-console-header">
        <TelemetryReadout />
        <Submarine3DContainer />
        <ConfigEditor />
        <div class="fullscreen-console-buttons">
          <button
            id="calibrate-orientation"
            onClick={handleCalibrate}
            title="Capture current orientation as the new home pose"
          >
            ⚓ Calibrate
          </button>
          <button
            id="download-console"
            onClick={handleDownload}
            title="Download &amp; clear"
          >
            ⬇ Download Console
          </button>
          <button
            id="toggle-heartbeat"
            onClick={handleToggleHeartbeat}
            title="Toggle motor-failsafe heartbeat"
          >
            {heartbeatEnabled.value ? "❤ Heartbeat: On" : "♡ Heartbeat: Off"}
          </button>
        </div>
      </div>

      <div id="console-history" ref={historyRef} class="fullscreen-console-buffer">
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

      <div class="fullscreen-console-input-row">
        <input
          type="text"
          class="console-input"
          placeholder="Send command..."
          autocomplete="off"
          onKeyDown={(e) => {
            if (e.key === "Enter" && e.currentTarget.value.trim()) {
              gamepadService.sendConsoleCommand(e.currentTarget.value.trim());
              e.currentTarget.value = "";
            }
          }}
        />
      </div>
    </div>
  );
}

function App() {
  useEffect(() => {
    gamepadService.init();
    return () => gamepadService.destroy();
  }, []);

  return <FullscreenConsole />;
}

const root = document.getElementById("app");
if (root) {
  render(<App />, root);
} else {
  console.error("#app mount point not found!");
}

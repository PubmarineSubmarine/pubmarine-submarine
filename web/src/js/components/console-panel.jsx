import { useEffect, useRef } from "preact/hooks";
import gamepadService, {
  startPressed,
  consoleEntries,
} from "../gamepad-service.js";

export function ConsolePanel({ collapsed, onToggle }) {
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

  const handleCalibrate = () => {
    gamepadService.sendWebSocketData({
      type: "console_command",
      text: "CAL",
    });
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
        <label
          for="console-collapsed"
          id="collapse-console"
          title="Toggle console"
          onClick={onToggle}
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

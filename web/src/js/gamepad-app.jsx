import { render } from "preact";
import { useState, useEffect, useRef } from "preact/hooks";
import ArtificialHorizon from "./artificial-horizon.jsx";
import Submarine3D from "./submarine-3d.jsx";

import gamepadService, {
  leftStick,
  rightStick,
  leftTrigger,
  rightTrigger,
  startPressed,
  orientation,
  connected,
  wsConnected,
} from "./gamepad-service.js";

import { TelemetryReadout } from "./components/telemetry.jsx";
import { ConsolePanel } from "./components/console-panel.jsx";

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
  return null;
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
  const ori = orientation.value;

  return (
    <div class="overlay-submarine-3d">
      <Submarine3D
        modelPath="/static/subsanwich.obj"
        orientation={ori}
      />
    </div>
  );
}

function ArtificialHorizonCanvas() {
  const ori = orientation.value;
  const pitch = ori?.pitch ?? 0;
  const roll = ori?.roll ?? 0;

  return (
    <div class="overlay-artificial-horizon">
      <ArtificialHorizon pitch={pitch} roll={roll} />
    </div>
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
  const [consoleCollapsed, setConsoleCollapsed] = useState(true);
  const toggleConsole = () => setConsoleCollapsed((c) => !c);

  useEffect(() => {
    gamepadService.init();
    return () => gamepadService.destroy();
  }, []);

  // Toggle the console when the gamepad's Start button is pressed.
  useEffect(() => {
    return startPressed.subscribe(() => {
      setConsoleCollapsed((c) => !c);
    });
  }, []);

  return (
    <div class="container">
      <div class="gamepad-section">
        <div class="video-stream-container">
          <div class="video-overlay-wrapper">
            <VideoStream />

            {/* Gamepad Overlay */}
            <div class="gamepad-overlay">
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

      <ConsolePanel collapsed={consoleCollapsed} onToggle={toggleConsole} />
    </div>
  );
}

const root = document.getElementById("app");
if (root) {
  render(<App />, root);
} else {
  console.error("#app mount point not found!");
}

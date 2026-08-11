import { signal } from "@preact/signals";

export const wsConnected = signal(false);

let ws = null;
let reconnectTimer = null;

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/gamepad`;

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("WebSocket connected");
      wsConnected.value = true;
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      wsConnected.value = false;
      ws = null;
      reconnectTimer = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      wsConnected.value = false;
    };

    return ws;
  } catch (error) {
    console.error("Failed to create WebSocket:", error);
    wsConnected.value = false;
    return null;
  }
}

function send(data) {
  if (ws && wsConnected.value && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    ws.close();
    ws = null;
  }
}

export { connect, send, disconnect };

import { activeAlerts, WARN, CRITICAL } from "../alerts.js";
import { sendConsoleCommand } from "../gamepad-service.js";

export function AlertBanner() {
  const alerts = activeAlerts.value;

  if (!alerts || alerts.length === 0) return null;

  return (
    <div class="alert-banner-container">
      {alerts.map((alert) => (
        <div key={alert.id} class={`alert-banner alert-banner--${alert.severity}`}>
          <span class="alert-banner-message">{alert.message}</span>
          {alert.action && (
            <button
              class="alert-banner-btn"
              onClick={() => sendConsoleCommand(alert.action.command)}
            >
              {alert.action.label}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

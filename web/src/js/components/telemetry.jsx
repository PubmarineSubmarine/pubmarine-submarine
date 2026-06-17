import { telemetry, orientation } from "../gamepad-service.js";

export const TELEMETRY_FIELDS = [
  ["bat", "Battery"],
  ["depth", "Depth"],
  ["acc", "Accel"],
  ["gyro", "Gyro"],
  ["ori", "Ori"],
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

export function TelemetryReadout() {
  const state = telemetry.value;
  const ori = orientation.value;

  return (
    <div class="overlay-status-left">
      <div class="stick-values-overlay status-values">
        {!state ? (
          "Waiting for telemetry"
        ) : (
          <>
            {TELEMETRY_FIELDS.map(([key, label]) => {
              if (key === "ori") {
                if (!ori) return null;
                return (
                  <div key={key}>
                    {label}: r={ori.roll?.toFixed(1)} p={ori.pitch?.toFixed(1)} y={ori.yaw?.toFixed(1)}
                  </div>
                );
              }
              const val = state[key];
              if (val == null) return null;
              const fmt = (n) => (typeof n === "number" ? n.toFixed(1) : n);
              const text = Array.isArray(val) ? val.map(fmt).join(", ") : val;
              return (
                <div key={key}>
                  {label}: {text}
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}

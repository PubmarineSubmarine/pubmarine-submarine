import { computed } from "@preact/signals";
import { telemetry, config, sendConsoleCommand } from "./gamepad-service.js";

export const WARN = "warn";
export const CRITICAL = "critical";

const DEFAULTS = {
  battery_warn_voltage: 10.5,
  battery_critical_voltage: 9.9,
};

const ALERT_DEFINITIONS = [
  {
    id: "battery-critical",
    check: (state, cfg) => {
      const threshold = cfg?.battery_critical_voltage ?? DEFAULTS.battery_critical_voltage;
      return state?.bat != null && state.bat < threshold;
    },
    severity: CRITICAL,
    message: (state) => `Battery critical: ${state.bat.toFixed(1)}V`,
  },
  /* {
    id: "driver-fault",
    check: (state) => state?.fm != null && state?.fj != null && (state.fm === 0 || state.fj === 0),
    severity: CRITICAL,
    message: (state) => {
      const parts = [];
      if (state.fm === 0) parts.push("motor");
      if (state.fj === 0) parts.push("jet");
      return `Driver fault: ${parts.join(" + ")} driver`;
    },
    action: { label: "Clear Fault", command: "CLEAR_FAULT" },
  }, */
  {
    id: "battery-warn",
    check: (state, cfg) => {
      const critical = cfg?.battery_critical_voltage ?? DEFAULTS.battery_critical_voltage;
      const warn = cfg?.battery_warn_voltage ?? DEFAULTS.battery_warn_voltage;
      return state?.bat != null && state.bat >= critical && state.bat < warn;
    },
    severity: WARN,
    message: (state) => `Battery low: ${state.bat.toFixed(1)}V`,
  },
];

export const activeAlerts = computed(() => {
  const state = telemetry.value;
  const cfg = config.value;
  if (!state) return [];

  return ALERT_DEFINITIONS
    .filter((def) => def.check(state, cfg))
    .map((def) => ({
      id: def.id,
      severity: def.severity,
      message: def.message(state),
      action: def.action,
    }));
});

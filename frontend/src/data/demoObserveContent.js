/** Manager-friendly copy for the observability demo (≈60-second read). */

export const OBSERVE_DEMO_INTRO = {
  headline: "Unified observability — one pane for on-call",
  bullets: [
    {
      label: "The problem",
      text: "Engineers lose minutes jumping between Prometheus, Loki, and trace tools during an incident — context fragments before triage even starts.",
    },
    {
      label: "This demo",
      text: "Metrics, logs, and OTEL pipeline health for auth-service in a single Observe view — the same signals an enterprise NOC would correlate.",
    },
    {
      label: "The outcome",
      text: "Faster time-to-context: one screen shows SLI drift, stack health, and anomaly feed so you can decide whether to escalate or drill deeper.",
    },
  ],
};

export const OBSERVE_DEMO_SERVICES = ["auth-service", "payment-api"];

export const OBSERVE_DEMO_DEFAULT_SERVICE = "auth-service";

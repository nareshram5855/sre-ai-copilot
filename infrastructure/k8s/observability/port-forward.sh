#!/usr/bin/env bash
# Port-forward observability services to localhost for the host-run backend.
# Uses 19090/13100 to avoid clashing with kube-prometheus-stack on 9090/3100.
set -euo pipefail

PROM_PORT="${PROMETHEUS_LOCAL_PORT:-19090}"
LOKI_PORT="${LOKI_LOCAL_PORT:-13100}"
NS=observability

_stop_pf() {
  local port=$1
  local pids
  pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    echo "    Stopping stale port-forward on :$port"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

echo "==> Port-forwarding observability stack to localhost"
# Kill stale/hung port-forwards first (common after sleep or minikube restart).
_stop_pf "$PROM_PORT"
_stop_pf "$LOKI_PORT"

kubectl port-forward "svc/prometheus" -n "$NS" "${PROM_PORT}:9090" >/tmp/pf-prometheus.log 2>&1 &
kubectl port-forward "svc/loki"       -n "$NS" "${LOKI_PORT}:3100" >/tmp/pf-loki.log 2>&1 &

_wait_ready() {
  local url=$1 label=$2
  local i
  for i in 1 2 3 4 5; do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "  ✓ $label"
      return 0
    fi
    sleep 1
  done
  echo "  ⚠ $label — not ready (see /tmp/pf-*.log)"
  return 1
}

sleep 2
_wait_ready "http://localhost:${PROM_PORT}/-/healthy" "Prometheus  http://localhost:${PROM_PORT}"
_wait_ready "http://localhost:${LOKI_PORT}/ready"     "Loki        http://localhost:${LOKI_PORT}"
echo ""
echo "  Leave this terminal open, or run processes in background."
echo "  Backend .env should use:"
echo "    PROMETHEUS_URL=http://localhost:${PROM_PORT}"
echo "    LOKI_URL=http://localhost:${LOKI_PORT}"

#!/usr/bin/env bash
# Idempotent observability port-forwards for hybrid Minikube dev on macOS.
# Kills stale kubectl port-forward processes, starts fresh ones, verifies health.
#
# Usage:
#   scripts/ensure-port-forwards.sh           # start + verify once (exit 0/1)
#   scripts/ensure-port-forwards.sh --loop    # daemon: re-check every 30s
set -euo pipefail

PROM_PORT="${PROMETHEUS_LOCAL_PORT:-19090}"
LOKI_PORT="${LOKI_LOCAL_PORT:-13100}"
NS="${OBSERVABILITY_NS:-observability}"
LOOP="${1:-}"

_log() { echo "==> $*"; }

_minikube_ok() {
  local i
  for i in 1 2 3 4 5; do
    kubectl cluster-info >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

_kubectl_pf_pids() {
  local port=$1
  pgrep -f "kubectl port-forward svc/(prometheus|loki).*${port}:" 2>/dev/null || true
}

_stop_pf_on_port() {
  local port=$1
  local pids
  pids=$(_kubectl_pf_pids "$port")
  if [[ -z "$pids" ]]; then
    pids=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)
  fi
  if [[ -n "$pids" ]]; then
    _log "Stopping kubectl port-forward on :$port (pid $pids)"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

_pf_alive() {
  local port=$1
  local pids
  pids=$(_kubectl_pf_pids "$port")
  [[ -n "$pids" ]] && kill -0 $pids 2>/dev/null
}

_start_pfs() {
  _stop_pf_on_port "$PROM_PORT"
  _stop_pf_on_port "$LOKI_PORT"

  if ! kubectl get svc/prometheus -n "$NS" >/dev/null 2>&1; then
    echo "ERROR: svc/prometheus not found in namespace $NS — run: make deploy-observability"
    return 1
  fi

  kubectl port-forward "svc/prometheus" -n "$NS" "${PROM_PORT}:9090" >/tmp/pf-prometheus.log 2>&1 &
  kubectl port-forward "svc/loki"       -n "$NS" "${LOKI_PORT}:3100" >/tmp/pf-loki.log 2>&1 &
  sleep 2
}

_health_ok() {
  curl -sf "http://localhost:${PROM_PORT}/-/healthy" >/dev/null 2>&1 &&
    curl -sf "http://localhost:${LOKI_PORT}/ready" >/dev/null 2>&1
}

_wait_ready() {
  local i
  for i in 1 2 3 4 5 6 7 8; do
    if _health_ok; then
      _log "Prometheus http://localhost:${PROM_PORT} ✓"
      _log "Loki       http://localhost:${LOKI_PORT} ✓"
      return 0
    fi
    sleep 1
  done
  echo "WARN: health check failed — see /tmp/pf-prometheus.log /tmp/pf-loki.log"
  return 1
}

_ensure_once() {
  if ! _minikube_ok; then
    echo "ERROR: minikube is not running — run: minikube start"
    return 1
  fi

  if _health_ok && _pf_alive "$PROM_PORT" && _pf_alive "$LOKI_PORT"; then
    _log "Port-forwards already healthy (:${PROM_PORT}, :${LOKI_PORT})"
    return 0
  fi

  if _health_ok; then
    _log "Port-forwards healthy (:${PROM_PORT}, :${LOKI_PORT})"
    return 0
  fi

  _log "Ensuring observability port-forwards (:${PROM_PORT}, :${LOKI_PORT})"
  _start_pfs
  _wait_ready
}

_loop_daemon() {
  local check_interval=10
  _log "Port-forward watchdog — checking every ${check_interval}s (Ctrl+C to stop)"
  while true; do
    if ! kubectl cluster-info >/dev/null 2>&1; then
      echo "WARN: minikube down — retrying in 15s"
      sleep 15
      continue
    fi
    if ! _health_ok; then
      _log "Stale or missing port-forward — restarting"
      _start_pfs || true
      _wait_ready || true
    fi
    sleep "$check_interval"
  done
}

case "$LOOP" in
  --loop) _loop_daemon ;;
  *)      _ensure_once ;;
esac

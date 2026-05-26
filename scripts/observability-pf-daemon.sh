#!/usr/bin/env bash
# Supervised observability port-forward daemon for hybrid Minikube dev.
# Auto-restarts kubectl port-forwards after Mac sleep, minikube restart, or PF crash.
#
# Usage:
#   scripts/observability-pf-daemon.sh start   # background watchdog + initial PF
#   scripts/observability-pf-daemon.sh stop    # stop watchdog (leaves active PFs)
#   scripts/observability-pf-daemon.sh status  # daemon + PF health
#   scripts/observability-pf-daemon.sh restart
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="${ROOT}/.observability-pf.pid"
LOGFILE="/tmp/observability-pf-daemon.log"
ENSURE="${ROOT}/scripts/ensure-port-forwards.sh"

_log() { echo "==> $*"; }

_running() {
  [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

start() {
  chmod +x "$ENSURE"
  if _running; then
    _log "Observability PF daemon already running (pid $(cat "$PIDFILE"))"
    "$ENSURE" || true
    return 0
  fi

  _log "Starting observability PF daemon (log: $LOGFILE)"
  nohup "$ENSURE" --loop >>"$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  sleep 1

  if ! _running; then
    echo "ERROR: daemon failed to start — see $LOGFILE"
    rm -f "$PIDFILE"
    return 1
  fi

  _log "Daemon pid $(cat "$PIDFILE") — ensuring initial port-forwards"
  "$ENSURE" || true
  _log "Daemon running — port-forwards auto-restart every 30s when stale"
}

stop() {
  if _running; then
    _log "Stopping observability PF daemon (pid $(cat "$PIDFILE"))"
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$PIDFILE"
  _log "Daemon stopped"
}

status() {
  if _running; then
    echo "daemon: running (pid $(cat "$PIDFILE"))"
  else
    echo "daemon: stopped"
  fi
  if [[ -x "$ENSURE" ]]; then
    if "$ENSURE"; then
      echo "port-forwards: healthy"
      return 0
    fi
    echo "port-forwards: unhealthy"
    return 1
  fi
  echo "port-forwards: ensure script missing"
  return 1
}

case "${1:-start}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  status ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac

#!/usr/bin/env bash
# Post-deploy smoke checks for Minikube stack (CI-friendly).
#
# Environment:
#   BACKEND_HEALTH_URL     e.g. http://localhost:8080/health (hybrid host backend)
#   STRICT_BACKEND=true    Fail if backend health check is unreachable
#   CHROMA_HEALTH_URL      Default: in-cluster port-forward probe
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STRICT_BACKEND="${STRICT_BACKEND:-false}"
BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://localhost:8080/health}"
FAIL=0

pass() { echo "  ✓ $*"; }
fail() { echo "  ✗ $*"; FAIL=1; }
warn() { echo "  ⚠ $*"; }

check_namespace_pods_ready() {
  local ns="$1"
  echo "=== Namespace: $ns ==="
  if ! kubectl get namespace "$ns" >/dev/null 2>&1; then
    fail "namespace $ns missing"
    return
  fi
  local not_ready
  not_ready="$(kubectl get pods -n "$ns" --no-headers 2>/dev/null \
    | awk '$2 !~ /^[0-9]+\/[0-9]+$/ || $3 != "Running" {print}' || true)"
  if [[ -n "$not_ready" ]]; then
    fail "pods not ready in $ns"
    echo "$not_ready"
  else
    pass "all pods running in $ns"
  fi
}

check_synthetic_nodeports() {
  echo "=== Synthetic demo apps (NodePort) ==="
  local ip
  ip="$(minikube ip 2>/dev/null || true)"
  if [[ -z "$ip" ]]; then
    fail "minikube ip unavailable"
    return
  fi
  curl -sf --max-time 10 "http://${ip}:30500/health" >/dev/null && pass "auth-service :30500" || fail "auth-service :30500"
  curl -sf --max-time 10 "http://${ip}:30800/health" >/dev/null && pass "order-service :30800" || fail "order-service :30800"
  curl -sf --max-time 10 "http://${ip}:30510/health" >/dev/null && pass "payment-api :30510" || fail "payment-api :30510"
  curl -sf --max-time 10 "http://${ip}:30520/health" >/dev/null && pass "inventory-service :30520" || fail "inventory-service :30520"
  curl -sf --max-time 10 "http://${ip}:30530/health" >/dev/null && pass "notification-service :30530" || fail "notification-service :30530"
  curl -sf --max-time 10 "http://${ip}:30540/health" >/dev/null && pass "gateway-api :30540" || fail "gateway-api :30540"
  curl -sf --max-time 10 "http://${ip}:30550/health" >/dev/null && pass "user-profile-service :30550" || fail "user-profile-service :30550"
}

check_chromadb() {
  echo "=== ChromaDB (in-cluster) ==="
  if [[ -n "${CHROMA_HEALTH_URL:-}" ]]; then
    curl -sf --max-time 10 "$CHROMA_HEALTH_URL" >/dev/null && pass "ChromaDB $CHROMA_HEALTH_URL" || fail "ChromaDB $CHROMA_HEALTH_URL"
    return
  fi
  local pf_log pf_pid
  pf_log="$(mktemp)"
  kubectl port-forward svc/chromadb -n sre-ai 18000:8000 >"$pf_log" 2>&1 &
  pf_pid=$!
  sleep 2
  if curl -sf --max-time 10 http://localhost:18000/api/v1/heartbeat >/dev/null; then
    pass "ChromaDB heartbeat via port-forward"
  else
    fail "ChromaDB heartbeat via port-forward"
  fi
  kill "$pf_pid" 2>/dev/null || true
  wait "$pf_pid" 2>/dev/null || true
  rm -f "$pf_log"
}

check_redis() {
  echo "=== Redis (in-cluster) ==="
  kubectl exec deploy/sre-ai-redis -- redis-cli ping 2>/dev/null | grep -q PONG && pass "redis PING" || fail "redis PING"
}

check_kafka_topics() {
  echo "=== Kafka topics ==="
  kubectl exec -n kafka deploy/kafka -- bash -c \
    '/opt/bitnami/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092' 2>/dev/null \
    | grep -q 'sre\.' && pass "SRE topics present" || fail "SRE topics missing"
}

check_backend() {
  echo "=== Backend API ==="
  if curl -sf --max-time 5 "$BACKEND_HEALTH_URL" >/dev/null; then
    pass "backend health at $BACKEND_HEALTH_URL"
    return
  fi
  if kubectl get deployment sre-ai-backend -n sre-ai >/dev/null 2>&1; then
    local pf_log pf_pid
    pf_log="$(mktemp)"
    kubectl port-forward svc/sre-ai-backend -n sre-ai 18080:8080 >"$pf_log" 2>&1 &
    pf_pid=$!
    sleep 2
    if curl -sf --max-time 10 http://localhost:18080/health >/dev/null; then
      pass "in-cluster backend /health"
      kill "$pf_pid" 2>/dev/null || true
      wait "$pf_pid" 2>/dev/null || true
      rm -f "$pf_log"
      return
    fi
    kill "$pf_pid" 2>/dev/null || true
    wait "$pf_pid" 2>/dev/null || true
    rm -f "$pf_log"
  fi
  if [[ "$STRICT_BACKEND" == "true" ]]; then
    fail "backend unreachable at $BACKEND_HEALTH_URL (hybrid: run make start-backend)"
  else
    warn "backend offline (expected in hybrid dev — run make start-backend on host)"
  fi
}

main() {
  cd "$ROOT"
  echo "Running Minikube smoke tests..."
  echo ""

  check_namespace_pods_ready observability
  check_namespace_pods_ready kafka
  check_namespace_pods_ready sre-ai
  if kubectl get namespace synthetic >/dev/null 2>&1; then
    check_namespace_pods_ready synthetic
    check_synthetic_nodeports
  else
    warn "synthetic namespace absent (SKIP_SYNTHETIC?)"
  fi

  check_redis
  check_chromadb
  check_kafka_topics
  check_backend

  echo ""
  if [[ "$FAIL" -ne 0 ]]; then
    echo "Smoke tests FAILED"
    exit 1
  fi
  echo "Smoke tests passed"
}

main "$@"

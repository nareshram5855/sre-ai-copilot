#!/usr/bin/env bash
# One-command Minikube deploy for SRE AI Copilot data stack (+ optional in-cluster backend).
#
# Default (hybrid dev): observability, synthetic apps, Kafka, Redis, ChromaDB in Minikube;
# FastAPI backend runs on the host (make start-backend).
#
# Environment:
#   DEPLOY_BACKEND=true     Build backend image in Minikube and apply .github/cd/kubernetes/backend-deployment.yaml
#   BACKEND_IMAGE           Override image tag (default: sre-ai-backend:local)
#   MINIKUBE_CPUS           Default: 4
#   MINIKUBE_MEMORY         Default: 8192
#   SKIP_SYNTHETIC=true     Skip demo app build/deploy (faster CI)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
K8S_DIR="$ROOT/infrastructure/k8s"
OBS_DIR="$K8S_DIR/observability"
MINIKUBE_CPUS="${MINIKUBE_CPUS:-4}"
MINIKUBE_MEMORY="${MINIKUBE_MEMORY:-8192}"
DEPLOY_BACKEND="${DEPLOY_BACKEND:-false}"
BACKEND_IMAGE="${BACKEND_IMAGE:-sre-ai-backend:local}"
SKIP_SYNTHETIC="${SKIP_SYNTHETIC:-false}"

log() { echo "==> $*"; }

ensure_minikube() {
  log "Ensuring Minikube is running..."
  if ! minikube status >/dev/null 2>&1; then
    echo "    Starting minikube (cpus=${MINIKUBE_CPUS}, memory=${MINIKUBE_MEMORY})..."
    minikube start --cpus="${MINIKUBE_CPUS}" --memory="${MINIKUBE_MEMORY}" || minikube start
  fi
  kubectl cluster-info >/dev/null
  echo "    Minikube IP: $(minikube ip)"
}

wait_rollout() {
  local kind="$1" name="$2" namespace="$3" timeout="${4:-180s}"
  kubectl rollout status "$kind/$name" -n "$namespace" --timeout="$timeout"
}

deploy_observability() {
  log "Deploying observability stack..."
  bash "$OBS_DIR/install.sh"
}

deploy_synthetic() {
  if [[ "$SKIP_SYNTHETIC" == "true" ]]; then
    log "Skipping synthetic demo apps (SKIP_SYNTHETIC=true)"
    return
  fi
  log "Deploying synthetic demo apps..."
  bash "$OBS_DIR/deploy-synthetic.sh"
}

deploy_kafka() {
  log "Deploying Kafka..."
  bash "$K8S_DIR/kafka/install.sh"
}

deploy_redis() {
  log "Deploying Redis..."
  kubectl apply -f "$K8S_DIR/redis.yaml"
  wait_rollout deployment sre-ai-redis default
}

deploy_chromadb() {
  log "Deploying ChromaDB..."
  kubectl apply -f "$K8S_DIR/chromadb.yaml"
  wait_rollout deployment chromadb sre-ai
}

deploy_backend_in_cluster() {
  if [[ "$DEPLOY_BACKEND" != "true" ]]; then
    log "Hybrid mode: backend not deployed in cluster (run 'make start-backend' on host)"
    return
  fi

  log "Building backend image inside Minikube Docker (${BACKEND_IMAGE})..."
  eval "$(minikube docker-env)"
  docker build -t "$BACKEND_IMAGE" -f "$ROOT/Dockerfile" "$ROOT"

  log "Applying backend deployment..."
  local rendered
  rendered="$(mktemp)"
  sed "s|ghcr.io/OWNER/REPO:TAG|${BACKEND_IMAGE}|g" \
    "$ROOT/.github/cd/kubernetes/backend-deployment.yaml" > "$rendered"
  kubectl apply -f "$rendered"
  rm -f "$rendered"

  kubectl -n sre-ai set image "deployment/sre-ai-backend" "backend=${BACKEND_IMAGE}" --record=false 2>/dev/null || true
  kubectl -n sre-ai patch deployment sre-ai-backend --type=json \
    -p='[{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]' \
    >/dev/null
  wait_rollout deployment sre-ai-backend sre-ai
}

main() {
  cd "$ROOT"
  ensure_minikube
  deploy_observability
  deploy_synthetic
  deploy_kafka
  deploy_redis
  deploy_chromadb
  deploy_backend_in_cluster

  echo ""
  echo "✓ Minikube deploy complete."
  echo ""
  echo "  Hybrid dev (default):"
  echo "    make observability-port-forward   # Prometheus :19090, Loki :13100"
  echo "    make kafka-port-forward           # Kafka :9092"
  echo "    make start-backend                # FastAPI :8080 on host"
  echo ""
  echo "  Smoke test:"
  echo "    bash infrastructure/k8s/smoke-test.sh"
  echo ""
}

main "$@"

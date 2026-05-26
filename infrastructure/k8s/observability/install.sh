#!/usr/bin/env bash
# Deploy Prometheus, Loki, Promtail, and OTel Collector to Minikube.
# Canonical manifests live in infrastructure/k8s/observability/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
DIR="$(cd "$(dirname "$0")" && pwd)"
NAMESPACE=observability

echo "==> Ensuring Minikube is running..."
if ! minikube status >/dev/null 2>&1; then
  echo "    Starting minikube (this may take a minute)..."
  minikube start --cpus=4 --memory=8192 || minikube start
fi

echo "==> Creating namespace: $NAMESPACE"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

echo "==> Deploying observability stack"
kubectl apply -f "$DIR/prometheus.yaml"
kubectl apply -f "$DIR/loki.yaml"
kubectl apply -f "$DIR/promtail.yaml"
kubectl apply -f "$DIR/otel-collector.yaml"

echo "==> Waiting for rollouts..."
kubectl rollout status deployment/prometheus      -n "$NAMESPACE" --timeout=180s
kubectl rollout status deployment/loki            -n "$NAMESPACE" --timeout=180s
kubectl rollout status deployment/otel-collector  -n "$NAMESPACE" --timeout=180s
kubectl rollout status daemonset/promtail         -n "$NAMESPACE" --timeout=180s

echo ""
echo "==> Observability stack ready in namespace: $NAMESPACE"
echo ""
echo "  Port-forwards (host backend — run in separate terminals or use make):"
echo "    make observability-port-forward"
echo ""
echo "  Health checks:"
echo "    make observability-status"
echo ""
echo "  Demo apps (metrics + logs for Observe page):"
echo "    make deploy-synthetic"
echo ""

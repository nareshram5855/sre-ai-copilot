#!/usr/bin/env bash
# Build and deploy synthetic demo services for SRE AI Copilot testing.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
NAMESPACE=synthetic
SYNTHETIC_DIR="$ROOT/infrastructure/k8s/synthetic"

echo "==> Ensuring Minikube is running..."
if ! minikube status >/dev/null 2>&1; then
  minikube start --cpus=4 --memory=8192 || minikube start
fi

echo "==> Creating namespace: $NAMESPACE"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

echo "==> Building demo images inside Minikube Docker..."
eval "$(minikube docker-env)"
docker build -t auth-service:latest   "$ROOT/synthetic/python-app"
docker build -t order-service:latest  "$ROOT/synthetic/java-app"
docker build -t demo-service:latest   "$ROOT/synthetic/demo-service"

echo "==> Deploying demo services"
kubectl apply -f "$ROOT/synthetic/python-app/k8s/deployment.yaml"
kubectl apply -f "$ROOT/synthetic/java-app/k8s/deployment.yaml"
for svc_dir in payment-api inventory-service notification-service gateway-api user-profile-service; do
  kubectl apply -f "$SYNTHETIC_DIR/$svc_dir/deployment.yaml"
done

echo "==> Waiting for rollouts..."
DEPLOYS=(
  auth-service order-service
  payment-api inventory-service notification-service gateway-api user-profile-service
)
for dep in "${DEPLOYS[@]}"; do
  kubectl rollout status "deployment/$dep" -n "$NAMESPACE" --timeout=180s
done

MINIKUBE_IP="$(minikube ip)"
echo ""
echo "==> Synthetic demo apps ready (namespace: $NAMESPACE)"
echo "    auth-service:           http://${MINIKUBE_IP}:30500/health"
echo "    order-service:          http://${MINIKUBE_IP}:30800/health"
echo "    payment-api:            http://${MINIKUBE_IP}:30510/health"
echo "    inventory-service:      http://${MINIKUBE_IP}:30520/health"
echo "    notification-service:   http://${MINIKUBE_IP}:30530/health"
echo "    gateway-api:            http://${MINIKUBE_IP}:30540/health"
echo "    user-profile-service:   http://${MINIKUBE_IP}:30550/health"
echo ""
echo "    Trigger example: curl -X POST http://${MINIKUBE_IP}:30510/simulate/high_error_rate"
echo ""

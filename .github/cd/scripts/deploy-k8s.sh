#!/usr/bin/env bash
# Render and apply Kubernetes manifests for CD workflows.
set -euo pipefail

IMAGE="${1:?image required, e.g. ghcr.io/org/repo:tag}"
NAMESPACE="${K8S_NAMESPACE:-sre-ai}"
MANIFEST=".github/cd/kubernetes/backend-deployment.yaml"
RENDERED="$(mktemp)"

mkdir -p "$(dirname "$RENDERED")"

sed "s|ghcr.io/OWNER/REPO:TAG|${IMAGE}|g" "$MANIFEST" > "$RENDERED"

echo "→ Applying ${RENDERED} to namespace ${NAMESPACE}"
kubectl apply -f "$RENDERED"
kubectl -n "$NAMESPACE" rollout status "deployment/${K8S_DEPLOYMENT:-sre-ai-backend}" --timeout=180s

echo "✓ Deployed ${IMAGE}"

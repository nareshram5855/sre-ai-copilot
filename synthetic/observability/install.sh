#!/usr/bin/env bash
# Deploy the full observability stack to Minikube.
# Components: Prometheus, Loki, Promtail, OTel Collector, Grafana (optional)
set -euo pipefail

NAMESPACE=observability

echo "==> Creating namespace: $NAMESPACE"
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# ── RBAC for Prometheus pod discovery ─────────────────────────────────────────
echo "==> Applying RBAC for Prometheus"
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus
  namespace: observability
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus
rules:
  - apiGroups: [""]
    resources: [nodes, nodes/proxy, services, endpoints, pods]
    verbs: [get, list, watch]
  - nonResourceURLs: [/metrics]
    verbs: [get]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: prometheus
subjects:
  - kind: ServiceAccount
    name: prometheus
    namespace: observability
EOF

# ── Prometheus ─────────────────────────────────────────────────────────────────
echo "==> Deploying Prometheus"
kubectl apply -f prometheus.yaml

# ── Loki (single-binary, in-memory, no S3 needed) ─────────────────────────────
echo "==> Deploying Loki"
kubectl apply -f loki.yaml

# ── Promtail (DaemonSet — ships pod logs to Loki) ─────────────────────────────
echo "==> Deploying Promtail"
kubectl apply -f promtail.yaml

# ── OpenTelemetry Collector ────────────────────────────────────────────────────
echo "==> Deploying OTel Collector"
kubectl apply -f otel-collector.yaml

echo ""
echo "==> Waiting for rollouts..."
kubectl rollout status deployment/prometheus    -n $NAMESPACE --timeout=120s
kubectl rollout status deployment/loki         -n $NAMESPACE --timeout=120s
kubectl rollout status deployment/otel-collector -n $NAMESPACE --timeout=120s

echo ""
echo "==> Observability stack ready!"
echo "    Prometheus:    kubectl port-forward svc/prometheus    -n observability 9090:9090"
echo "    Loki:          kubectl port-forward svc/loki          -n observability 3100:3100"
echo "    OTel Collector: endpoint otel-collector.observability:4317"

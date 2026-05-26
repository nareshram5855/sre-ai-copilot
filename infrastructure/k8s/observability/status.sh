#!/usr/bin/env bash
# Health-check observability stack (cluster + localhost port-forwards).
set -euo pipefail

PROM_PORT="${PROMETHEUS_LOCAL_PORT:-19090}"
LOKI_PORT="${LOKI_LOCAL_PORT:-13100}"
NS=observability

echo "=== Kubernetes ($NS namespace) ==="
kubectl get pods,svc -n "$NS" 2>/dev/null || echo "  namespace not deployed — run: make deploy-observability"

echo ""
echo "=== Local port-forwards ==="
curl -sf "http://localhost:${PROM_PORT}/-/healthy" >/dev/null && echo "  Prometheus (:${PROM_PORT}) healthy" || echo "  Prometheus (:${PROM_PORT}) offline — run: make observability-port-forward"
curl -sf "http://localhost:${LOKI_PORT}/ready"     >/dev/null && echo "  Loki (:${LOKI_PORT}) ready"       || echo "  Loki (:${LOKI_PORT}) offline — run: make observability-port-forward"

echo ""
echo "=== Synthetic demo apps ==="
kubectl get pods -n synthetic -l 'app in (auth-service,order-service)' 2>/dev/null || echo "  not deployed — run: make deploy-synthetic"

echo ""
echo "=== Known cluster noise (safe to ignore for SRE demo) ==="
echo "  monitoring/*     duplicate kube-prometheus-stack (use observability/ stack instead)"
echo "  demo/oom-demo    intentional OOM demo pod — CrashLoopBackOff expected"
echo "  kube-system/*    etcd/scheduler alerts — common minikube flakiness after sleep"

echo ""
echo "=== Backend API (requires backend on :8080) ==="
curl -sf http://localhost:8080/api/v1/observability/stack 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  backend offline or stack unreachable"

# Demo Scenarios — Synthetic Namespace

Production-realistic failure modes for SRE AI Copilot testing (Observe, anomaly watch, triage, execution).

**Namespace:** `synthetic`  
**Trigger pattern:** `curl -X POST http://$(minikube ip):<port>/simulate/<mode>`  
**Reset:** `curl -X POST http://$(minikube ip):<port>/simulate/normal`

| Service | Use case | How to trigger | Expected Observe behavior |
|---------|----------|----------------|---------------------------|
| **auth-service** (:30500) | Auth DB pool exhaustion, 5xx cascade | `POST /simulate/high_error_rate` or `connection_exhaust` | `HIGH_ERROR_RATE` critical, `POOL_EXHAUSTION`, ERROR logs in Loki (DatabasePool) |
| **order-service** (:30800) | JVM NPE, deadlock, GC pressure | `POST /simulate/npe` or `deadlock` | `HIGH_ERROR_RATE` or `JVM_HIGH_HEAP`, Java ERROR logs, JVM metrics elevated |
| **payment-api** (:30510) | Intermittent 5xx / payment processor failures | `POST /simulate/high_error_rate` | `HIGH_ERROR_RATE` ≥ 0.5/s critical, 500/502/503 in Loki (PaymentController) |
| **inventory-service** (:30520) | Slow stock queries / P99 latency spikes | `POST /simulate/slow_response` | `HIGH_LATENCY` critical (P99 ≥ 2000ms), WARN logs with high `latency_ms` |
| **notification-service** (:30530) | Memory leak → OOM risk | `POST /simulate/memory_leak` | `HIGH_HEAP` warning → critical, heap gauge climbing, OOMKilled possible at 128Mi limit |
| **gateway-api** (:30540) | Rate limiting (429) + auth dependency | `POST /simulate/rate_limit` (+ optional auth failure) | 429 errors, `rate_limit_exceeded_total` up; 502 if auth-service unhealthy |
| **user-profile-service** (:30550) | Disk/log volume spike | `POST /simulate/log_flood` | Burst of ERROR logs in Loki (disk quota, log rotation); metrics may stay green |

## Combined / cascade scenarios

1. **Gateway + auth cascade:** Trigger `auth-service` `high_error_rate`, then `gateway-api` `rate_limit`. Gateway logs show upstream auth failures (502).
2. **Payment incident:** `payment-api` `high_error_rate` → SLO burn rate critical on `/api/v1/observability/slo`.
3. **Inventory latency:** `inventory-service` `slow_response` → Anomaly Watch shows `HIGH_LATENCY` without high error rate.

## API verification

```bash
# All services (Prometheus auto-discovery)
curl -s http://localhost:8080/api/v1/observability/services | python3 -m json.tool

# Anomaly watch dashboard feed
curl -s 'http://localhost:8080/api/v1/observability/watch?minutes=10' | python3 -m json.tool

# Trigger via backend
curl -s -X POST http://localhost:8080/api/v1/observability/trigger-issue \
  -H 'Content-Type: application/json' \
  -d '{"service":"payment-api","issue":"high_error_rate"}'
```

## Prometheus alerts (synthetic.demo group)

| Alert | Fires when |
|-------|------------|
| SyntheticHighErrorRate | `http_errors_total` rate > 0.5/s for 2m |
| SyntheticHighLatency | P99 latency > 2000ms for 2m |
| SyntheticHighHeap | `memory_heap_bytes` > 100MB for 1m |
| SyntheticRateLimitStorm | `rate_limit_exceeded_total` rate > 1/s for 1m |

## Deploy

```bash
bash infrastructure/k8s/observability/deploy-synthetic.sh
# or full stack:
bash infrastructure/k8s/deploy-all.sh
```

# Runbook: Database Connection Pool Exhaustion

**Alert:** DBConnectionPoolExhausted / HighDBLatency
**Severity:** P2 (P1 if token service or auth DB)
**Owner:** IAM Platform / SRE

## Diagnosis Steps

### Step 1 — Confirm connection pool state
```bash
# Check app-level pool metrics (Spring Boot Actuator)
kubectl exec -n <namespace> <pod-name> -- \
  curl -s http://localhost:8081/actuator/metrics/hikaricp.connections.active

# For non-Spring apps, check env vars for pool config
kubectl describe deployment <deployment-name> -n <namespace> | grep -i "pool\|conn\|db_max"
```

### Step 2 — Check PostgreSQL directly
```bash
kubectl exec -n <namespace> deploy/<postgres-deployment> -- \
  psql -U <admin-user> -c \
  "SELECT application_name, state, count(*) 
   FROM pg_stat_activity 
   GROUP BY application_name, state 
   ORDER BY count DESC;"

# Check max_connections setting
kubectl exec -n <namespace> deploy/<postgres-deployment> -- \
  psql -U <admin-user> -c "SHOW max_connections;"
```

### Step 3 — Identify the connection hog
```bash
kubectl exec -n <namespace> deploy/<postgres-deployment> -- \
  psql -U <admin-user> -c \
  "SELECT application_name, usename, count(*), max(now() - state_change) as oldest
   FROM pg_stat_activity
   WHERE state != 'idle'
   GROUP BY application_name, usename
   ORDER BY count DESC LIMIT 10;"
```

## Fixes

### Emergency: kill the connection hog
```bash
# Scale to 0 immediately
kubectl scale deployment <offending-deployment> -n <namespace> --replicas=0

# Or if you know specific PIDs
kubectl exec -n <namespace> deploy/<postgres-deployment> -- \
  psql -U <admin-user> -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name='<app>';"
```

### Reduce pool size on the problematic service
```bash
kubectl set env deployment/<deployment-name> -n <namespace> \
  SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE=20

# Or via Helm values update and ArgoCD sync
```

### Long-term: add PgBouncer
```bash
# Deploy PgBouncer as a sidecar or separate deployment
# All app connections → PgBouncer → PostgreSQL
# PgBouncer config: pool_mode=transaction, max_client_conn=500, default_pool_size=25
kubectl apply -f infrastructure/helm/pgbouncer/
```

## Escalation
- Token service DB affected: P1 immediately, SLO breach within minutes
- > 80% max_connections hit: escalate for emergency PgBouncer deploy
- Always update ServiceNow with connection count graph from Grafana

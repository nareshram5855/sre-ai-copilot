# Incident: Database Connection Pool Exhausted — IAM Token Store
Date: 2024-07-22
Severity: P2
Duration: 55 minutes
Service: iam-token-service
Team: IAM Platform

## Summary
Token validation latency spiked to 8s (SLO: 200ms) due to exhausted PostgreSQL
connection pool on the IAM token store. OAuth2 token introspection endpoints
returned 503 for approximately 35% of requests.

## Root Cause
A new batch job (compliance-audit-export) was deployed at 14:00 with max_connections=100,
stealing connections from the token service pool (also max=100). Total connections
exceeded PostgreSQL's max_connections=150 limit.

## Timeline
- 14:15: Latency alert fired — p99 token validation > 5000ms
- 14:18: On-call paged
- 14:25: Identified connection pool exhaustion via pg_stat_activity query
- 14:35: Batch job scaled to 0 replicas as immediate mitigation
- 14:52: Token service pool reduced to 80, batch job redeployed with pool=20
- 15:10: Permanent fix: PgBouncer connection pooler added

## Commands Run
```bash
# Check PostgreSQL connections
kubectl exec -n iam deploy/iam-postgres -- psql -U iam_admin -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Identify which app is holding connections
kubectl exec -n iam deploy/iam-postgres -- psql -U iam_admin -c \
  "SELECT application_name, count(*) FROM pg_stat_activity GROUP BY application_name;"

# Emergency: scale batch job to 0
kubectl scale deployment compliance-audit-export -n iam --replicas=0

# Verify pool recovery
kubectl exec -n iam deploy/iam-token-service -- \
  curl -s http://localhost:8081/actuator/metrics/hikaricp.connections.active
```

## Prevention
- PgBouncer added as connection pooler — all apps connect through it
- max_connections per app enforced via PgBouncer pool_size limits
- Connection count added to SLO alerting dashboard

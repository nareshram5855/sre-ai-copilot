# Incident: IAM Token Service — Database Connection Pool Exhausted
Date: 2024-08-21
Severity: P1
Duration: 34 minutes
Service: iam-token-service
Team: IAM Platform + SRE

## Summary
The IAM token service stopped issuing OAuth tokens for 34 minutes due to complete
exhaustion of the PostgreSQL connection pool. All downstream services using
machine-to-machine auth tokens were affected, including the payment gateway,
audit logging pipeline, and internal API gateway.

## Root Cause
A recent code change increased the thread pool size from 50 to 200 threads without
a corresponding increase in the database connection pool (still capped at 50).
Under load, 200 threads competed for 50 connections. Connection wait timeouts
cascaded into HTTP 503s on the token endpoint.

## Contributing Factors
1. No load test ran against the new thread pool configuration before deploy
2. DB connection pool exhaustion metric (`hikari.connections.pending`) had no alert
3. The deploy was pushed on a Friday afternoon (low SRE coverage)

## Impact
- 34 minutes of token issuance failure
- ~15,000 API requests failed with 503 (payment, audit, API gateway)
- No data loss — token DB was healthy throughout
- Regulatory notification required (PCI-DSS: payment flow disruption > 15 min)

## Timeline
- 14:31: Deploy of iam-token-service v2.3.1 (thread pool 50→200)
- 14:44: First 503 errors appear in Datadog APM
- 14:47: Alert fires — HTTP error rate > 5% on iam-token-service
- 14:49: On-call engineer paged
- 14:55: Root cause identified (Hikari pool exhaustion in logs)
- 15:00: Connection pool bumped to 200 via env var, rolling restart triggered
- 15:05: Token issuance restored, error rate returns to baseline

## Commands Run
```bash
# Identify error pattern
kubectl logs -n iam deployment/iam-token-service --tail=500 | \
  grep -E 'HikariPool|timeout|exhausted'

# Check DB connection count
kubectl exec -n iam deployment/iam-token-service -- \
  curl -s localhost:8081/actuator/metrics/hikari.connections.active

# Apply fix — increase pool size without full redeploy
kubectl set env deployment/iam-token-service -n iam \
  SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE=200

# Monitor rollout
kubectl rollout status deployment/iam-token-service -n iam
```

## Prevention
1. Add alert on `hikari.connections.pending > 10` for 2 minutes
2. Load test all database-bound services before thread pool changes
3. Deploy freeze Fridays after 14:00 for P1 services
4. Add `db_connection_pool_max` to the service's Helm values (not env var)

## Action Items
- IAM Platform: Add Hikari metrics alert by 2024-08-28
- SRE: Add connection pool size to service health endpoint by 2024-09-04
- Engineering: Load test iam-token-service at 200 threads before next deploy

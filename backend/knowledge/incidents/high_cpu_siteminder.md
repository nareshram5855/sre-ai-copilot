# Incident: High CPU — SiteMinder Policy Server
Date: 2024-05-08
Severity: P1
Duration: 22 minutes
Service: siteminder-policy-server
Team: CISO Platform

## Summary
SiteMinder policy server CPU spiked to 98% across all pods during a mass
re-authentication event triggered by an expired session cookie config push.
All internal apps using SiteMinder for SSO were unreachable.

## Root Cause
A Kubernetes ConfigMap update to `sm-session-cookie-ttl` was applied without
a rolling restart. The old policy server processes cached the stale config,
causing every session validation to fail → client retries → thundering herd → CPU saturation.

## Timeline
- 10:02: ConfigMap updated via ArgoCD sync
- 10:05: CPU alert fired — 98% across 6 policy server pods
- 10:06: P1 declared, incident bridge opened
- 10:11: Identified ConfigMap as root cause via git diff of ArgoCD sync
- 10:18: Rolled back ConfigMap, triggered rolling restart
- 10:24: CPU normalized, sessions re-established

## Commands Run
```bash
# Identify CPU spike
kubectl top pods -n ciso --sort-by=cpu

# Check recent config changes
kubectl describe configmap sm-session-config -n ciso
kubectl get events -n ciso --sort-by='.lastTimestamp' | tail -20

# Rollback
kubectl rollout undo deployment/siteminder-policy-server -n ciso
kubectl rollout status deployment/siteminder-policy-server -n ciso

# Verify
kubectl top pods -n ciso -l app=siteminder-policy-server
```

## Prevention
- ConfigMap changes now require a staged rollout with canary (5% pods first)
- Added post-sync health check hook in ArgoCD for policy server
- Alert threshold lowered from 90% to 75% CPU for policy server pods

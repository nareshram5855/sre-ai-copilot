# Incident: Pod CrashLoopBackOff — Auth Service
Date: 2024-03-12
Severity: P2
Duration: 38 minutes
Service: ping-identity-auth
Team: IAM Platform

## Summary
Ping Identity authentication pods entered CrashLoopBackOff state during morning
traffic ramp-up. 40% of SSO login attempts failed for ~30 minutes.

## Root Cause
JVM heap exhausted (OOMKilled). Memory limit was set to 512Mi but PingFederate
requires 768Mi minimum under production token issuance load.

## Timeline
- 08:14: Alert fired — KubePodCrashLooping, ping-identity-auth, restarts=6
- 08:17: On-call paged via PagerDuty
- 08:22: Engineer ran `kubectl describe pod` — confirmed OOMKilled exit code 137
- 08:35: Memory limit patched to 1Gi via kubectl set resources
- 08:52: All pods stabilized, error rate returned to baseline

## Commands Run
```bash
kubectl get pods -n iam -l app=ping-identity-auth
kubectl describe pod ping-identity-auth-xxx -n iam
kubectl logs ping-identity-auth-xxx -n iam --previous | tail -50
kubectl set resources deployment ping-identity-auth -n iam \
  -c ping-identity-auth --limits=memory=1Gi --requests=memory=768Mi
kubectl rollout status deployment/ping-identity-auth -n iam
```

## Prevention
- Added VPA (VerticalPodAutoscaler) targeting p95 memory usage
- Added OOMKilled alert rule in Prometheus with 5m window
- Updated Helm values to 1.5Gi limit for auth services

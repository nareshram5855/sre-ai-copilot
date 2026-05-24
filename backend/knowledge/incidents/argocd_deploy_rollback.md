# Incident: Broken ArgoCD Deploy — auth-gateway Rollback
Date: 2024-10-03
Severity: P2
Duration: 18 minutes
Service: auth-gateway
Team: CISO Platform + SRE

## Summary
A Helm chart upgrade to auth-gateway introduced an invalid NGINX ingress annotation
that caused the ingress controller to reject all routing rules. External OAuth
redirect URIs stopped resolving for 18 minutes, blocking SSO login for all
browser-based applications.

## Root Cause
The Helm chart upgrade changed the annotation prefix from
`nginx.ingress.kubernetes.io` to `kubernetes.io/ingress.nginx` (typo in PR).
NGINX ingress controller silently ignored unrecognized annotations, causing
auth redirect rules to disappear from the ingress config.

## Timeline
- 09:14: auth-gateway v1.8.0 deployed via ArgoCD (auto-sync triggered by merged PR)
- 09:17: Users report "redirect_uri mismatch" OAuth errors across Citi internal apps
- 09:19: Alert fires — 5xx error rate on auth-gateway > 10%
- 09:21: On-call identifies ingress annotation typo via `kubectl describe ingress`
- 09:28: Rolled back to v1.7.9 via ArgoCD UI
- 09:32: SSO logins restored

## Commands Run
```bash
# Identify the ingress problem
kubectl describe ingress auth-gateway -n ciso | grep -A 20 "Annotations"
kubectl get events -n ciso --sort-by='.lastTimestamp' | tail -20

# Check NGINX ingress controller logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller --tail=100 | \
  grep -E 'error|warn|auth-gateway'

# Rollback via ArgoCD CLI
argocd app history auth-gateway
argocd app rollback auth-gateway <previous-revision-id>

# Verify ingress restored
kubectl describe ingress auth-gateway -n ciso
curl -I https://auth.internal.example.com/oauth/authorize
```

## Prevention
1. Add ingress annotation validation to CI pipeline (`kubeval`, `kube-score`)
2. Smoke test OAuth redirect after every auth-gateway deploy (canary check)
3. NGINX ingress controller should log a warning for unknown annotations
4. Add auth-gateway to the list of services requiring manual approval for auto-sync

## Detection Gap
3 minutes — users noticed before the alert fired. Alert threshold was 10% error rate;
OAuth errors appear immediately at 100% when ingress is broken. Lower threshold to 1%
for auth-gateway specifically.

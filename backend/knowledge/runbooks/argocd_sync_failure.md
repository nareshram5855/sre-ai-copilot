# Runbook: ArgoCD Sync Failure

**Alert:** ArgoCDAppOutOfSync, ArgoCDSyncFailed
**Severity:** P2 (P1 if blocking a hotfix deploy)
**Owner:** SRE Platform / DevOps
**Estimated time:** 10-15 minutes

## Diagnosis

### Step 1 — Check sync status
```bash
# List all apps and their sync status
argocd app list

# Get detailed status for a specific app
argocd app get <app-name>
argocd app history <app-name>
```

### Step 2 — Read the sync error
```bash
# Show sync operation result
argocd app sync-status <app-name>

# Via kubectl
kubectl get application <app-name> -n argocd -o jsonpath='{.status.operationState.message}'
kubectl describe application <app-name> -n argocd | grep -A 20 "Operation State"
```

### Step 3 — Check ArgoCD controller logs
```bash
kubectl logs -n argocd deployment/argocd-application-controller --tail=100 | \
  grep -E 'error|fail|<app-name>'
kubectl logs -n argocd deployment/argocd-repo-server --tail=50
```

## Common Causes and Fixes

### Cause 1 — Git credentials expired or repo unreachable
```bash
# Check repository connection
argocd repo list
argocd repo get <repo-url>

# Re-add credentials
argocd repo add <repo-url> \
  --username <user> \
  --password <token>
```

### Cause 2 — Invalid Helm values or resource conflict
```bash
# Diff what ArgoCD wants to apply vs live state
argocd app diff <app-name>

# Validate Helm chart locally
helm template <chart-path> -f values.yaml | kubectl apply --dry-run=client -f -
```

### Cause 3 — Resource stuck in Terminating state
```bash
# Find stuck resources
kubectl get all -n <namespace> | grep Terminating

# Force delete (use carefully)
kubectl delete pod <pod-name> -n <namespace> --grace-period=0 --force

# Remove finalizers if stuck
kubectl patch <resource-type> <name> -n <namespace> \
  -p '{"metadata":{"finalizers":null}}' --type=merge
```

### Cause 4 — Sync wave ordering issue
```bash
# Check sync wave annotations
kubectl get applications -n argocd -o yaml | grep -A 5 "sync-wave"

# Force sync with replace strategy (last resort)
argocd app sync <app-name> --replace
```

## Remediation

### Standard sync retry
```bash
# Trigger a manual sync
argocd app sync <app-name>

# Sync with force (overwrites manual changes in cluster)
argocd app sync <app-name> --force

# Sync specific resources only
argocd app sync <app-name> --resource '<group>:<kind>:<name>'
```

### Hard reset (when cluster state is badly diverged)
```bash
# Reset app to Git HEAD
argocd app set <app-name> --sync-policy none   # disable auto-sync temporarily
argocd app terminate-op <app-name>             # cancel any in-progress op
argocd app sync <app-name> --replace           # force reconcile
argocd app set <app-name> --sync-policy automated  # re-enable auto-sync
```

## Escalation
- If sync is blocking a security hotfix: escalate to SRE lead immediately
- If multiple apps failing simultaneously: check ArgoCD controller health first
- Document all manual kubectl changes in the incident ticket

# Runbook: Pod CrashLoopBackOff

**Alert:** KubePodCrashLooping
**Severity:** P2 (P1 if auth/identity service)
**Owner:** IAM Platform / SRE

## Diagnosis Steps

### Step 1 — Identify affected pods
```bash
kubectl get pods -n <namespace> --field-selector=status.phase!=Running
kubectl get pods -n <namespace> | grep -E 'CrashLoop|Error|OOMKilled'
```

### Step 2 — Get restart count and reason
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Last State"
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Events"
```

### Step 3 — Read crash logs
```bash
# Current container logs
kubectl logs <pod-name> -n <namespace> --tail=100

# Previous container logs (before crash)
kubectl logs <pod-name> -n <namespace> --previous --tail=200
```

## Common Causes and Fixes

### OOMKilled (exit code 137)
```bash
# Check current limits
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].resources}'

# Increase memory limit (temporary — update Helm values permanently)
kubectl set resources deployment <deployment-name> -n <namespace> \
  -c <container-name> --limits=memory=<new-limit>Gi --requests=memory=<new-request>Mi

# Verify fix
kubectl rollout status deployment/<deployment-name> -n <namespace>
```

### Missing ConfigMap or Secret (exit code 1 with "no such file")
```bash
# Check mounted volumes
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Volumes"

# List secrets/configmaps in namespace
kubectl get secrets -n <namespace>
kubectl get configmaps -n <namespace>
```

### Liveness Probe Failing (exit code 137, frequent restarts)
```bash
# Check probe config
kubectl get deployment <deployment-name> -n <namespace> -o yaml | grep -A 10 "livenessProbe"

# Temporarily increase failure threshold
kubectl patch deployment <deployment-name> -n <namespace> \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"<container>","livenessProbe":{"failureThreshold":10}}]}}}}'
```

## Escalation
- If auth or identity service: escalate immediately to IAM Platform team
- If restarts > 20: page senior SRE
- Always create a ServiceNow ticket with pod logs attached

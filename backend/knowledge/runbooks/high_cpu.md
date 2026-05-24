# Runbook: High CPU on Kubernetes Pod

**Alert:** KubePodCPUThrottling / NodeCPUHigh
**Severity:** P2 (P1 if affecting auth/policy server)
**Owner:** IAM Platform / SRE

## Diagnosis Steps

### Step 1 — Identify top CPU consumers
```bash
kubectl top pods -n <namespace> --sort-by=cpu
kubectl top nodes
```

### Step 2 — Check if CPU is throttled or running hot
```bash
# Throttling rate (>25% is concerning)
kubectl exec -n <namespace> <pod-name> -- cat /sys/fs/cgroup/cpu/cpu.stat | grep throttled

# Check CPU limits
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].resources.limits.cpu}'
```

### Step 3 — Profile what's consuming CPU
```bash
# For JVM-based services (PingFederate, PingDirectory)
kubectl exec -n <namespace> <pod-name> -- jstack <pid> | grep -A 5 "RUNNABLE"

# For Node/Python services
kubectl exec -n <namespace> <pod-name> -- top -b -n 1
```

## Common Fixes

### Thundering herd / retry storm
```bash
# Scale up replicas to spread load
kubectl scale deployment <deployment-name> -n <namespace> --replicas=<n>

# Check HPA status
kubectl get hpa -n <namespace>
kubectl describe hpa <hpa-name> -n <namespace>
```

### Runaway process
```bash
# Restart the specific pod (graceful)
kubectl delete pod <pod-name> -n <namespace>

# Rolling restart of all pods in deployment
kubectl rollout restart deployment/<deployment-name> -n <namespace>
```

### CPU limits too low (constant throttling)
```bash
# Increase CPU limit — update Helm values file permanently
kubectl set resources deployment <deployment-name> -n <namespace> \
  -c <container-name> --limits=cpu=2000m --requests=cpu=500m
```

### Misconfigured cache causing repeated expensive operations
```bash
# For SiteMinder / Ping — check session cache hit rate
kubectl exec -n ciso <policy-server-pod> -- \
  curl -s http://localhost:8080/metrics | grep cache_hit_rate
```

## Escalation
- CPU > 90% for > 10 minutes on auth service → P1, page on-call lead
- CPU throttling > 50% → SLO risk, escalate to IAM Platform
- All HPA replicas at max → escalate for Karpenter node provisioning check

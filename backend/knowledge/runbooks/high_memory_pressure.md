# Runbook: High Memory Pressure / Node Memory Pressure

**Alert:** NodeMemoryPressure, KubeNodeMemoryPressure
**Severity:** P1 (node eviction imminent)
**Owner:** SRE Platform
**Estimated time:** 15-20 minutes

## Diagnosis

### Step 1 — Identify the pressured node
```bash
kubectl get nodes -o wide
kubectl describe node <node-name> | grep -A 10 "Conditions"
kubectl top nodes --sort-by=memory
```

### Step 2 — Find memory-hungry pods on the node
```bash
kubectl top pods --all-namespaces --sort-by=memory | head -20

# Show all pods on the specific node
kubectl get pods --all-namespaces -o wide --field-selector spec.nodeName=<node-name> \
  | sort -k5 -r | head -20
```

### Step 3 — Check for memory leaks (growing over time)
```bash
# Watch memory trend for a specific pod
watch -n 5 kubectl top pod <pod-name> -n <namespace>

# Check resource requests vs actual usage
kubectl describe node <node-name> | grep -A 30 "Allocated resources"
```

## Immediate Remediation

### Option A — Evict low-priority pods to free memory
```bash
# Identify pods without resource limits (biggest risk)
kubectl get pods --all-namespaces -o json | \
  jq -r '.items[] | select(.spec.containers[].resources.limits == null) | .metadata.name + " " + .metadata.namespace'

# Delete least-critical pods first (check with team before deleting)
kubectl delete pod <pod-name> -n <namespace>
```

### Option B — Drain node if eviction is imminent
```bash
# Cordon first (no new scheduling)
kubectl cordon <node-name>

# Check what will be evicted
kubectl drain <node-name> --ignore-daemonsets --dry-run=client

# Drain (only if approved by senior SRE)
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
```

### Option C — Scale out the node group (EKS)
```bash
# Check current ASG state
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names <asg-name> \
  --query 'AutoScalingGroups[0].{Min:MinSize,Max:MaxSize,Desired:DesiredCapacity}'

# Increase desired count (triggers Karpenter or cluster-autoscaler)
aws autoscaling set-desired-capacity \
  --auto-scaling-group-name <asg-name> \
  --desired-capacity <current+1>
```

## Prevention
- Set memory requests AND limits on all deployments (no unbounded pods)
- Configure VPA (Vertical Pod Autoscaler) for services with variable load
- Set up PodDisruptionBudgets so draining doesn't take down critical services

## Escalation
- If OOM killer is firing on multiple nodes simultaneously → P1, page SRE lead
- If AWS ASG is not scaling → check service quota limits in AWS console

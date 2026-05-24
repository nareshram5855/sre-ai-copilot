# Runbook: Java Pod OOMKilled — Diagnosis and Resolution
Service: Any Java/JVM workload on Kubernetes
Severity: P2 (single pod) → P1 (deployment-wide)
Alert: JavaPodOOMKilled / JavaPodCrashLoopOOM / KubePodCrashLooping

## What is Happening
The Linux kernel OOM killer terminated the Java process because the container's
memory usage exceeded the Kubernetes memory limit. The JVM heap grew beyond
the configured `-Xmx` value, or non-heap memory (metaspace, threads, native)
pushed total RSS over the container limit.

Exit code: `137` (SIGKILL from OOM killer)
Kubernetes status: `OOMKilled` → leads to `CrashLoopBackOff` after repeated restarts.

## Immediate Diagnosis (run in order)

### 1. Confirm OOMKilled and check restart count
```bash
kubectl get pod -n <namespace> -l app=<app-name> -o wide
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Last State"
```
Look for: `Reason: OOMKilled`, `Exit Code: 137`

### 2. Check how much memory the pod was using before crash
```bash
kubectl top pod -n <namespace> --containers
```
If the pod is crashed, check Prometheus for recent memory usage:
```bash
# Max memory used in last 30 minutes
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring &
# Query: max_over_time(container_memory_working_set_bytes{namespace="demo",container="oom-demo"}[30m])
```

### 3. Check current resource limits
```bash
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].resources}' | python3 -m json.tool
```

### 4. Check recent OOM events
```bash
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep -i "oom\|kill\|memory\|BackOff"
```

### 5. Get JVM heap settings from pod logs (before crash)
```bash
kubectl logs <pod-name> -n <namespace> --previous | grep -E "Heap|heap|Xmx|memory|GC"
```

## Resolution Options

### Option A — Increase the K8s memory limit (fastest fix)
Use when: the app is legitimate and just needs more memory.
```bash
kubectl set resources deployment/<deployment-name> \
  -n <namespace> \
  --limits=memory=256Mi \
  --requests=memory=128Mi

kubectl rollout status deployment/<deployment-name> -n <namespace>
kubectl get pods -n <namespace>
```

### Option B — Increase JVM heap via environment variable
Use when: you can control JVM flags via env vars (Spring Boot, etc.).
```bash
kubectl set env deployment/<deployment-name> \
  -n <namespace> \
  JAVA_OPTS="-Xms64m -Xmx192m -XX:MaxMetaspaceSize=128m"

kubectl rollout restart deployment/<deployment-name> -n <namespace>
kubectl rollout status deployment/<deployment-name> -n <namespace>
```

### Option C — Get a heap dump for leak investigation
Use when: memory keeps growing — suspected memory leak.
```bash
# Exec into pod while it is still running (watch -n1 kubectl get pods)
kubectl exec -it <pod-name> -n <namespace> -- sh

# Inside the container — trigger heap dump
jmap -dump:format=b,file=/tmp/heap.hprof 1

# Copy heap dump to local machine for analysis with Eclipse MAT / VisualVM
kubectl cp <namespace>/<pod-name>:/tmp/heap.hprof ./heap.hprof
```

### Option D — Scale horizontally to reduce per-pod load
Use when: memory pressure is due to high request volume.
```bash
kubectl scale deployment/<deployment-name> -n <namespace> --replicas=3
kubectl rollout status deployment/<deployment-name> -n <namespace>
```

## Verify Fix
```bash
# Watch pod stabilise
kubectl get pods -n <namespace> -w

# Confirm no more OOMKilled events
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep -i oom

# Monitor memory over next 10 minutes
kubectl top pod -n <namespace> --containers
```

## Escalation
- If memory grows unbounded after increasing limits → **memory leak, escalate to the owning dev team**
- If multiple pods across the deployment are OOMKilling → **P1, page senior SRE**
- For iam-token-service specifically → contact `#iam-oncall` Slack channel

## Prevention
1. Set JVM heap (`-Xmx`) to 75% of the container memory limit — leaves headroom for metaspace and native memory
2. Add `container_memory_working_set_bytes > 0.8 * container_spec_memory_limit_bytes` alert for early warning
3. Enable GC logging: `-Xlog:gc*:file=/tmp/gc.log:time,uptime:filecount=5,filesize=10m`
4. Add readiness probe so OOMing pods are removed from load balancer before crashing
5. Use Java 21+ with `-XX:+UseZGC` for lower GC pause and better memory efficiency

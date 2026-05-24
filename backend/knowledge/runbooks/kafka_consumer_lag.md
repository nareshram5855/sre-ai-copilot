# Runbook: Kafka Consumer Lag

**Alert:** KafkaConsumerLagHigh, KafkaConsumerGroupBehind
**Severity:** P2 (P1 if lag is growing and service is real-time critical)
**Owner:** Data Platform / SRE
**Estimated time:** 20-30 minutes

## Diagnosis

### Step 1 — Check consumer group lag
```bash
# List all consumer groups
kubectl exec -n kafka kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server kafka:9092 --list

# Check lag for a specific group
kubectl exec -n kafka kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group <consumer-group-name>

# Watch lag in real-time
watch -n 10 "kubectl exec -n kafka kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group <consumer-group-name>"
```

### Step 2 — Check consumer pod health
```bash
# Check if consumer pods are running
kubectl get pods -n <namespace> -l app=<consumer-app>
kubectl logs -n <namespace> deployment/<consumer-name> --tail=100 | \
  grep -E 'error|exception|lag|offset'

# Check consumer CPU/memory (processing too slow?)
kubectl top pods -n <namespace> -l app=<consumer-app>
```

### Step 3 — Check Kafka broker health
```bash
# Broker status
kubectl get pods -n kafka

# Check under-replicated partitions (indicates broker issues)
kubectl exec -n kafka kafka-0 -- \
  kafka-topics.sh --bootstrap-server kafka:9092 \
  --describe --under-replicated-partitions

# Check topic partition count
kubectl exec -n kafka kafka-0 -- \
  kafka-topics.sh --bootstrap-server kafka:9092 \
  --describe --topic <topic-name>
```

## Remediation

### Option A — Scale up consumers (most common fix)
```bash
# Scale consumer deployment
kubectl scale deployment <consumer-name> -n <namespace> --replicas=<new-count>

# Note: replicas cannot exceed partition count — check partition count first
kubectl exec -n kafka kafka-0 -- \
  kafka-topics.sh --bootstrap-server kafka:9092 \
  --describe --topic <topic-name> | grep PartitionCount
```

### Option B — Increase partitions to allow more parallelism
```bash
# Add partitions (can only increase, never decrease)
kubectl exec -n kafka kafka-0 -- \
  kafka-topics.sh --bootstrap-server kafka:9092 \
  --alter --topic <topic-name> \
  --partitions <new-count>

# Rebalance consumer group after partition increase
kubectl exec -n kafka kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --group <consumer-group-name> \
  --topic <topic-name> \
  --execute --reset-offsets --to-latest
```

### Option C — Reset offsets (skip backlog when data is stale)
```bash
# DRY RUN first — see what would happen
kubectl exec -n kafka kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --group <consumer-group-name> \
  --topic <topic-name> \
  --reset-offsets --to-latest --dry-run

# Execute after team approval
kubectl exec -n kafka kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --group <consumer-group-name> \
  --topic <topic-name> \
  --reset-offsets --to-latest --execute
```

## Escalation
- If lag is growing faster than consumption rate → scale immediately, page data platform team
- If broker is under-replicated → do not reset offsets, risk of data loss
- Document any offset reset in incident ticket (audit requirement for financial data)

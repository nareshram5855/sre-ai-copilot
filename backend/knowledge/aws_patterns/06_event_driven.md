# AWS Reference: Event-Driven Architecture

## Pattern: Event-Driven Microservices
**Use when**: async processing, decoupled services, high throughput, audit trail needed

### Architecture
```
API Producers → API Gateway → Lambda (validator)
                            → SQS (primary queue) → Lambda (processor) → DynamoDB
                            → SNS (fan-out) → SQS-A (service A) → Lambda A
                                           → SQS-B (service B) → Lambda B
                                           → SQS-C (service C) → Lambda C

EventBridge → Rules → Lambda (scheduled jobs)
                    → SQS (cross-account events)
                    → SNS (notifications)

Dead Letter Queues: all SQS → DLQ → Lambda (DLQ reprocessor) → CloudWatch alarm
S3 Event Notifications → SQS → Lambda (file processing pipeline)

CloudWatch Events → SNS → Email/PagerDuty (ops alerts)
```

### SQS Design Patterns
- Standard Queue: at-least-once delivery, unlimited throughput (most cases)
- FIFO Queue: exactly-once, ordered — use for financial transactions only (3000 msg/s limit)
- Visibility timeout: set to 6x Lambda timeout to prevent double-processing
- Message retention: 4 days default, 14 days max
- DLQ: after 3 failed attempts, message moves to DLQ — alarm on DLQ depth > 0

### SNS Fan-Out Pattern
- SNS topic per event type (OrderCreated, PaymentProcessed, etc.)
- Each downstream service has its own SQS subscription — they process at their own pace
- SNS message filtering: service only receives relevant attributes (no polling overhead)
- Cross-account: SNS → SQS in another account with resource policy

### EventBridge (preferred over SNS for new architectures)
- EventBridge is the modern choice: 100+ AWS service sources, schema registry, replay
- Replaces SNS+Lambda for routing — EventBridge rules replace Lambda router functions
- EventBridge Pipes: SQS → filter → enrich → target (zero Lambda code)
- Custom event bus per domain (payments-bus, inventory-bus) for isolation

### Idempotency
- DynamoDB conditional writes (if_not_exists) for exactly-once semantics
- Idempotency key in message attributes (request_id or event_id)
- Lambda Powertools idempotency module (recommended)

### Well-Architected
- Reliability: 92/100 — DLQs catch all failures; retry with exponential backoff
- Performance: 88/100 — SQS decouples producers from consumers; burst to thousands/sec
- Cost: 90/100 — Lambda + SQS = pay per message, no idle cost
- Operations: 82/100 — DLQ monitoring critical; add CloudWatch dashboard for queue depths

### Cost Estimate
- SQS: $0.40/million requests (negligible at moderate scale)
- Lambda: $0.20/million invocations + compute
- EventBridge: $1/million events
- DynamoDB on-demand: scales with load
- Total: $20–100/mo depending on message volume

### Terraform Modules
1. security/kms (SQS + SNS encryption at rest)
2. security/iam (Lambda execution roles, SQS send/receive per service)
3. integration/sqs (main queues + DLQs per service)
4. integration/sns (topics per event type)
5. integration/eventbridge (custom buses + rules)
6. networking/apigw (HTTP API for event ingestion)
7. compute/lambda (per event processor, 128MB–512MB)
8. data/dynamodb (on-demand, event store + idempotency table)
9. data/s3 (event archive for replay)
10. monitoring/cloudwatch (DLQ depth alarm, Lambda error rate, age of oldest message)

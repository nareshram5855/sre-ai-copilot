# AWS Reference: Real-Time Streaming Architecture

## Pattern: Real-Time Data Streaming Pipeline
**Use when**: IoT data, clickstream, fraud detection, live analytics, log aggregation

### Architecture (Kinesis-based)
```
Producers → Kinesis Data Streams (KDS, 1 shard = 1MB/s in, 2MB/s out)
          → Lambda (stream processor, batch 100 records)
          → DynamoDB (real-time state / hot storage)
          → S3 (cold storage via Firehose)
          → OpenSearch (search + dashboards)

Kinesis Data Firehose → S3 (Parquet, partitioned by date)
                      → Redshift (analytics)

CloudWatch → Kinesis → Lambda (log-driven alerting)
MSK (Kafka) → alternative for high-throughput (>100MB/s) or complex routing
```

### Kinesis vs MSK Decision
| Factor | Kinesis Data Streams | MSK (Kafka) |
|--------|---------------------|-------------|
| Throughput | Up to 1MB/s per shard | 1GB+/s |
| Retention | 24h default, 7 days max (extended 365 days) | Configurable, unlimited |
| Consumers | 5 enhanced fan-out, unlimited standard | Thousands of consumer groups |
| Ordering | Per-shard | Per-partition |
| Cost | $0.015/shard-hour + put cost | $0.10/broker-hour (3 brokers min) |
| Ops | Zero — fully managed | Medium — broker management |
| Best for | < 1GB/s, AWS-native, simple routing | > 1GB/s, complex routing, existing Kafka |

### Lambda Stream Processor Best Practices
- Batch size: 100–1000 records (tune based on Lambda duration)
- Starting position: LATEST for real-time, TRIM_HORIZON for replay
- Bisect on error: enabled (splits failing batch to isolate poison pills)
- Destination on failure: SQS DLQ
- Parallelization factor: 1–10 (process multiple batches per shard concurrently)
- Tumbling window: aggregate across 5-minute windows with Lambda state

### Fraud Detection Pattern
```
Transaction event → Kinesis → Lambda (feature extraction)
                            → DynamoDB (transaction history lookup, user velocity)
                            → SageMaker endpoint (ML model inference)
                            → DynamoDB (fraud score write)
                            → SNS (alert if score > threshold)
                  → Firehose → S3 → Glue → Athena (audit trail)
```

### Well-Architected
- Performance: 92/100 — Kinesis scales horizontally with shards, sub-second latency
- Reliability: 88/100 — Kinesis replicates across 3 AZs; DLQ catches Lambda failures
- Cost: 75/100 — Kinesis shards + Lambda + S3 storage adds up; right-size shards
- Operations: 80/100 — Kinesis Shard-level metrics in CloudWatch; add iterator age alarm

### Key Alarms
- GetRecords.IteratorAgeMilliseconds > 60000 (processing lag — add shards or optimize Lambda)
- WriteProvisionedThroughputExceeded > 0 (need more shards)
- Lambda Iterator Age > 5 minutes (serious backpressure)

### Cost Estimate
- Kinesis (5 shards): $54/mo
- Lambda (10M invocations): $20/mo
- DynamoDB on-demand (10M writes): $62/mo
- Firehose to S3: $0.029/GB
- S3 storage (1TB): $23/mo
- Total: $200–$400/mo at moderate scale

### Terraform Modules
1. security/kms (Kinesis + S3 + DynamoDB encryption)
2. security/iam (producer role, Lambda consumer role)
3. integration/sqs (DLQ for Lambda failures)
4. data/dynamodb (real-time state store, on-demand)
5. data/s3 (Firehose destination, Parquet partitioned)
6. compute/lambda (stream processor, batch processing)
7. monitoring/cloudwatch (iterator age alarm, error rate)
8. monitoring/xray (Lambda trace sampling)

# AWS Reference: ML Inference Service

## Pattern: Real-Time ML Inference API
**Use when**: model serving, low-latency predictions (<100ms), auto-scaling inference

### Architecture Options

#### Option A: ECS-based (general ML, CPU/GPU)
```
Users → CloudFront → WAF → ALB → ECS Fargate (inference containers)
                                → S3 (model artifacts)
                                → ElastiCache Redis (prediction cache)
                                → SQS (batch inference queue)
                                → Lambda (batch processor)
                              ECR (model container images)
                              KMS + Secrets Manager
                              CloudWatch + X-Ray
```

#### Option B: Lambda-based (lightweight models <250MB)
```
Users → API Gateway → Lambda (model loaded in /tmp or Lambda Layer)
                    → DynamoDB (feature store, prediction logs)
                    → S3 (model artifacts, loaded at cold start)
                    → ElastiCache (feature cache, reduce feature fetch latency)
```

#### Option C: SageMaker Endpoints (managed inference)
- SageMaker Real-Time Endpoint → auto-scaling, A/B testing built in
- Best for: teams that don't want to manage inference infrastructure
- Cost: 2x ECS cost but zero operational overhead

### Model Artifact Management
- S3: models stored in versioned prefix (s3://models-bucket/model-name/v1.2.3/)
- ECR: container with model baked in (simpler) OR model mounted from S3 at startup
- S3 recommendation: mount model at startup for faster updates (no ECR push per model version)

### Performance Patterns
- Redis cache for identical inputs (feature hash → prediction) — cuts 80% of compute
- SQS for batch requests: Lambda consumer processes 1000 records/batch, writes to DynamoDB
- ECS auto-scaling: scale on ALB RequestCountPerTarget (not CPU — inference is bursty)
- Provisioned concurrency (Lambda) or min-task-count=2 (ECS) to eliminate cold starts

### GPU Workloads
- ECS on EC2 g4dn.xlarge (T4 GPU) — NOT Fargate (no GPU support)
- Use NVIDIA Container Toolkit
- Spot instances for batch inference (save 70%), On-Demand for real-time
- EFA (Elastic Fabric Adapter) for distributed training

### Well-Architected
- Performance: 88/100 — Redis cache + auto-scaling + optimized container
- Cost: 82/100 — Spot for batch + cache reduces repeated compute
- Reliability: 80/100 — Multi-AZ ECS + S3 model versioning + ECS health checks
- Security: 85/100 — WAF + KMS + private subnets; no model data public

### Cost Estimate (ECS CPU-based, medium scale)
- ECS Fargate (2 vCPU, 4GB, 3 tasks): ~$120/mo
- ElastiCache cache.t3.small: ~$30/mo
- S3 model storage (10GB): ~$0.25/mo
- CloudWatch + X-Ray: ~$15/mo
- Total: $165–$250/mo (GPU adds ~$300/mo for g4dn.xlarge)

### Terraform Modules
1. networking/vpc
2. networking/waf
3. networking/alb
4. security/kms (S3 model bucket + ECR)
5. security/iam (ECS task role: S3 read, CloudWatch put)
6. security/secrets-manager
7. compute/ecs (GPU: EC2 launch type; CPU: Fargate)
8. cicd/ecr (model containers)
9. data/s3 (model artifacts, versioned)
10. data/elasticache (prediction cache)
11. data/dynamodb (prediction logs, feature store)
12. integration/sqs (batch inference queue)
13. compute/lambda (batch consumer)
14. monitoring/cloudwatch (latency p50/p95/p99 alarms)
15. monitoring/xray

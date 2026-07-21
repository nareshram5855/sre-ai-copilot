# AWS Reference: Serverless API

## Pattern: Serverless REST/GraphQL API
**Use when**: variable traffic, small–medium scale, cost-sensitive, no persistent connections needed

### Architecture
```
Users → CloudFront → WAF → API Gateway → Lambda → DynamoDB
                                       → S3 (file storage)
                                       → SQS (async tasks)
                          Cognito (JWT auth)
                          KMS (encrypt DynamoDB + S3)
                          Secrets Manager (3rd-party API keys)
                          CloudWatch Logs + X-Ray
```

### Key Design Decisions
- API Gateway (HTTP API, not REST API) — 60% cheaper, lower latency
- Lambda: Node.js or Python runtime, 512MB–1GB memory, 30s timeout
- DynamoDB on-demand billing — no capacity planning, scales to 0
- CloudFront in front of API Gateway — caches GET responses, reduces Lambda invocations
- WAF on CloudFront — protects entire surface area with one WAF WebACL
- Cognito User Pool for JWT — Lambda authorizer validates tokens

### Cold Start Mitigation
- Provisioned concurrency for critical paths (prod only, adds $30/mo per 1 concurrency unit)
- Lambda SnapStart for Java runtimes
- Keep functions <10MB deployment package
- Use Lambda Layers for shared dependencies

### Security
- Lambda in VPC only if accessing RDS/ElastiCache — otherwise avoid VPC (adds cold start)
- KMS customer-managed key for DynamoDB encryption + S3 SSE-KMS
- API Gateway resource policy: restrict to CloudFront IPs only
- WAF: AWS Managed Rules + rate limiting (100 req/s per IP)

### Cost Estimate
- Lambda: ~$5–15/mo for 1M invocations
- API Gateway HTTP: $1/million requests
- DynamoDB on-demand: $1.25/million reads, $6.25/million writes
- Total small: $5–30/mo | medium (50M req/mo): $80–200/mo

### Well-Architected
- Security: 88/100 — WAF + Cognito + KMS + Secrets Manager
- Cost: 95/100 — pay per invocation, scales to zero
- Reliability: 75/100 — Lambda retry + DLQ on SQS; no Multi-AZ concern (serverless)
- Performance: 70/100 — cold starts can be 200–800ms on first invoke

### Terraform Modules (deploy order)
1. security/kms
2. security/iam (Lambda execution role)
3. security/secrets-manager
4. networking/waf
5. networking/cloudfront
6. networking/apigw (HTTP API + Lambda integration)
7. compute/lambda (runtime, memory, timeout, VPC config if needed)
8. data/dynamodb (on-demand, GSI for query patterns)
9. data/s3 (versioning, SSE-KMS, lifecycle rules)
10. integration/sqs (DLQ + main queue for async tasks)
11. monitoring/cloudwatch
12. monitoring/xray

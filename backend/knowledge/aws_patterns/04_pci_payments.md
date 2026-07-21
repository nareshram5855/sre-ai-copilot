# AWS Reference: PCI-DSS Compliant Payment Platform

## Pattern: PCI-DSS Level 1 Payment Processing
**Use when**: card data processing, financial transactions, strict compliance required

### PCI-DSS Scope Reduction Strategy
The goal is to minimize the PCI scope. Tokenize card data at the edge; only the token vault and payment processor touch raw PANs.

### Architecture
```
Users → CloudFront → WAF (PCI WAF ruleset) → API Gateway
                                            → Lambda (tokenization)
                                            → Payment Processor (Stripe/Braintree)
                                            → DynamoDB (tokens only, NOT card numbers)
                                            → SQS (transaction events)
                                            → Lambda (fulfillment, out of PCI scope)
                     VPC (isolated, no internet egress except payment processor)
                     ├── Private Subnet: ECS (payment API)
                     ├── Private Subnet: RDS Aurora (transaction records)
                     └── VPC Endpoint: DynamoDB, S3, KMS, Secrets Manager
                     KMS (CMK for all data, annual rotation)
                     Secrets Manager (payment processor API keys, DB creds)
                     CloudTrail (ALL API calls, immutable, 7-year retention)
                     CloudWatch (real-time alerts on anomalies)
                     Security Hub (PCI-DSS standard enabled)
                     GuardDuty (threat detection)
                     Config Rules (continuous compliance)
```

### PCI-DSS Control Mapping
- Requirement 1 (Network): VPC + Security Groups + Network ACLs + no direct internet to cardholder data env
- Requirement 2 (Defaults): No default passwords, hardened AMIs, SSM Parameter Store for config
- Requirement 3 (Stored data): Never store CVV/CVV2, tokenize PAN, KMS encryption at rest
- Requirement 4 (Transit): TLS 1.2+ mandatory, no unencrypted protocols
- Requirement 6 (Vulnerabilities): WAF + Inspector scanning + dependency scanning in CI
- Requirement 7 (Access): IRSA least privilege, no wildcard * policies in PCI scope
- Requirement 8 (Auth): MFA for all human access, IAM Identity Center
- Requirement 9 (Physical): AWS-managed, AWS PCI Attestation of Compliance covers this
- Requirement 10 (Logging): CloudTrail ALL regions + CloudWatch Logs Insights + immutable S3 log bucket
- Requirement 11 (Testing): Inspector continuous + Penetration test per PCI schedule
- Requirement 12 (Policy): Documented in runbooks

### Critical Security Controls (non-negotiable)
- WAF: AWS Managed Rules + AWSManagedRulesPCIv32RuleSet
- No public S3 buckets — S3 Block Public Access account-level
- VPC Endpoints for ALL AWS service access (no traffic to internet)
- CloudTrail: multi-region, log file validation, SNS alert on disable attempts
- S3 log bucket: Object Lock (WORM), Versioning, separate AWS account
- KMS: CMK (not AWS-managed), key rotation annually, key policy restricts to PCI workloads
- RDS: encryption at rest + in transit (ssl-mode=require), no public endpoint
- Security Groups: whitelist ONLY — 0.0.0.0/0 is a PCI violation
- Secrets Manager: auto-rotation, no hardcoded credentials anywhere

### Well-Architected
- Security: 97/100 — Full PCI controls, WAF, zero trust networking
- Reliability: 88/100 — Multi-AZ Aurora + ECS auto-scaling + SQS decoupling
- Cost: 65/100 — Compliance tools (Security Hub, GuardDuty, Config) add $150–300/mo
- Operations: 85/100 — CloudTrail + Config + CloudWatch gives full audit trail

### Cost Estimate
- ECS (2 tasks): $60/mo
- Aurora Multi-AZ: $175/mo
- WAF + Shield Standard: $25/mo
- GuardDuty: $30/mo
- Security Hub (PCI standard): $20/mo
- Config Rules: $15/mo
- CloudTrail: $10/mo
- KMS + Secrets Manager: $15/mo
- Total: $350–$500/mo

### Terraform Modules (deploy order)
1. networking/vpc (isolated, VPC endpoints for all AWS services)
2. networking/waf (PCI ruleset + rate limiting)
3. security/kms (CMK, annual rotation)
4. security/iam (least privilege, no wildcard)
5. security/secrets-manager (payment processor keys, DB creds, rotation)
6. networking/alb (HTTPS only, TLS 1.2+)
7. compute/ecs (private subnets only, task-level IRSA)
8. cicd/ecr (scan on push, tag immutability)
9. data/aurora (PostgreSQL, Multi-AZ, encrypted, no public)
10. data/dynamodb (encrypted, point-in-time recovery)
11. integration/sqs (encrypted, DLQ, visibility timeout)
12. monitoring/cloudwatch (anomaly detection, real-time alerts)

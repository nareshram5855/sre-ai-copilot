# AWS Well-Architected Framework — Quick Reference

## The 6 Pillars

### 1. Operational Excellence
**Goal**: Run and monitor systems, deliver business value, continually improve processes

Key practices:
- Infrastructure as Code (IaC) — Terraform/Terragrunt for all resources
- CI/CD pipelines with automated testing and rollback
- Observability: structured logging (JSON), metrics (CloudWatch), traces (X-Ray)
- Runbooks and playbooks for incident response
- CloudWatch Alarms → SNS → PagerDuty/OpsGenie
- Feature flags for safe releases (AWS AppConfig)

AWS Services: CloudWatch, X-Ray, CloudTrail, Systems Manager, AppConfig

Score boosters:
- CloudWatch dashboards per service (+10)
- X-Ray distributed tracing (+15)
- Automated runbooks (SSM Automation) (+10)
- Canary deployments / blue-green with CodeDeploy (+15)

---

### 2. Security
**Goal**: Protect data, systems, assets — apply security at all layers

Key practices:
- Identity: IAM least privilege, no root account usage, MFA everywhere
- Detective: CloudTrail + CloudWatch Logs Insights + GuardDuty + Security Hub
- Infrastructure: VPC, Security Groups (deny by default), WAF, Shield
- Data: Encryption at rest (KMS) + in transit (TLS 1.2+) for ALL data
- Application: Secrets Manager (no hardcoded credentials), no public S3

Non-negotiable for every architecture:
- WAF on every internet-facing endpoint
- KMS CMK on every data store (RDS, DynamoDB, S3, SQS, SNS)
- CloudTrail in all regions, log file validation enabled
- Secrets Manager (not SSM Parameter Store) for credentials

Score boosters:
- WAF with OWASP Managed Rules (+20)
- KMS on all data stores (+20)
- GuardDuty enabled (+10)
- Security Hub + standard enabled (+10)
- No public S3 (account-level Block Public Access) (+15)

---

### 3. Reliability
**Goal**: Recover from failures, meet demand, mitigate disruptions

Key practices:
- Multi-AZ for all stateful resources (RDS, ElastiCache, ECS)
- Auto-scaling for compute (ECS Service Auto Scaling, EKS Karpenter)
- Health checks and circuit breakers
- Backup and restore: RDS automated backups (7–35 days), DynamoDB PITR
- Service quotas: monitor and request increases proactively

Score boosters:
- Multi-AZ RDS (+20)
- ECS/EKS auto-scaling policy (+15)
- DynamoDB Point-in-Time Recovery enabled (+10)
- S3 versioning (+10)
- ALB health checks with proper thresholds (+10)
- SQS DLQ for all queues (+10)

---

### 4. Performance Efficiency
**Goal**: Use computing resources efficiently, maintain performance as demand changes

Key practices:
- Select right instance type (Graviton3 ARM saves 20% cost, 40% better perf)
- ElastiCache for repeated database queries
- CloudFront for static assets and global distribution
- Connection pooling for RDS (RDS Proxy)
- Lambda: right-size memory (Lambda Power Tuning tool)
- DynamoDB: design for access patterns (GSI), avoid hot partitions

Score boosters:
- ElastiCache Redis (+20)
- CloudFront CDN (+15)
- RDS Proxy (Lambda → RDS) (+15)
- Aurora read replicas (+15)
- Graviton instance types (+10)

---

### 5. Cost Optimization
**Goal**: Avoid unnecessary costs, understand spending, achieve business outcomes efficiently

Key practices:
- Serverless-first (Lambda, DynamoDB on-demand, Fargate) — no idle cost
- Savings Plans (1-year, no upfront) for steady-state workloads: 40% savings
- Spot Instances for stateless/batch workloads: 60–90% savings
- S3 Intelligent-Tiering for unknown access patterns
- Right-size instances: use AWS Compute Optimizer recommendations
- Delete unused resources: unattached EBS volumes, unused Elastic IPs, old snapshots

Score boosters:
- Serverless components present (+15)
- Spot/Fargate Spot for non-critical workloads (+15)
- Auto-scaling to zero off-hours (+10)
- S3 lifecycle policies (+10)
- Savings Plans noted in design (+10)

---

### 6. Sustainability
**Goal**: Minimize environmental impact of running cloud workloads

Key practices:
- Use managed services (AWS manages the hardware efficiency)
- Graviton (ARM) processors: 60% less energy than x86 equivalents
- Scale to zero when not in use (Lambda, Fargate)
- Data lifecycle management: delete old data, use S3 Glacier for archives
- Right-size: over-provisioned resources waste energy

Score boosters:
- AWS managed services (no self-managed EC2) (+20)
- Graviton2/3 instance types (+10)
- Lambda/serverless (scale to zero) (+20)
- Auto-scaling enabled (+15)
- S3 lifecycle to Glacier (+10)

---

## Common Compliance Frameworks

### SOC 2 Type II
- Covered by: CloudTrail, GuardDuty, Security Hub, Config, KMS, VPC Flow Logs
- AWS has SOC 2 Type II report available under NDA (AWS Artifact)

### PCI-DSS Level 1
- WAF mandatory, KMS mandatory, no public S3, VPC private subnets, CloudTrail 7 years
- AWS infrastructure is PCI-certified (see Compliance → PCI in AWS Artifact)

### HIPAA
- Business Associate Agreement (BAA) required with AWS
- Encryption at rest + in transit mandatory
- Access logging, audit trails, minimum necessary access
- PHI must not appear in CloudWatch logs (scrub before logging)

### SOX (Sarbanes-Oxley)
- IT General Controls: change management, access control, audit trail
- CloudTrail + Config provide the audit trail
- Immutable S3 bucket (Object Lock) for log retention (7 years)

### GDPR
- EU data residency (eu-west-1 or eu-central-1)
- Encryption + pseudonymization
- Right to erasure: design DynamoDB / RDS schemas with user_id for targeted delete
- Data Processing Agreement (DPA) with AWS (in GDPR Data Processing Addendum)

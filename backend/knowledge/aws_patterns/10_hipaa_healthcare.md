# AWS Reference: HIPAA-Compliant Healthcare Platform

## Pattern: HIPAA-Compliant API + Data Store
**Use when**: electronic health records (EHR), patient data, clinical apps, telehealth

### HIPAA Technical Safeguards → AWS Services
| Safeguard | AWS Implementation |
|-----------|-------------------|
| Access Control | IAM + Cognito (MFA required) + RBAC per patient role |
| Audit Controls | CloudTrail (7 years) + CloudWatch Logs + Config |
| Integrity | KMS signatures + S3 versioning + DynamoDB PITR |
| Transmission Security | TLS 1.2+ everywhere + VPC endpoints (no public internet for PHI) |
| Person Authentication | Cognito + MFA + IAM Identity Center |

### Architecture
```
Patients → CloudFront → WAF (OWASP + rate limit)
                     → API Gateway (Cognito JWT authorizer)
                     → Lambda (PHI scrubbing before log, PII redaction)
                     → VPC Endpoints (PrivateLink) — PHI never traverses public internet
                     → Aurora PostgreSQL Encrypted (KMS CMK)
                     → S3 (medical images, DICOM — SSE-KMS, versioning)
                     → ElastiCache Redis (session cache — in-transit + at-rest encrypted)

Clinician Portal → ALB + Cognito SAML (hospital IdP)
                → ECS Fargate (clinical application)
                → Aurora (patient records, row-level security by provider_id)
                → S3 (lab results, imaging)

PHI Audit Trail → CloudTrail → S3 (WORM with Object Lock, 7 years)
               → CloudWatch Logs (sanitized — no raw PHI in log strings)
               → Config Rules → Lambda (auto-remediate non-compliant resources)

HIPAA Backup → RDS automated backups (35 days) + manual snapshots (7 years)
             → S3 Cross-Region Replication to secondary region (DR)
             → DynamoDB Global Tables (if using DynamoDB)
```

### BAA (Business Associate Agreement)
- AWS signs a BAA — required before storing any PHI
- Enable on: RDS, S3, DynamoDB, Lambda, ECS, EKS, CloudWatch, CloudTrail, KMS
- HIPAA Eligible Services list: https://aws.amazon.com/compliance/hipaa-eligible-services-reference/

### PHI Data Handling
- Never log PHI — scrub in Lambda before CloudWatch (use regex for SSN, DOB, name)
- Pseudonymize: store patient_id (UUID), not name, in query params / log context
- S3: separate bucket per data class (imaging, lab results, clinical notes)
- DynamoDB: attribute-level encryption for PHI fields (Lambda encryption layer)

### Minimum Necessary Access (HIPAA §164.514(d))
- IAM: physicians see own-patient records only (row-level using patient_id + Cognito claims)
- Lambda: only the processing function that needs PHI gets DecryptSecretValue permission
- Cross-service: VPC endpoints + resource policies — no internet path for PHI data

### Well-Architected
- Security: 92/100 — KMS everywhere + CloudTrail WORM + WAF + no public PHI paths
- Compliance: 95/100 — BAA + all 18 HIPAA technical safeguards covered
- Reliability: 85/100 — Multi-AZ Aurora + S3 replication; add Route53 health check failover
- Cost: 72/100 — HIPAA overhead (KMS + 7-year retention + audit) adds baseline cost

### Cost Estimate
- Aurora Multi-AZ (db.r6g.large): ~$250/mo
- KMS (100k API calls/mo): ~$5/mo
- CloudTrail + S3 (7-year logs): ~$15/mo
- WAF: ~$5 + $0.60/million requests
- Cognito (10k MAU free, then $0.0055/MAU): minimal at early stage
- Total: $350–$600/mo base (compliance overhead is significant)

### Terraform Modules
1. networking/vpc (private subnets only for PHI, VPC endpoints for S3/DynamoDB/KMS)
2. networking/waf (OWASP + rate limit + geo-block if US-only)
3. networking/apigw (Cognito JWT authorizer)
4. security/kms (CMK per data class: RDS, S3-imaging, S3-docs, DynamoDB)
5. security/iam (RBAC: physician role, nurse role, admin role, audit role)
6. security/secrets-manager (DB creds, 3rd party lab system API keys)
7. data/aurora (encrypted, Multi-AZ, 35-day backup, deletion protection)
8. data/s3 (3 buckets: imaging, lab, clinical-notes — WORM for audit bucket)
9. data/elasticache (encrypted Redis, no PHI cache keys exposed)
10. compute/lambda (PHI scrubbing middleware)
11. compute/ecs (clinical application, private subnets)
12. monitoring/cloudwatch (PHI access alarms, unusual access patterns)

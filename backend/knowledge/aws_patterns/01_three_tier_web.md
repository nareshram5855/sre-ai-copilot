# AWS Reference: Three-Tier Web Application

## Pattern: Three-Tier Web Application on ECS
**Use when**: REST API backend + relational database, medium scale (10k–500k req/day), team familiar with containers

### Architecture
- **Tier 1 (Edge)**: CloudFront CDN + WAF (rate limiting, OWASP Top 10 rules) + Route53
- **Tier 2 (Compute)**: ALB → ECS Fargate (private subnet, auto-scaling 2–20 tasks)
- **Tier 3 (Data)**: RDS PostgreSQL Multi-AZ (private subnet) + ElastiCache Redis (session + cache)

### Key AWS Services
```
Route53 → CloudFront → WAF → ALB → ECS Fargate → RDS Aurora PostgreSQL
                                                 → ElastiCache Redis
                              ECR (image registry)
                              Secrets Manager (DB creds)
                              KMS (encrypt RDS + ElastiCache at rest)
                              CloudWatch (logs + alarms)
                              X-Ray (distributed tracing)
```

### Security Best Practices
- WAF with AWS Managed Rules (AWSManagedRulesCommonRuleSet)
- ECS task role: least-privilege IAM, never use root/admin
- RDS: encryption at rest (KMS), SSL in transit, no public accessibility
- Secrets Manager for DB password rotation (not env vars)
- Security Groups: ALB allows 443 only; ECS allows from ALB SG only; RDS allows from ECS SG only
- VPC Flow Logs enabled

### Well-Architected Notes
- Security: 92/100 — WAF + KMS + Secrets Manager + private subnets
- Reliability: 85/100 — Multi-AZ RDS + ECS auto-scaling
- Performance: 78/100 — ElastiCache reduces DB reads by ~60%
- Cost: $120–$280/mo (ECS 2 tasks + RDS t3.medium Multi-AZ + ElastiCache t3.micro)

### Terraform Modules (deploy order)
1. networking/vpc (CIDR 10.0.0.0/16, 2 AZs, public + private subnets)
2. networking/waf (managed rules, rate limit 2000 req/5min per IP)
3. networking/cloudfront (origin = ALB)
4. networking/alb (HTTPS listener, HTTP→HTTPS redirect)
5. security/kms (1 key for RDS + ElastiCache)
6. security/iam (ECS task role + execution role)
7. security/secrets-manager (DB password, auto-rotation 30 days)
8. compute/ecs (Fargate, 0.5 vCPU / 1GB min, auto-scale on CPU 70%)
9. cicd/ecr (container registry, scan on push)
10. data/rds (postgres 15, db.t3.medium, Multi-AZ, 100GB gp3)
11. data/elasticache (redis 7, cache.t3.micro, cluster mode off)
12. monitoring/cloudwatch (log groups, CPU/memory/latency alarms)
13. monitoring/xray (sampling 5%, ECS instrumentation)

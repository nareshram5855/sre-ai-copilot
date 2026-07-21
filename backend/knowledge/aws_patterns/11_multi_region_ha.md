# AWS Reference: Multi-Region Active-Active Architecture

## Pattern: Multi-Region Active-Active for High Availability
**Use when**: 99.99%+ SLA, global users, disaster recovery RTO < 1 minute

### Architecture
```
Global → Route53 Latency Routing → us-east-1 + eu-west-1 + ap-southeast-1
       → GeoDNS (optional: GDPR requires EU traffic stays in EU)

Each Region:
  CloudFront → WAF → ALB → ECS Fargate (stateless API)
                         → Aurora Global Database (primary in us-east-1, read replicas in other regions)
                         → ElastiCache Global Datastore (Redis replication <1s lag)
                         → DynamoDB Global Tables (multi-master, <1s replication)

Cross-Region:
  Route53 Health Checks → Failover to secondary region if health check fails
  S3 Cross-Region Replication → static assets, uploads sync across regions
  Secrets Manager Replication → credentials in each region (no cross-region calls)
  ECR → cross-region image replication (ECS pulls from local ECR)
```

### Aurora Global Database (the key component)
- Primary region: all writes go here (us-east-1)
- Secondary regions: read replicas with <1 second replication lag
- Promotion (failover): 60–120 seconds to promote secondary to primary
- RPO: < 1 second (almost zero data loss)
- RTO: 1–2 minutes (manual or automated promotion)

### DynamoDB Global Tables (for sessions/state)
- Multi-master: writes in ANY region, replicated everywhere
- Conflict resolution: last-writer-wins (LWW) by timestamp
- Best for: session data, feature flags, configuration, user preferences
- Not for: financial transactions (use Aurora for ACID compliance)

### Route53 Failover Strategy
```
Tier 1: Latency routing (normal ops — lowest latency wins)
  Route53 Latency → us-east-1 (50ms) | eu-west-1 (80ms) | ap (200ms)

Tier 2: Health-check failover (incident ops)
  If us-east-1 health check fails → Route53 removes it from rotation
  Traffic shifts to eu-west-1 within 30 seconds (DNS TTL: 30s)
```

### ECS Stateless Design (critical for active-active)
- No local state in containers — all state in DynamoDB/Aurora/Redis
- Sticky sessions: NOT allowed in active-active (load balancer must route freely)
- JWT tokens with short expiry (15 min) — no server-side session storage
- File uploads: direct S3 upload (presigned URL), no file on ECS container

### Cross-Region Cost Optimization
- Don't run full capacity in each region — use auto-scaling min=1, max=20
- Off-peak regions scale down (us-east-1 at 3am = ap peak, so both stay active)
- Aurora Global DB: secondary regions are read-only — 50% cost savings on DB
- CloudFront: cache static assets at edge — reduces origin calls in non-primary regions

### Disaster Recovery Tiers
| Tier | RTO | RPO | Strategy |
|------|-----|-----|----------|
| Backup/Restore | Hours | Hours | S3 snapshots only |
| Pilot Light | 30 min | Minutes | Secondary region with min infra |
| Warm Standby | 5 min | Seconds | Secondary fully running, smaller fleet |
| Active-Active | <1 min | <1 sec | This pattern — all regions active |

### Well-Architected
- Reliability: 98/100 — Multi-region, no single point of failure, Route53 auto-failover
- Performance: 90/100 — Latency routing + CloudFront + regional Aurora read replicas
- Cost: 55/100 — Expensive: 3x compute + Aurora Global + Route53 health checks + data transfer
- Operations: 82/100 — Runbooks for promotion, chaos testing (Game Day) essential

### Cost Estimate (2-region active-active)
- ECS Fargate (3 tasks × 2 regions): ~$300/mo
- Aurora Global Database: ~$500/mo (primary + 2 replicas)
- ElastiCache Global Datastore: ~$150/mo
- DynamoDB Global Tables: ~$50–200/mo (write replicated = 2x writes billed)
- CloudFront + Route53: ~$100/mo
- Data transfer cross-region: ~$0.02/GB (~$50/mo at 2.5TB)
- Total: $1,200–$2,000/mo (vs. $400–600/mo single region)

### Terraform Modules (per region, parameterized)
```hcl
# Deploy same stack to multiple regions via Terragrunt
module "app" {
  source = "git::https://github.com/nareshram5855/infra-platform//modules/app?ref=v1.0"
  region = var.region  # us-east-1, eu-west-1
  is_primary = var.region == "us-east-1"
}
```
1. networking/vpc (per region)
2. networking/waf (per region, CloudFront uses us-east-1 WAF)
3. networking/cloudfront (global, single distribution)
4. networking/route53 (latency records + health checks)
5. data/aurora (Global Database — primary in one region, replica in others)
6. data/elasticache (Global Datastore replication group)
7. data/dynamodb (Global Tables — regions declared in resource)
8. data/s3 (CRR — Cross-Region Replication between buckets)
9. security/secrets-manager (replicate to each region)
10. compute/ecs (per region, auto-scaling 1–20)
11. monitoring/cloudwatch (cross-region dashboard in us-east-1)

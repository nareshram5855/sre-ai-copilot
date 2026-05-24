# IAM Platform Architecture Overview

## Services

### Authentication Layer
- **PingFederate** (ping-identity-auth): OAuth2/OIDC token issuance
  - Namespace: iam
  - Replicas: 3 (HPA: 3-10)
  - Port: 9031 (HTTPS), 9999 (admin)
  - DB: PostgreSQL (iam-postgres)

- **SiteMinder Policy Server** (siteminder-policy-server): Legacy SSO
  - Namespace: ciso
  - Replicas: 6 (fixed — no HPA)
  - Port: 44441/44443
  - Session store: Redis (sm-redis)

### Token Services
- **iam-token-service**: Token validation/introspection
  - Namespace: iam
  - Replicas: 4 (HPA: 4-20)
  - DB: PostgreSQL (iam-token-db) via PgBouncer
  - SLO: p99 < 200ms

### Infrastructure Dependencies
- **PostgreSQL**: RDS Aurora PostgreSQL 15 (prod) / containerized (dev)
- **Redis**: ElastiCache Redis 7 for session caching
- **Kafka**: MSK for audit event streaming

## EKS Cluster Layout
- Node groups managed by Karpenter
- auth-node-pool: r6i.2xlarge (memory optimized — JVM workloads)
- general-pool: m6i.xlarge (default)
- Namespaces: iam, ciso, platform, monitoring

## Key Runbook Links
- Pod CrashLoop: runbooks/pod_crashloop.md
- High CPU: runbooks/high_cpu.md
- DB Connection Exhaustion: runbooks/db_connection_pool.md

## On-Call Contacts
- IAM Platform: #iam-oncall Slack
- CISO Platform: #ciso-oncall Slack
- Escalation: PagerDuty IAM-PROD service

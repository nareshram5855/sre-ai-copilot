# AWS Reference: EKS Microservices Platform

## Pattern: Kubernetes Microservices on EKS
**Use when**: large scale (500k+ req/day), multiple teams, service mesh needed, complex deployments

### Architecture
```
Users → Route53 → CloudFront → WAF → ALB (AWS Load Balancer Controller)
                                   → EKS (Managed Node Groups, 3 AZs)
                                       ├── Namespace: payments
                                       ├── Namespace: auth  
                                       └── Namespace: notifications
                              Aurora PostgreSQL (Multi-AZ, read replicas)
                              ElastiCache Redis Cluster Mode
                              ECR (container registry)
                              MSK / SQS (inter-service messaging)
                              Secrets Manager (K8s ExternalSecrets)
                              KMS (EKS secrets encryption, RDS, EBS)
                              CloudWatch Container Insights
                              X-Ray (AWS Distro for OpenTelemetry)
```

### EKS Cluster Design
- Managed Node Groups: On-demand (m5.xlarge) for system + Spot (m5.2xlarge) for app workloads
- Karpenter for node auto-provisioning (replaces Cluster Autoscaler)
- EKS Addons: CoreDNS, kube-proxy, VPC CNI, EBS CSI Driver
- IRSA (IAM Roles for Service Accounts) — no node-level IAM permissions
- EKS Control Plane logging → CloudWatch (audit, authenticator, API server)
- Private endpoint only for API server in prod

### Networking
- VPC: 3 AZs, /16 CIDR, private subnets for nodes, public subnets for ALB only
- AWS VPC CNI: pods get VPC IPs (no overlay network, low latency)
- Network Policies (Calico or AWS Network Policy Controller)
- ALB Ingress Controller: one ALB per environment, path-based routing per service

### Security
- EKS: cluster-level KMS encryption for Kubernetes Secrets
- Pod Security Standards: restricted mode for all namespaces
- IRSA per microservice — payment service gets DynamoDB:* only, nothing else
- ECR image scanning (enhanced with Inspector) + Admission Controller (OPA Gatekeeper)
- Falco runtime security
- WAF with Bot Control + Managed Rules on ALB

### Cost Estimate (prod, 3 m5.xlarge on-demand + Spot workers)
- EKS control plane: $73/mo
- On-demand nodes (3x m5.xlarge): ~$450/mo
- Spot workers (variable): $100–200/mo
- Aurora Multi-AZ db.r6g.large: $175/mo
- ElastiCache r6g.large: $120/mo
- Total: $900–$1,200/mo

### Well-Architected
- Security: 94/100 — IRSA + pod security + WAF + KMS + private API server
- Reliability: 92/100 — Multi-AZ nodes + Aurora replicas + K8s self-healing
- Performance: 90/100 — Spot workers + ElastiCache + Aurora read replicas
- Operations: 88/100 — Container Insights + X-Ray + Karpenter autoscaling
- Cost: 72/100 — Significant fixed cost; Spot workers help but EKS itself is expensive

### Terraform Modules (deploy order)
1. networking/vpc (3 AZs, large CIDR for pod IPs)
2. networking/waf
3. networking/alb (AWS LBC managed)
4. security/kms (3 keys: EKS secrets, RDS, ElastiCache)
5. security/iam (IRSA roles per service)
6. security/secrets-manager (ExternalSecrets operator)
7. compute/eks (1.29+, managed node groups, IRSA enabled)
8. cicd/ecr (per service repository)
9. data/aurora (PostgreSQL 15, Multi-AZ, 2 read replicas)
10. data/elasticache (Redis 7, cluster mode, 3 shards)
11. integration/sqs (per service queue + DLQ)
12. monitoring/cloudwatch (Container Insights, custom dashboards)
13. monitoring/xray (ADOT collector as DaemonSet)

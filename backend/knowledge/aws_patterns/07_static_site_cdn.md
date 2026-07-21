# AWS Reference: Static Site with CloudFront CDN

## Pattern: Static Website / SPA + Lambda API
**Use when**: React/Vue/Angular frontend, serverless backend, global distribution needed

### Architecture
```
Users → Route53 (apex + www CNAME) → CloudFront → WAF
                                               → S3 (static assets, OAC)
                                               → API Gateway → Lambda (REST/GraphQL)
                                                            → DynamoDB
                                                            → SES (email)
                                    ACM Certificate (us-east-1 for CloudFront)
                                    S3 (secondary: log bucket, redirect bucket)
                                    KMS (S3 SSE-KMS)
                                    Secrets Manager (3rd party API keys)
                                    CloudWatch + X-Ray
```

### S3 Configuration (critical)
- Block ALL public access — use CloudFront Origin Access Control (OAC), not OAI (legacy)
- OAC bucket policy: only CloudFront distribution can GetObject
- Versioning: enabled (easy rollback)
- Server-access logging → separate S3 bucket
- Static website hosting: DISABLED — let CloudFront handle routing
- Error document: index.html (for SPA client-side routing)

### CloudFront Configuration
- Price class: PriceClass_100 (US/EU) or PriceClass_All (global) based on audience
- Caching behaviors: /api/* → no cache; /*.js, /*.css → cache 365 days (content hash in filename)
- Custom error responses: 404 → index.html (200) for SPA routing
- Security headers via CloudFront Response Headers Policy: HSTS, CSP, X-Frame-Options
- WAF WebACL (us-east-1) with managed rules + rate limiting
- Compress: Gzip + Brotli enabled
- HTTP/2 + HTTP/3 (QUIC) enabled

### CI/CD for Deploys
```
GitHub Actions → npm build → aws s3 sync --delete
              → aws cloudfront create-invalidation --paths "/*"
```
- Use S3 sync with --cache-control for long-lived assets (1 year) vs index.html (no-cache)

### Lambda API (same domain via CloudFront path rule /api/*)
- Runtime: Node.js 20 (fastest cold start) or Python 3.12
- Memory: 512MB (good baseline, tune with Lambda Power Tuning tool)
- Lambda URL (alternative to API Gateway, simpler, lower cost)
- API Gateway HTTP API: cheaper than REST API, supports JWT authorizer

### Well-Architected
- Cost: 98/100 — S3 + CloudFront + Lambda = almost zero for small/medium traffic
- Performance: 92/100 — CloudFront PoPs globally, Brotli compression, HTTP/3
- Security: 85/100 — OAC + WAF + HTTPS; add CSP header for full marks
- Reliability: 88/100 — S3 is 11-nines; CloudFront automatically routes around failures
- Operations: 80/100 — Simple deploy pipeline; add CloudWatch RUM for real-user monitoring

### Cost Estimate
- S3 (10GB storage, 100GB transfer): ~$3/mo
- CloudFront (1TB transfer): ~$85/mo (most expensive item at scale)
- Lambda (1M invocations): ~$2/mo
- API Gateway HTTP: ~$1/mo
- WAF: ~$5/mo base + $0.60/million requests
- Route53: ~$0.50/mo
- Total small: $5–15/mo | medium (1TB/mo CDN): $100–130/mo

### Terraform Modules
1. networking/waf (us-east-1 for CloudFront)
2. networking/cloudfront (OAC, behaviors, error responses)
3. security/kms (S3 SSE-KMS)
4. security/iam (Lambda execution role)
5. security/secrets-manager (API keys)
6. data/s3 (website bucket + log bucket + redirect bucket)
7. networking/apigw (HTTP API, /api/* path)
8. compute/lambda (API handler)
9. data/dynamodb (on-demand)
10. monitoring/cloudwatch (Lambda errors, 4xx/5xx from CloudFront)

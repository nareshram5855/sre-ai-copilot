# Runbook: TLS Certificate Expiry / Rotation

**Alert:** CertificateExpiringSoon, TLSCertExpiry
**Severity:** P1 if < 7 days, P2 if < 30 days
**Owner:** IAM Platform / SRE
**Estimated time:** 20-30 minutes

## Diagnosis

### Step 1 — Identify expiring certificates
```bash
# List all cert-manager certificates and their expiry
kubectl get certificates --all-namespaces -o wide

# Find certs expiring within 30 days
kubectl get certificates --all-namespaces -o json | \
  jq -r '.items[] | select(.status.notAfter != null) |
    "\(.metadata.namespace)/\(.metadata.name): \(.status.notAfter)"' | \
  sort -k2

# Check a specific certificate
kubectl describe certificate <cert-name> -n <namespace>
```

### Step 2 — Check cert-manager controller health
```bash
kubectl get pods -n cert-manager
kubectl logs -n cert-manager deployment/cert-manager --tail=50 | grep -E 'error|fail|warn'
```

### Step 3 — Check the ACME challenge status (Let's Encrypt)
```bash
kubectl get challenges --all-namespaces
kubectl describe challenge <challenge-name> -n <namespace>
```

## Remediation

### Force cert-manager to renew immediately
```bash
# Trigger renewal by annotating the certificate
kubectl annotate certificate <cert-name> -n <namespace> \
  cert-manager.io/issue-once="true" --overwrite

# Or delete the certificate secret to force full reissuance
kubectl delete secret <tls-secret-name> -n <namespace>
# cert-manager will automatically recreate it
```

### Manual rotation for AWS ACM certificates
```bash
# Request new certificate
aws acm request-certificate \
  --domain-name <domain> \
  --validation-method DNS \
  --subject-alternative-names "*.internal.example.com"

# Import external certificate into ACM
aws acm import-certificate \
  --certificate fileb://cert.pem \
  --private-key fileb://key.pem \
  --certificate-chain fileb://chain.pem
```

### Update Kubernetes secret manually (emergency)
```bash
# Create TLS secret from existing cert files
kubectl create secret tls <secret-name> \
  --cert=cert.pem \
  --key=key.pem \
  -n <namespace> \
  --dry-run=client -o yaml | kubectl apply -f -

# Force pod restart to pick up new secret
kubectl rollout restart deployment/<deployment-name> -n <namespace>
```

### Verify rotation succeeded
```bash
# Check certificate expiry via openssl
echo | openssl s_client -connect <hostname>:443 2>/dev/null | \
  openssl x509 -noout -dates

# Check cert-manager issued successfully
kubectl get certificate <cert-name> -n <namespace> -o yaml | grep -A 5 "status"
```

## Escalation
- If ACME challenge is stuck > 10 minutes: check DNS propagation, firewall rules
- If cert is expired and service is down: use self-signed certificate as interim
- Always notify security team of certificate changes (audit trail requirement)

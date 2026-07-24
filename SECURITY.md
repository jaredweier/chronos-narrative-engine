# Chronos CJIS Security Configuration Strategy

This document outlines the security controls that must be enabled when deploying Chronos Narrative Engine to an enterprise GovCloud environment, fulfilling the Phase 3 roadmap.

## 1. Data Encryption at Rest (FIPS 140-2)
To comply with CJIS policies, all data at rest must be encrypted using FIPS 140-2 validated cryptographic modules.

- **PostgreSQL Data Volume**: The `pgdata` Docker volume must be backed by an AWS EBS Encrypted Volume or equivalent, utilizing a Customer Managed Key (CMK) in AWS KMS.
- **Evidence Storage**: The `evidence_storage` directory must be mapped to an encrypted S3 bucket (or EFS) using `AES256` or `aws:kms`.

## 2. Data Encryption in Transit (TLS 1.2+)
Internal microservice traffic must be encrypted:
- The FastAPI `api_server` is prepared to accept `--ssl-keyfile` and `--ssl-certfile`. In Kubernetes, use an ingress controller (like NGINX or Traefik) configured with `mTLS` and cert-manager to automatically issue certificates.
- Next.js must be served over HTTPS.

## 3. Identity and Access Management (MFA)
- **Keycloak IdP**: The `api_server.py` auth verification layer has been stubbed to intercept Keycloak-issued JWTs. 
- You must configure Keycloak to require hardware tokens (e.g., YubiKey, FIDO2) or PIV/CAC cards for officer login.

## 4. Threat Auditing
- Ensure the PostgreSQL database logs all login events to an external immutable audit log sink (e.g., AWS CloudWatch).

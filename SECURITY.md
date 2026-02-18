# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Current release |

As EcoTrack matures, we will maintain security patches for the current major release and one previous major release.

---

## Reporting a Vulnerability

**⚠️ Please do NOT report security vulnerabilities through public GitHub issues.**

We take the security of EcoTrack seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Email**: Send details to [security@ecotrack.earth](mailto:security@ecotrack.earth)
2. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Suggested fix (if any)
3. **Encrypt** sensitive details using our PGP key (available at [ecotrack.earth/.well-known/security.txt](https://ecotrack.earth/.well-known/security.txt))

### Response Timeline

| Stage | Timeline |
|-------|----------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix development | Depends on severity |
| Coordinated disclosure | After fix is released |

### What to Expect

- A confirmation email within 48 hours acknowledging receipt
- Regular updates on the status of your report
- Credit in the security advisory (unless you prefer anonymity)
- We will not take legal action against researchers who follow responsible disclosure

---

## Security Practices

### Authentication & Authorization

- **JWT tokens** for session-based authentication via Supabase Auth
- **API keys** (SHA-256 hashed) for programmatic access
- **Role-Based Access Control (RBAC)** with 5 roles: `viewer`, `analyst`, `contributor`, `admin`, `api_consumer`
- **Row-Level Security (RLS)** in PostgreSQL for data isolation

### Input Validation

- All API inputs validated via **Pydantic** schemas (Python) and **class-validator** (TypeScript)
- SQL injection prevention through parameterized queries and ORM usage
- XSS prevention via Content Security Policy (CSP) headers
- Request body size limits enforced

### Rate Limiting

- Token-bucket rate limiting backed by Redis
- Tiered limits based on user role:
  - Free: 30 requests/minute, 1,000/day
  - Researcher: 120 requests/minute, 10,000/day
  - Institutional: 600 requests/minute, 100,000/day

### Transport Security

- TLS 1.3 enforced for all production traffic
- HSTS headers with `includeSubDomains`
- Certificate management via cert-manager + Let's Encrypt

### Data Protection

- Database credentials stored in Kubernetes Secrets (Sealed Secrets in production)
- S3/MinIO server-side encryption for stored objects
- No sensitive data in application logs (PII redaction)
- Environment variables for all secrets (never committed to source)

### Container Security

- Multi-stage Docker builds with minimal runtime images
- Non-root container execution
- Read-only filesystem where possible
- Resource limits enforced via Kubernetes

### Supply Chain Security

- **Dependabot** for automated dependency updates
- **Trivy** container image scanning in CI/CD
- **CodeQL** static analysis for Python and TypeScript
- **GitLeaks** for secret detection in commits
- Pinned dependency versions in lock files

### CI/CD Security Gates

Every pull request must pass:

1. **SAST** — CodeQL static analysis
2. **Dependency audit** — Known vulnerability check
3. **Secret scanning** — GitLeaks pre-commit and CI check
4. **Container scan** — Trivy image vulnerability scan
5. **License compliance** — Automated license compatibility check

---

## Security-Related Configuration

### Environment Variables

Never commit secrets to source control. Use `.env` files locally (excluded via [`.gitignore`](.gitignore)) and Kubernetes Secrets in production.

Required secrets:

| Variable | Description |
|----------|-------------|
| `DB_PASSWORD` | PostgreSQL database password |
| `REDIS_PASSWORD` | Redis authentication password (production) |
| `S3_SECRET_KEY` | MinIO/S3 secret access key |
| `NEO4J_PASSWORD` | Neo4j database password |
| `JWT_SECRET` | JWT signing secret |
| `API_ENCRYPTION_KEY` | API key encryption key |

### Security Headers

The API sets the following security headers on all responses:

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Referrer-Policy: strict-origin-when-cross-origin
```

---

## Acknowledgments

We gratefully acknowledge security researchers who help improve EcoTrack's security posture. Acknowledged contributors will be listed here (with their permission).

---

## Contact

- **Security reports**: [security@ecotrack.earth](mailto:security@ecotrack.earth)
- **General questions**: [GitHub Discussions](https://github.com/ecotrack/ecotrack/discussions)

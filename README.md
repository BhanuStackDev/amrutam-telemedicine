# Amrutam Telemedicine Backend

Production-grade telemedicine backend built with FastAPI, PostgreSQL, Redis and containerized infrastructure.

## Scope

The platform covers:

- User lifecycle, authentication, RBAC and MFA
- Doctor management and search/filtering
- Availability slot management
- Concurrency-safe consultation booking
- Consultation lifecycle
- Prescription issuance
- Payment data model and administrative analytics
- Persistent idempotency for writes
- Security/compliance audit trails
- Prometheus metrics and structured logging
- Health/readiness probes
- Docker Compose development environment
- Automated tests and GitHub Actions CI

## Technology

- Python 3.11
- FastAPI
- SQLAlchemy async
- PostgreSQL
- Redis
- Alembic
- Celery-ready task infrastructure
- PyJWT
- Argon2 password hashing
- TOTP MFA
- Prometheus
- OpenTelemetry-compatible instrumentation
- Docker

## Local setup

### 1. Create environment

Copy `.env.example` to `.env` and provide strong secrets.

### 2. Start dependencies

```powershell
docker compose up -d postgres redis
---
Developed & Managed by Bhanuday Urmaliya — Full Stack Developer
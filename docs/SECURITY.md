# Amrutam Telemedicine Backend - Security and Threat Model



## Security Objectives



The service protects identity, authentication credentials, MFA secrets, consultation information, prescriptions, payment references and audit records.



Security controls focus on confidentiality, integrity, availability, least privilege and traceability.



## Data Classification



### Restricted



\- Password hashes

\- MFA secrets

\- Clinical notes

\- Prescription data

\- Patient/doctor relationships



### Confidential



\- Email addresses

\- Profiles

\- Appointment details

\- Payment metadata



### Internal



\- Operational logs

\- Metrics

\- Deployment metadata



### Public



\- API documentation

\- Non-sensitive service metadata



Restricted and confidential information must not be exposed through logs, metrics labels or error responses.



## Authentication Controls



Implemented controls include:



\- Argon2 password hashing

\- Short-lived JWT access tokens

\- Rotating refresh-token sessions

\- Refresh-token hash persistence

\- Refresh-token reuse detection

\- TOTP MFA

\- Encrypted MFA secret storage

\- Failed-login tracking

\- Temporary account lockout

\- Redis-backed rate limiting



Production traffic must use HTTPS/TLS.



## Authorization and RBAC



The application supports:



\- patient

\- doctor

\- admin



Authorization is enforced through API dependencies and service-layer checks.



Ownership checks prevent users from accessing another user's protected resources.



Administrative functionality requires the admin role.



## Threat Model



### Credential Stuffing



Attackers may repeatedly submit compromised credentials.



Mitigations:



\- Argon2 password hashing

\- rate limiting

\- failed-login tracking

\- account lockout

\- MFA



### JWT Theft



An attacker may obtain an access token.



Mitigations:



\- short access-token lifetime

\- token type validation

\- refresh-token rotation

\- HTTPS in production



### Refresh Token Replay



An attacker may replay a previously used refresh token.



Mitigations:



\- hashed refresh tokens

\- refresh rotation

\- revocation

\- reuse detection



### Broken Object-Level Authorization



An attacker may modify identifiers to access another user's consultation or prescription.



Mitigations:



\- authenticated identity checks

\- role checks

\- ownership validation

\- service-layer authorization



### Double Booking



Concurrent requests may attempt to reserve the same availability slot.



Mitigations:



\- persistent idempotency records

\- canonical request hashing

\- PostgreSQL row locking

\- atomic consultation and slot update

\- unique consultation/slot relationship



### SQL Injection



Malicious input may attempt to alter database queries.



Mitigations:



\- SQLAlchemy parameterized queries

\- Pydantic validation

\- no SQL string concatenation for application data



### Sensitive Data Leakage



Clinical or authentication information may accidentally appear in logs or errors.



Mitigations:



\- structured logging

\- controlled audit metadata

\- sensitive-field filtering

\- generic internal error responses

\- environment-based secret configuration



### Denial of Service



Attackers may send excessive traffic.



Mitigations:



\- Redis-backed rate limiting

\- health/readiness checks

\- bounded worker execution

\- indexed queries

\- container health checks



### Privilege Escalation



A lower-privileged user may attempt administrative actions.



Mitigations:



\- explicit RBAC dependencies

\- service-level role checks

\- ownership validation

\- audit logging



### Dependency Vulnerabilities



A vulnerable library may expose the service.



Mitigations:



\- pinned dependency lock file

\- automated pip-audit scanning

\- dependency upgrades

\- CI enforcement



## Encryption



Production requirements:



\- TLS for network traffic

\- encrypted database storage

\- encrypted backups

\- managed secret/KMS storage

\- encrypted MFA secret storage



Cryptographic keys must never be committed to source control.



## Secrets Management



`.env` is excluded from Git.



`.env.example` contains configuration placeholders only.



Production secrets should be provided through a secret manager or deployment platform.



The CI workflow uses test-only configuration values and must never be used as production credentials.



## Audit Logging



Security-sensitive operations generate audit events.



Audit records capture controlled information such as:



\- actor

\- action

\- resource

\- event time

\- request ID

\- IP address when available

\- outcome

\- controlled metadata



Audit records should be append-oriented and access-controlled in production.



## Key Rotation



Production rotation should cover:



\- JWT signing keys

\- MFA encryption keys

\- database credentials

\- Redis credentials

\- cloud/KMS credentials



Rotation procedures should support controlled migration and emergency revocation.



## Security Checklist



\- \[x] Password hashing

\- \[x] MFA

\- \[x] RBAC

\- \[x] Ownership checks

\- \[x] Rate limiting

\- \[x] Input validation

\- \[x] Booking idempotency

\- \[x] Audit logging

\- \[x] Security headers

\- \[x] Dependency scanning

\- \[x] Secrets excluded from Git

\- \[x] Refresh-token rotation

\- \[x] Login lockout

\- \[ ] Production WAF configuration

\- \[ ] External KMS integration

\- \[ ] Formal penetration test

\- \[ ] Production load test



Unchecked items are production deployment or verification activities and are not claimed as completed implementation features.


# Amrutam Telemedicine Backend - Operations and Disaster Recovery



## Service Endpoints



### Liveness



`GET /health`



Expected response:



```json

{"status":"healthy"}

Readiness



GET /ready



Expected response:



{

&#x20; "status": "ready",

&#x20; "dependencies": {

&#x20;   "postgres": "ok",

&#x20;   "redis": "ok"

&#x20; }

}



Readiness returns failure when required dependencies are unavailable.



Metrics



GET /metrics



Prometheus-compatible HTTP metrics are exposed.



Local Container Topology



Docker Compose runs:



PostgreSQL

Redis

FastAPI API

Celery worker



The API is exposed on port 8000 for local verification.



Deployment Strategy



Production should run multiple stateless API replicas behind a load balancer.



Recommended production dependencies:



managed PostgreSQL

managed Redis

external secret manager

container orchestration

centralized logs

Prometheus-compatible metrics backend

OpenTelemetry collector

Database Migrations



Alembic manages schema migrations.



Recommended deployment sequence:



Build the new application image.

Run compatible database migrations.

Start new application instances.

Verify readiness.

Shift traffic.

Monitor errors and latency.



Destructive changes should follow an expand/contract migration strategy.



Backup Strategy



Production PostgreSQL should use:



encrypted automated backups

point-in-time recovery

defined retention

off-host backup copies

cross-zone or cross-region recovery where required



Redis data should be classified by workload.



Rate-limit state may be recreated, while queued asynchronous work requires an appropriate durability strategy.



Recovery Objectives



Target objectives:



RPO <= 15 minutes

RTO <= 60 minutes



These are engineering targets and must be validated by real recovery drills.



Restore Runbook

Provision a clean PostgreSQL target.

Restore the latest valid backup.

Apply required migrations.

Validate critical tables and indexes.

Start the API against the restored database.

Verify /health.

Verify /ready.

Verify authentication.

Verify consultation and prescription data.

Verify audit records.

Resume background workers.

Record recovery duration and discrepancies.

Incident Response



For elevated latency or error rates:



Check API liveness and readiness.

Check HTTP error-rate metrics.

Check p95/p99 latency.

Check PostgreSQL connections and saturation.

Check Redis availability.

Check Celery worker status and queue depth.

Search structured logs using request IDs.

Roll back a bad deployment when regression is confirmed.

Preserve relevant audit and incident evidence.

Alerting Recommendations



Alert on:



sustained HTTP 5xx rate

p95/p99 latency threshold breaches

readiness failures

PostgreSQL saturation

connection pool exhaustion

Redis failures

Celery queue growth

abnormal login failures

repeated rate-limit violations

Secret Management



Production secrets must come from a managed secret store or deployment platform.



Never commit .env files, credentials, JWT signing secrets, encryption keys or database passwords to Git.



Rotate compromised credentials immediately.



Security Operations



Authentication and authorization controls should be monitored for abuse.



Audit events should be retained according to the organization's compliance and retention requirements.



Access to clinical and audit data should follow least privilege.



Current Validation



Validated locally:



API /health

API /ready

PostgreSQL readiness

Redis readiness

Celery worker startup

automated tests

dependency vulnerability audit

Docker container health



Not yet formally exercised:



100k consultation load testing

production disaster-recovery drill

production multi-region failover

live external tracing backend

real payment gateway integration


# Amrutam Telemedicine Backend — Architecture



## 1. System Overview



The backend is a modular FastAPI service designed for secure and scalable telemedicine workflows.



Core components:



\- FastAPI REST API

\- PostgreSQL system-of-record database

\- Redis for rate limiting and Celery transport/backend

\- Celery worker for asynchronous jobs

\- SQLAlchemy async ORM

\- Alembic database migrations

\- Prometheus metrics

\- OpenTelemetry-compatible tracing

\- Docker Compose containerization



## 2. Core Data Flow



Authentication validates credentials, lockout state and MFA requirements before issuing short-lived access tokens and rotating refresh sessions.



Read operations use typed validation, indexed database queries and pagination.



Write operations pass through service-layer validation, authorization and transaction boundaries.



Sensitive business changes produce audit events.



## 3. Booking Sequence



```mermaid

sequenceDiagram

&#x20;   participant P as Patient

&#x20;   participant API as FastAPI

&#x20;   participant I as Idempotency

&#x20;   participant DB as PostgreSQL

&#x20;   participant A as Audit



&#x20;   P->>API: POST /consultations

&#x20;   API->>API: Authenticate + authorize

&#x20;   API->>API: Build request hash

&#x20;   API->>I: Lookup idempotency key



&#x20;   alt Existing completed request

&#x20;       I-->>API: Stored response

&#x20;       API-->>P: Replay response

&#x20;   else New request

&#x20;       API->>I: Create pending record

&#x20;       API->>DB: Lock availability slot

&#x20;       API->>DB: Validate slot

&#x20;       API->>DB: Create consultation

&#x20;       API->>DB: Mark slot booked

&#x20;       API->>A: Write audit event

&#x20;       API->>I: Store final response

&#x20;       API->>DB: Commit transaction

&#x20;       API-->>P: 201 Created

&#x20;   end                       

4\. Entity Relationships

&#x20;|

&#x20;+---- profiles

&#x20;|

&#x20;+---- doctors

&#x20;|       |

&#x20;|       +---- availability\_slots

&#x20;|                 |

&#x20;|                 +---- consultations

&#x20;|                           |

&#x20;|                           +---- prescriptions

&#x20;|                           |

&#x20;|                           +---- payments

&#x20;|

&#x20;+---- audit\_logs

&#x20;|

&#x20;+---- idempotency\_records

&#x20;Integrity rules include unique doctor licensing, one consultation per availability slot, one prescription per consultation, unique payment provider references and unique idempotency keys per user and operation.



5\. Concurrency and Idempotency



Booking uses persistent idempotency records together with PostgreSQL row locking.



A repeated request with the same idempotency key and identical payload replays the original result.



The same key with a different request payload is rejected.



The availability row is locked before the booking transaction changes the slot from available to booked.



Consultation creation, slot transition, idempotency completion and audit creation are committed atomically.



6\. Transaction Management



Business state changes occur inside database transactions.



The system avoids holding database transactions open while waiting for remote external services.



Background work is delegated to Celery where asynchronous execution is appropriate.



Failed transactions roll back rather than leaving partial business state.



7\. Retry and Backoff



Background tasks use bounded retries with exponential backoff and jitter.



Retryable operations must be safe to replay.



Business writes use idempotency protection where duplicate execution could create inconsistent state.



8\. Caching and Redis



Redis currently supports:



distributed rate limiting

Celery broker/backend functionality



PostgreSQL remains the source of truth.



Production deployments can introduce short-lived read-through caching for low-volatility doctor/search responses with explicit invalidation.



9\. Scalability



The assignment target is 100,000 daily consultations.



Production scaling strategy:



stateless API replicas behind a load balancer

PostgreSQL connection pooling

read replicas for suitable read workloads

Redis managed service or cluster

horizontally scaled Celery workers

indexed consultation and availability queries

time-based partitioning for high-volume audit/event data when required

10\. Reliability and Availability



Target service availability is 99.95%.



The API exposes:



/health for liveness

/ready for dependency readiness



Readiness checks PostgreSQL and Redis.



Container orchestration can remove unhealthy API instances from traffic.



11\. Observability



Current implementation provides:



structured request logging

request IDs

Prometheus HTTP metrics

liveness/readiness probes

OpenTelemetry-compatible instrumentation hooks



Production monitoring should alert on elevated 5xx rate, p95/p99 latency, database saturation, Redis failures, worker queue growth and authentication abuse.



12\. Disaster Recovery



Production PostgreSQL should use encrypted automated backups and point-in-time recovery.



Recommended targets:



RPO <= 15 minutes

RTO <= 60 minutes



Recovery must be verified through regular restore drills.



Redis rate-limit state can be rebuilt, while queued background work requires an appropriate durable recovery strategy.



13\. Known Validation Gaps



The implementation is production-oriented but has not been formally load-tested at the full 100,000-consultation target.



Concurrent availability creation can still require a PostgreSQL exclusion constraint or stronger serialization strategy to eliminate every possible overlap race.



Real payment-provider integration, live OTLP infrastructure and multi-region disaster recovery are deployment-stage concerns and are not claimed as locally exercised features.

'@ | Set-Content .\\docs\\ARCHITECTURE.md





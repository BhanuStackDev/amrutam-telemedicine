from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class StatusCount(BaseModel):
    status: str
    count: int


class RoleCount(BaseModel):
    role: str
    count: int


class UserAnalytics(BaseModel):
    total: int
    by_role: list[RoleCount]
    by_status: list[StatusCount]


class DoctorAnalytics(BaseModel):
    total: int
    verified: int
    accepting_patients: int


class ConsultationAnalytics(BaseModel):
    total: int
    by_status: list[StatusCount]


class PaymentAnalytics(BaseModel):
    total: int
    succeeded: int
    failed: int
    pending: int
    refunded: int
    gross_succeeded_amount: Decimal
    refunded_amount: Decimal
    currency: str = "INR"


class PrescriptionAnalytics(BaseModel):
    total: int


class AuditAnalytics(BaseModel):
    total_events: int
    successful_events: int
    failed_events: int


class AdminAnalyticsResponse(BaseModel):
    users: UserAnalytics
    doctors: DoctorAnalytics
    consultations: ConsultationAnalytics
    prescriptions: PrescriptionAnalytics
    payments: PaymentAnalytics
    audit: AuditAnalytics


class AuditLogResponse(BaseModel):
    id: str
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    event_time: str
    ip_address: str | None
    request_id: str | None
    event_metadata: dict | None
    outcome: str


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)

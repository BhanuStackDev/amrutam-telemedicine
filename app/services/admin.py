from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.consultation import Consultation, ConsultationStatus
from app.models.doctor import Doctor
from app.models.payment import Payment, PaymentStatus
from app.models.prescription import Prescription
from app.models.user import User, UserRole, UserStatus
from app.schemas.admin import (
    AdminAnalyticsResponse,
    AuditAnalytics,
    AuditLogListResponse,
    AuditLogResponse,
    ConsultationAnalytics,
    DoctorAnalytics,
    PaymentAnalytics,
    PrescriptionAnalytics,
    RoleCount,
    StatusCount,
    UserAnalytics,
)


class AdminService:
    """Administrative analytics and compliance reporting."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _group_counts(
        self,
        model,
        column,
    ) -> list[tuple[str, int]]:
        result = await self.db.execute(
            select(
                column,
                func.count(),
            )
            .select_from(model)
            .group_by(column)
            .order_by(column)
        )

        return [
            (
                str(value.value if hasattr(value, "value") else value),
                int(count),
            )
            for value, count in result.all()
        ]

    async def get_analytics(self) -> AdminAnalyticsResponse:
        user_total = int(
            await self.db.scalar(
                select(func.count()).select_from(User)
            )
            or 0
        )

        user_role_counts = await self._group_counts(
            User,
            User.role,
        )

        user_status_counts = await self._group_counts(
            User,
            User.status,
        )

        doctor_total = int(
            await self.db.scalar(
                select(func.count()).select_from(Doctor)
            )
            or 0
        )

        doctor_verified = int(
            await self.db.scalar(
                select(func.count())
                .select_from(Doctor)
                .where(Doctor.is_verified.is_(True))
            )
            or 0
        )

        doctor_accepting = int(
            await self.db.scalar(
                select(func.count())
                .select_from(Doctor)
                .where(Doctor.is_accepting_patients.is_(True))
            )
            or 0
        )

        consultation_total = int(
            await self.db.scalar(
                select(func.count()).select_from(Consultation)
            )
            or 0
        )

        consultation_status_counts = await self._group_counts(
            Consultation,
            Consultation.status,
        )

        prescription_total = int(
            await self.db.scalar(
                select(func.count()).select_from(Prescription)
            )
            or 0
        )

        payment_total = int(
            await self.db.scalar(
                select(func.count()).select_from(Payment)
            )
            or 0
        )

        payment_status_counts = dict(
            await self._group_counts(
                Payment,
                Payment.status,
            )
        )

        succeeded_amount = (
            await self.db.scalar(
                select(
                    func.coalesce(
                        func.sum(Payment.amount),
                        Decimal("0.00"),
                    )
                )
                .select_from(Payment)
                .where(
                    Payment.status
                    == PaymentStatus.SUCCEEDED
                )
            )
            or Decimal("0.00")
        )

        refunded_amount = (
            await self.db.scalar(
                select(
                    func.coalesce(
                        func.sum(Payment.amount),
                        Decimal("0.00"),
                    )
                )
                .select_from(Payment)
                .where(
                    Payment.status
                    == PaymentStatus.REFUNDED
                )
            )
            or Decimal("0.00")
        )

        audit_total = int(
            await self.db.scalar(
                select(func.count()).select_from(AuditLog)
            )
            or 0
        )

        audit_success = int(
            await self.db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.outcome == "success")
            )
            or 0
        )

        audit_failed = int(
            await self.db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.outcome != "success")
            )
            or 0
        )

        return AdminAnalyticsResponse(
            users=UserAnalytics(
                total=user_total,
                by_role=[
                    RoleCount(
                        role=role,
                        count=count,
                    )
                    for role, count in user_role_counts
                ],
                by_status=[
                    StatusCount(
                        status=status,
                        count=count,
                    )
                    for status, count in user_status_counts
                ],
            ),
            doctors=DoctorAnalytics(
                total=doctor_total,
                verified=doctor_verified,
                accepting_patients=doctor_accepting,
            ),
            consultations=ConsultationAnalytics(
                total=consultation_total,
                by_status=[
                    StatusCount(
                        status=status,
                        count=count,
                    )
                    for status, count in consultation_status_counts
                ],
            ),
            prescriptions=PrescriptionAnalytics(
                total=prescription_total,
            ),
            payments=PaymentAnalytics(
                total=payment_total,
                succeeded=payment_status_counts.get(
                    PaymentStatus.SUCCEEDED.value,
                    0,
                ),
                failed=payment_status_counts.get(
                    PaymentStatus.FAILED.value,
                    0,
                ),
                pending=payment_status_counts.get(
                    PaymentStatus.PENDING.value,
                    0,
                )
                + payment_status_counts.get(
                    PaymentStatus.PROCESSING.value,
                    0,
                ),
                refunded=payment_status_counts.get(
                    PaymentStatus.REFUNDED.value,
                    0,
                ),
                gross_succeeded_amount=succeeded_amount,
                refunded_amount=refunded_amount,
            ),
            audit=AuditAnalytics(
                total_events=audit_total,
                successful_events=audit_success,
                failed_events=audit_failed,
            ),
        )

    async def list_audit_logs(
        self,
        *,
        action: str | None,
        resource_type: str | None,
        outcome: str | None,
        limit: int,
        offset: int,
    ) -> AuditLogListResponse:
        conditions = []

        if action:
            conditions.append(
                AuditLog.action == action.strip()
            )

        if resource_type:
            conditions.append(
                AuditLog.resource_type
                == resource_type.strip()
            )

        if outcome:
            conditions.append(
                AuditLog.outcome == outcome.strip()
            )

        total = int(
            await self.db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(*conditions)
            )
            or 0
        )

        result = await self.db.execute(
            select(AuditLog)
            .where(*conditions)
            .order_by(
                AuditLog.event_time.desc()
            )
            .limit(limit)
            .offset(offset)
        )

        items = [
            AuditLogResponse(
                id=str(log.id),
                actor_user_id=(
                    str(log.actor_user_id)
                    if log.actor_user_id
                    else None
                ),
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                event_time=log.event_time.isoformat(),
                ip_address=log.ip_address,
                request_id=log.request_id,
                event_metadata=log.event_metadata,
                outcome=log.outcome,
            )
            for log in result.scalars().all()
        ]

        return AuditLogListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

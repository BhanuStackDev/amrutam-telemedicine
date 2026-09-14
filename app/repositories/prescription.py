from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prescription import Prescription


class PrescriptionRepository:
    """Database access layer for prescriptions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(
        self,
        prescription_id: UUID,
    ) -> Prescription | None:
        result = await self.db.execute(
            select(Prescription).where(
                Prescription.id == prescription_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_consultation(
        self,
        consultation_id: UUID,
    ) -> Prescription | None:
        result = await self.db.execute(
            select(Prescription).where(
                Prescription.consultation_id == consultation_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        prescription: Prescription,
    ) -> Prescription:
        self.db.add(prescription)
        await self.db.flush()
        await self.db.refresh(prescription)
        return prescription

    async def list_for_patient(
        self,
        patient_id: UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Prescription], int]:
        count_result = await self.db.execute(
            select(func.count(Prescription.id)).where(
                Prescription.patient_id == patient_id,
            )
        )
        total = int(count_result.scalar_one())

        result = await self.db.execute(
            select(Prescription)
            .where(
                Prescription.patient_id == patient_id,
            )
            .order_by(
                Prescription.issued_on.desc(),
                Prescription.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all()), total

    async def list_for_doctor(
        self,
        doctor_id: UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Prescription], int]:
        count_result = await self.db.execute(
            select(func.count(Prescription.id)).where(
                Prescription.doctor_id == doctor_id,
            )
        )
        total = int(count_result.scalar_one())

        result = await self.db.execute(
            select(Prescription)
            .where(
                Prescription.doctor_id == doctor_id,
            )
            .order_by(
                Prescription.issued_on.desc(),
                Prescription.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all()), total

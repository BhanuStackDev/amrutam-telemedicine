from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AvailabilitySlot, Consultation, ConsultationStatus


class ConsultationRepository:
    """Data-access layer for consultation records."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(
        self,
        consultation_id: UUID,
        *,
        for_update: bool = False,
    ) -> Consultation | None:
        """Fetch a consultation by ID, optionally with a row lock."""

        query = select(Consultation).where(
            Consultation.id == consultation_id
        )

        if for_update:
            query = query.with_for_update()

        return await self.db.scalar(query)

    async def get_by_slot(
        self,
        availability_slot_id: UUID,
        *,
        for_update: bool = False,
    ) -> Consultation | None:
        """Fetch the consultation associated with a slot."""

        query = select(Consultation).where(
            Consultation.availability_slot_id
            == availability_slot_id
        )

        if for_update:
            query = query.with_for_update()

        return await self.db.scalar(query)

    async def create(
        self,
        consultation: Consultation,
    ) -> Consultation:
        """Persist a new consultation."""

        self.db.add(consultation)
        await self.db.flush()
        await self.db.refresh(consultation)

        return consultation

    async def update(
        self,
        consultation: Consultation,
    ) -> Consultation:
        """Persist changes to a consultation."""

        await self.db.flush()
        await self.db.refresh(consultation)

        return consultation

    async def list_for_patient(
        self,
        patient_id: UUID,
        *,
        status: ConsultationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Consultation], int]:
        """Return paginated consultations for a patient."""

        filters = [
            Consultation.patient_id == patient_id,
        ]

        if status is not None:
            filters.append(
                Consultation.status == status
            )

        count_query = (
            select(func.count())
            .select_from(Consultation)
            .where(*filters)
        )

        total = int(
            await self.db.scalar(count_query) or 0
        )

        query = (
            select(Consultation)
            .where(*filters)
            .order_by(
                Consultation.scheduled_start.desc()
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.scalars(query)

        return list(result.all()), total

    async def list_for_doctor(
        self,
        doctor_id: UUID,
        *,
        status: ConsultationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Consultation], int]:
        """Return paginated consultations for a doctor."""

        filters = [
            Consultation.doctor_id == doctor_id,
        ]

        if status is not None:
            filters.append(
                Consultation.status == status
            )

        count_query = (
            select(func.count())
            .select_from(Consultation)
            .where(*filters)
        )

        total = int(
            await self.db.scalar(count_query) or 0
        )

        query = (
            select(Consultation)
            .where(*filters)
            .order_by(
                Consultation.scheduled_start.desc()
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.scalars(query)

        return list(result.all()), total

    async def get_slot_for_update(
        self,
        slot_id: UUID,
    ) -> AvailabilitySlot | None:
        """
        Lock an availability slot for the booking transaction.

        This is the critical concurrency boundary for preventing
        double booking.
        """

        query = (
            select(AvailabilitySlot)
            .where(
                AvailabilitySlot.id == slot_id
            )
            .with_for_update()
        )

        return await self.db.scalar(query)

    async def exists_for_patient_slot(
        self,
        patient_id: UUID,
        availability_slot_id: UUID,
    ) -> bool:
        """Check whether a patient already booked a specific slot."""

        query = (
            select(Consultation.id)
            .where(
                Consultation.patient_id == patient_id,
                Consultation.availability_slot_id
                == availability_slot_id,
            )
            .limit(1)
        )

        return (
            await self.db.scalar(query)
        ) is not None

    async def count_active_for_slot(
        self,
        availability_slot_id: UUID,
    ) -> int:
        """
        Count non-cancelled/non-no-show consultations for a slot.

        The database also enforces a unique slot relationship, so this
        method is primarily useful for validation and diagnostics.
        """

        query = (
            select(func.count())
            .select_from(Consultation)
            .where(
                Consultation.availability_slot_id
                == availability_slot_id,
                Consultation.status.not_in(
                    [
                        ConsultationStatus.CANCELLED,
                        ConsultationStatus.NO_SHOW,
                    ]
                ),
            )
        )

        return int(
            await self.db.scalar(query) or 0
        )

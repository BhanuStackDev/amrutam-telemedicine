from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AvailabilitySlot, SlotStatus


class AvailabilityRepository:
    """Data-access layer for doctor availability slots."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(
        self,
        slot_id: UUID,
        *,
        for_update: bool = False,
    ) -> AvailabilitySlot | None:
        """Fetch a slot by ID, optionally taking a row lock."""

        query = select(AvailabilitySlot).where(
            AvailabilitySlot.id == slot_id
        )

        if for_update:
            query = query.with_for_update()

        return await self.db.scalar(query)

    async def create(
        self,
        slot: AvailabilitySlot,
    ) -> AvailabilitySlot:
        """Persist a new availability slot."""

        self.db.add(slot)
        await self.db.flush()
        await self.db.refresh(slot)

        return slot

    async def update(
        self,
        slot: AvailabilitySlot,
    ) -> AvailabilitySlot:
        """Persist changes to an existing slot."""

        await self.db.flush()
        await self.db.refresh(slot)

        return slot

    async def delete(
        self,
        slot: AvailabilitySlot,
    ) -> None:
        """Delete an availability slot."""

        await self.db.delete(slot)
        await self.db.flush()

    async def list_for_doctor(
        self,
        doctor_id: UUID,
        *,
        starts_from: datetime | None = None,
        starts_until: datetime | None = None,
        status: SlotStatus | None = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AvailabilitySlot], int]:
        """Return filtered and paginated slots for a doctor."""

        filters = [
            AvailabilitySlot.doctor_id == doctor_id,
        ]

        if starts_from is not None:
            filters.append(
                AvailabilitySlot.starts_at >= starts_from
            )

        if starts_until is not None:
            filters.append(
                AvailabilitySlot.starts_at < starts_until
            )

        if status is not None:
            filters.append(
                AvailabilitySlot.status == status
            )

        if active_only:
            filters.append(
                AvailabilitySlot.is_active.is_(True)
            )

        count_query = (
            select(func.count())
            .select_from(AvailabilitySlot)
            .where(*filters)
        )

        total = int(
            await self.db.scalar(count_query) or 0
        )

        query = (
            select(AvailabilitySlot)
            .where(*filters)
            .order_by(
                AvailabilitySlot.starts_at.asc()
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.scalars(query)

        return list(result.all()), total

    async def find_overlapping_slot(
        self,
        doctor_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        *,
        exclude_slot_id: UUID | None = None,
        active_only: bool = True,
    ) -> AvailabilitySlot | None:
        """
        Find an existing slot that overlaps the requested interval.

        Overlap rule:
            existing.starts_at < requested.ends_at
            AND
            existing.ends_at > requested.starts_at
        """

        filters = [
            AvailabilitySlot.doctor_id == doctor_id,
            AvailabilitySlot.starts_at < ends_at,
            AvailabilitySlot.ends_at > starts_at,
        ]

        if active_only:
            filters.append(
                AvailabilitySlot.is_active.is_(True)
            )

        if exclude_slot_id is not None:
            filters.append(
                AvailabilitySlot.id != exclude_slot_id
            )

        query = (
            select(AvailabilitySlot)
            .where(and_(*filters))
            .order_by(
                AvailabilitySlot.starts_at.asc()
            )
            .limit(1)
        )

        return await self.db.scalar(query)

    async def find_overlapping_available_slot(
        self,
        doctor_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        *,
        exclude_slot_id: UUID | None = None,
    ) -> AvailabilitySlot | None:
        """Find an overlapping slot that is currently bookable."""

        filters = [
            AvailabilitySlot.doctor_id == doctor_id,
            AvailabilitySlot.starts_at < ends_at,
            AvailabilitySlot.ends_at > starts_at,
            AvailabilitySlot.status == SlotStatus.AVAILABLE,
            AvailabilitySlot.is_active.is_(True),
        ]

        if exclude_slot_id is not None:
            filters.append(
                AvailabilitySlot.id != exclude_slot_id
            )

        query = (
            select(AvailabilitySlot)
            .where(and_(*filters))
            .order_by(
                AvailabilitySlot.starts_at.asc()
            )
            .limit(1)
            .with_for_update()
        )

        return await self.db.scalar(query)

    async def exists_exact_interval(
        self,
        doctor_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        *,
        exclude_slot_id: UUID | None = None,
    ) -> bool:
        """Check whether an exact doctor interval already exists."""

        filters = [
            AvailabilitySlot.doctor_id == doctor_id,
            AvailabilitySlot.starts_at == starts_at,
            AvailabilitySlot.ends_at == ends_at,
        ]

        if exclude_slot_id is not None:
            filters.append(
                AvailabilitySlot.id != exclude_slot_id
            )

        query = (
            select(AvailabilitySlot.id)
            .where(*filters)
            .limit(1)
        )

        return (
            await self.db.scalar(query)
        ) is not None

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Doctor


class DoctorRepository:
    """Data-access layer for doctor records."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, doctor_id: UUID) -> Doctor | None:
        """Fetch a doctor by primary key."""
        return await self.db.scalar(
            select(Doctor).where(Doctor.id == doctor_id)
        )

    async def get_by_user_id(self, user_id: UUID) -> Doctor | None:
        """Fetch a doctor profile by its linked user."""
        return await self.db.scalar(
            select(Doctor).where(Doctor.user_id == user_id)
        )

    async def get_by_license_number(
        self,
        license_number: str,
    ) -> Doctor | None:
        """Fetch a doctor by unique license number."""
        return await self.db.scalar(
            select(Doctor).where(
                Doctor.license_number == license_number
            )
        )

    async def create(self, doctor: Doctor) -> Doctor:
        """Persist a new doctor."""
        self.db.add(doctor)
        await self.db.flush()
        await self.db.refresh(doctor)
        return doctor

    async def update(self, doctor: Doctor) -> Doctor:
        """Persist changes to an existing doctor."""
        await self.db.flush()
        await self.db.refresh(doctor)
        return doctor

    async def delete(self, doctor: Doctor) -> None:
        """Delete a doctor record."""
        await self.db.delete(doctor)
        await self.db.flush()

    async def list_doctors(
        self,
        *,
        specialization: str | None = None,
        verified_only: bool = False,
        accepting_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Doctor], int]:
        """Return filtered and paginated doctors with total count."""

        filters = []

        if specialization:
            filters.append(
                func.lower(Doctor.specialization)
                == specialization.strip().lower()
            )

        if verified_only:
            filters.append(Doctor.is_verified.is_(True))

        if accepting_only:
            filters.append(Doctor.is_accepting_patients.is_(True))

        count_query = select(func.count()).select_from(Doctor)

        if filters:
            count_query = count_query.where(*filters)

        total = int(await self.db.scalar(count_query) or 0)

        query = (
            select(Doctor)
            .where(*filters)
            .order_by(
                Doctor.is_verified.desc(),
                Doctor.is_accepting_patients.desc(),
                Doctor.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.scalars(query)

        return list(result.all()), total

    async def exists_for_user(
        self,
        user_id: UUID,
    ) -> bool:
        """Check whether a doctor profile already exists for a user."""
        query = select(Doctor.id).where(Doctor.user_id == user_id).limit(1)

        return (await self.db.scalar(query)) is not None

    async def exists_for_license(
        self,
        license_number: str,
        *,
        exclude_doctor_id: UUID | None = None,
    ) -> bool:
        """Check whether a license is already registered."""
        query = select(Doctor.id).where(
            Doctor.license_number == license_number
        )

        if exclude_doctor_id is not None:
            query = query.where(Doctor.id != exclude_doctor_id)

        return (await self.db.scalar(query)) is not None
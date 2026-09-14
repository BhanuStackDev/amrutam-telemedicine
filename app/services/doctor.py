from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Doctor, User, UserRole
from app.repositories.doctor import DoctorRepository
from app.schemas.doctor import DoctorCreateRequest, DoctorUpdateRequest


class DoctorService:
    """Business logic for doctor management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = DoctorRepository(db)

    async def create_doctor(
        self,
        payload: DoctorCreateRequest,
    ) -> Doctor:
        """Create a doctor profile for an existing doctor-role user."""

        user = await self.db.get(User, payload.user_id)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if user.role != UserRole.DOCTOR:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must have doctor role",
            )

        existing_profile = await self.repository.get_by_user_id(
            payload.user_id
        )

        if existing_profile is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Doctor profile already exists for this user",
            )

        license_number = payload.license_number.strip()

        existing_license = await self.repository.get_by_license_number(
            license_number
        )

        if existing_license is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="License number is already registered",
            )

        doctor = Doctor(
            user_id=payload.user_id,
            license_number=license_number,
            specialization=payload.specialization.strip(),
            qualification=payload.qualification.strip(),
            experience_years=payload.experience_years,
            consultation_fee=payload.consultation_fee,
            bio=payload.bio,
            is_verified=payload.is_verified,
            is_accepting_patients=payload.is_accepting_patients,
        )

        await self.repository.create(doctor)

        await self.db.commit()
        await self.db.refresh(doctor)

        return doctor

    async def get_doctor(
        self,
        doctor_id: UUID,
    ) -> Doctor:
        """Fetch a doctor or raise 404."""

        doctor = await self.repository.get_by_id(doctor_id)

        if doctor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found",
            )

        return doctor

    async def get_doctor_for_user(
        self,
        user_id: UUID,
    ) -> Doctor:
        """Fetch the doctor profile linked to a user."""

        doctor = await self.repository.get_by_user_id(user_id)

        if doctor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found",
            )

        return doctor

    async def list_doctors(
        self,
        *,
        specialization: str | None = None,
        verified_only: bool = False,
        accepting_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Doctor], int]:
        """Return filtered and paginated doctor profiles."""

        return await self.repository.list_doctors(
            specialization=specialization,
            verified_only=verified_only,
            accepting_only=accepting_only,
            limit=limit,
            offset=offset,
        )

    async def update_doctor(
        self,
        doctor_id: UUID,
        payload: DoctorUpdateRequest,
    ) -> Doctor:
        """Apply a partial update to a doctor profile."""

        doctor = await self.get_doctor(doctor_id)

        update_data = payload.model_dump(exclude_unset=True)

        if "license_number" in update_data:
            license_number = update_data["license_number"].strip()

            if (
                await self.repository.exists_for_license(
                    license_number,
                    exclude_doctor_id=doctor.id,
                )
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="License number is already registered",
                )

            update_data["license_number"] = license_number

        for field_name, value in update_data.items():
            setattr(doctor, field_name, value)

        await self.repository.update(doctor)

        await self.db.commit()
        await self.db.refresh(doctor)

        return doctor

    async def delete_doctor(
        self,
        doctor_id: UUID,
    ) -> None:
        """Delete a doctor profile when referential constraints permit."""

        doctor = await self.get_doctor(doctor_id)

        try:
            await self.repository.delete(doctor)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Doctor cannot be deleted because related records "
                    "already exist"
                ),
            )
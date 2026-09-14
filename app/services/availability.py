from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AvailabilitySlot, Doctor, SlotStatus
from app.repositories.availability import AvailabilityRepository
from app.repositories.doctor import DoctorRepository
from app.schemas.availability import (
    AvailabilitySlotCreateRequest,
    AvailabilitySlotUpdateRequest,
)


class AvailabilityService:
    """Business logic for doctor availability management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.availability_repo = AvailabilityRepository(db)
        self.doctor_repo = DoctorRepository(db)

    @staticmethod
    def _ensure_timezone_aware(value: datetime, field_name: str) -> None:
        """Require timezone-aware datetimes."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field_name} must include timezone information.",
            )

    @staticmethod
    def _normalize_to_utc(value: datetime) -> datetime:
        """Normalize an aware datetime to UTC."""

        return value.astimezone(timezone.utc)

    async def _get_doctor_for_user(
        self,
        user_id: UUID,
    ) -> Doctor:
        """Resolve a doctor profile from the authenticated user."""

        doctor = await self.doctor_repo.get_by_user_id(user_id)

        if doctor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found.",
            )

        return doctor

    @staticmethod
    def _validate_interval(
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        """Validate the requested availability interval."""

        if ends_at <= starts_at:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="ends_at must be later than starts_at.",
            )

    @staticmethod
    def _validate_future_slot(
        starts_at: datetime,
    ) -> None:
        """Prevent creation of slots in the past."""

        now = datetime.now(timezone.utc)

        if starts_at <= now:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Availability slot must start in the future.",
            )

    @staticmethod
    def _validate_slot_duration(
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        """Keep slot duration within a practical scheduling range."""

        duration_seconds = (
            ends_at - starts_at
        ).total_seconds()

        # Minimum 5 minutes, maximum 4 hours.
        if duration_seconds < 5 * 60:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Availability slot must be at least 5 minutes long.",
            )

        if duration_seconds > 4 * 60 * 60:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Availability slot cannot exceed 4 hours.",
            )

    async def create_for_user(
        self,
        user_id: UUID,
        payload: AvailabilitySlotCreateRequest,
    ) -> AvailabilitySlot:
        """Create a new availability slot for the authenticated doctor."""

        doctor = await self._get_doctor_for_user(user_id)

        if not doctor.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Verified doctor profile is required to create availability.",
            )

        if not doctor.is_accepting_patients:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Doctor is not currently accepting patients.",
            )

        self._ensure_timezone_aware(
            payload.starts_at,
            "starts_at",
        )
        self._ensure_timezone_aware(
            payload.ends_at,
            "ends_at",
        )

        starts_at = self._normalize_to_utc(
            payload.starts_at
        )
        ends_at = self._normalize_to_utc(
            payload.ends_at
        )

        self._validate_interval(
            starts_at,
            ends_at,
        )

        self._validate_future_slot(
            starts_at
        )

        self._validate_slot_duration(
            starts_at,
            ends_at,
        )

        existing_slot = (
            await self.availability_repo.find_overlapping_slot(
                doctor.id,
                starts_at,
                ends_at,
                active_only=True,
            )
        )

        if existing_slot is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Availability slot overlaps an existing active slot.",
            )

        slot = AvailabilitySlot(
            doctor_id=doctor.id,
            starts_at=starts_at,
            ends_at=ends_at,
            status=SlotStatus.AVAILABLE,
            is_active=True,
        )

        try:
            await self.availability_repo.create(slot)
            await self.db.commit()
            await self.db.refresh(slot)
            return slot

        except IntegrityError:
            await self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Availability slot conflicts with an existing slot.",
            )

        except Exception:
            await self.db.rollback()
            raise

    async def get_slot(
        self,
        slot_id: UUID,
    ) -> AvailabilitySlot:
        """Fetch an availability slot."""

        slot = await self.availability_repo.get_by_id(
            slot_id
        )

        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability slot not found.",
            )

        return slot

    async def get_slot_for_user(
        self,
        user_id: UUID,
        slot_id: UUID,
    ) -> AvailabilitySlot:
        """Fetch a slot while enforcing doctor ownership."""

        doctor = await self._get_doctor_for_user(
            user_id
        )

        slot = await self.availability_repo.get_by_id(
            slot_id
        )

        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability slot not found.",
            )

        if slot.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this availability slot.",
            )

        return slot

    async def list_for_doctor(
        self,
        doctor_id: UUID,
        *,
        starts_from: datetime | None = None,
        starts_until: datetime | None = None,
        status_filter: SlotStatus | None = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AvailabilitySlot], int]:
        """List a doctor's availability slots."""

        if starts_from is not None:
            self._ensure_timezone_aware(
                starts_from,
                "starts_from",
            )
            starts_from = self._normalize_to_utc(
                starts_from
            )

        if starts_until is not None:
            self._ensure_timezone_aware(
                starts_until,
                "starts_until",
            )
            starts_until = self._normalize_to_utc(
                starts_until
            )

        if (
            starts_from is not None
            and starts_until is not None
            and starts_until <= starts_from
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="starts_until must be later than starts_from.",
            )

        return await self.availability_repo.list_for_doctor(
            doctor_id,
            starts_from=starts_from,
            starts_until=starts_until,
            status=status_filter,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        starts_from: datetime | None = None,
        starts_until: datetime | None = None,
        status_filter: SlotStatus | None = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AvailabilitySlot], int]:
        """List slots belonging to the authenticated doctor."""

        doctor = await self._get_doctor_for_user(
            user_id
        )

        return await self.list_for_doctor(
            doctor.id,
            starts_from=starts_from,
            starts_until=starts_until,
            status_filter=status_filter,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    async def update_for_user(
        self,
        user_id: UUID,
        slot_id: UUID,
        payload: AvailabilitySlotUpdateRequest,
    ) -> AvailabilitySlot:
        """Update an availability slot owned by the doctor."""

        doctor = await self._get_doctor_for_user(
            user_id
        )

        slot = await self.availability_repo.get_by_id(
            slot_id,
            for_update=True,
        )

        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability slot not found.",
            )

        if slot.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this availability slot.",
            )

        # Booked/cancelled/expired slots should not have their
        # schedule interval rewritten.
        interval_fields_changed = (
            payload.starts_at is not None
            or payload.ends_at is not None
        )

        if slot.status == SlotStatus.BOOKED and interval_fields_changed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Booked availability slot cannot have its time changed.",
            )

        if slot.status in {
            SlotStatus.CANCELLED,
            SlotStatus.EXPIRED,
        } and interval_fields_changed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cancelled or expired slot cannot have its time changed.",
            )

        new_starts_at = slot.starts_at
        new_ends_at = slot.ends_at

        if payload.starts_at is not None:
            self._ensure_timezone_aware(
                payload.starts_at,
                "starts_at",
            )
            new_starts_at = self._normalize_to_utc(
                payload.starts_at
            )

        if payload.ends_at is not None:
            self._ensure_timezone_aware(
                payload.ends_at,
                "ends_at",
            )
            new_ends_at = self._normalize_to_utc(
                payload.ends_at
            )

        if interval_fields_changed:
            self._validate_interval(
                new_starts_at,
                new_ends_at,
            )

            self._validate_future_slot(
                new_starts_at
            )

            self._validate_slot_duration(
                new_starts_at,
                new_ends_at,
            )

            overlapping_slot = (
                await self.availability_repo.find_overlapping_slot(
                    doctor.id,
                    new_starts_at,
                    new_ends_at,
                    exclude_slot_id=slot.id,
                    active_only=True,
                )
            )

            if overlapping_slot is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Updated availability slot overlaps an existing active slot.",
                )

            slot.starts_at = new_starts_at
            slot.ends_at = new_ends_at

        if payload.status is not None:
            # Prevent reopening booked/cancelled records through an
            # arbitrary status transition.
            if (
                slot.status == SlotStatus.BOOKED
                and payload.status != SlotStatus.BOOKED
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Booked slot status cannot be changed directly.",
                )

            slot.status = payload.status

        if payload.is_active is not None:
            slot.is_active = payload.is_active

            if not payload.is_active:
                # Deactivating a slot is effectively making it
                # unavailable for future booking.
                if slot.status == SlotStatus.AVAILABLE:
                    slot.status = SlotStatus.CANCELLED

        try:
            await self.availability_repo.update(slot)
            await self.db.commit()
            await self.db.refresh(slot)
            return slot

        except IntegrityError:
            await self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Updated availability slot conflicts with an existing slot.",
            )

        except Exception:
            await self.db.rollback()
            raise

    async def delete_for_user(
        self,
        user_id: UUID,
        slot_id: UUID,
    ) -> None:
        """Deactivate an availability slot instead of hard deleting it."""

        doctor = await self._get_doctor_for_user(
            user_id
        )

        slot = await self.availability_repo.get_by_id(
            slot_id,
            for_update=True,
        )

        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability slot not found.",
            )

        if slot.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this availability slot.",
            )

        if slot.status == SlotStatus.BOOKED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Booked availability slot cannot be deleted.",
            )

        if not slot.is_active:
            # Idempotent delete/deactivation.
            await self.db.commit()
            return

        slot.is_active = False
        slot.status = SlotStatus.CANCELLED

        try:
            await self.db.commit()

        except Exception:
            await self.db.rollback()
            raise

    async def hold_slot(
        self,
        slot_id: UUID,
    ) -> AvailabilitySlot:
        """
        Atomically transition an available slot to HELD.

        Booking will use this operation as a concurrency boundary.
        """

        slot = await self.availability_repo.get_by_id(
            slot_id,
            for_update=True,
        )

        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability slot not found.",
            )

        if not slot.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Availability slot is inactive.",
            )

        if slot.status != SlotStatus.AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Availability slot is not available.",
            )

        now = datetime.now(timezone.utc)

        if slot.starts_at <= now:
            slot.status = SlotStatus.EXPIRED
            slot.is_active = False

            await self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Availability slot has already started or expired.",
            )

        slot.status = SlotStatus.HELD

        try:
            await self.db.commit()
            await self.db.refresh(slot)
            return slot

        except Exception:
            await self.db.rollback()
            raise

    async def release_hold(
        self,
        slot_id: UUID,
    ) -> AvailabilitySlot:
        """Release a held slot back to AVAILABLE."""

        slot = await self.availability_repo.get_by_id(
            slot_id,
            for_update=True,
        )

        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability slot not found.",
            )

        if slot.status != SlotStatus.HELD:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only a held slot can be released.",
            )

        if not slot.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Inactive slot cannot be released.",
            )

        slot.status = SlotStatus.AVAILABLE

        try:
            await self.db.commit()
            await self.db.refresh(slot)
            return slot

        except Exception:
            await self.db.rollback()
            raise

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import AvailabilitySlot, SlotStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.models.doctor import Doctor
from app.models.user import User
from app.repositories.consultation import ConsultationRepository
from app.services.audit import AuditService
from app.services.idempotency import IdempotencyService


class ConsultationService:
    BOOKING_OPERATION = "consultation.book"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ConsultationRepository(db)
        self.audit = AuditService(db)

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _consultation_response_body(
        consultation: Consultation,
    ) -> dict[str, Any]:
        return {
            "id": str(consultation.id),
            "patient_id": str(consultation.patient_id),
            "doctor_id": str(consultation.doctor_id),
            "availability_slot_id": str(
                consultation.availability_slot_id
            ),
            "status": (
                consultation.status.value
                if hasattr(consultation.status, "value")
                else str(consultation.status)
            ),
            "scheduled_start": (
                consultation.scheduled_start.isoformat()
                if consultation.scheduled_start
                else None
            ),
            "scheduled_end": (
                consultation.scheduled_end.isoformat()
                if consultation.scheduled_end
                else None
            ),
            "actual_started_at": (
                consultation.actual_started_at.isoformat()
                if consultation.actual_started_at
                else None
            ),
            "actual_completed_at": (
                consultation.actual_completed_at.isoformat()
                if consultation.actual_completed_at
                else None
            ),
            "clinical_notes": consultation.clinical_notes,
            "cancellation_reason": (
                consultation.cancellation_reason
            ),
            "created_at": (
                consultation.created_at.isoformat()
                if consultation.created_at
                else None
            ),
            "updated_at": (
                consultation.updated_at.isoformat()
                if consultation.updated_at
                else None
            ),
        }

    @staticmethod
    def _booking_payload(
        slot_id: UUID,
    ) -> dict[str, str]:
        return {
            "availability_slot_id": str(slot_id),
        }

    async def book_slot(
        self,
        patient: User,
        availability_slot_id: UUID,
        idempotency_key: str,
    ) -> Consultation | dict[str, Any]:
        """
        Book an available doctor slot with persistent idempotency.

        The successful booking and its audit event are committed
        atomically with the idempotency record.
        """
        if patient.role.value != "patient":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can book consultations.",
            )

        key = IdempotencyService.normalize_key(
            idempotency_key
        )

        request_hash = IdempotencyService.canonical_hash(
            self._booking_payload(
                availability_slot_id
            )
        )

        existing_record = (
            await IdempotencyService.get_existing(
                self.db,
                user_id=patient.id,
                operation=self.BOOKING_OPERATION,
                idempotency_key=key,
            )
        )

        if existing_record is not None:
            IdempotencyService.ensure_same_request(
                existing_record,
                request_hash=request_hash,
            )

            if IdempotencyService.is_completed(
                existing_record
            ):
                _, stored_response = (
                    IdempotencyService.replay_response(
                        existing_record
                    )
                )
                return stored_response

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A request with this idempotency key "
                    "is already being processed."
                ),
            )

        (
            idempotency_record,
            created_by_this_request,
        ) = await IdempotencyService.create_pending(
            self.db,
            user_id=patient.id,
            operation=self.BOOKING_OPERATION,
            idempotency_key=key,
            request_hash=request_hash,
        )

        if not created_by_this_request:
            IdempotencyService.ensure_same_request(
                idempotency_record,
                request_hash=request_hash,
            )

            if IdempotencyService.is_completed(
                idempotency_record
            ):
                _, stored_response = (
                    IdempotencyService.replay_response(
                        idempotency_record
                    )
                )
                return stored_response

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A request with this idempotency key "
                    "is already being processed."
                ),
            )

        try:
            slot = await self.repo.get_slot_for_update(
                availability_slot_id
            )

            if slot is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Availability slot not found.",
                )

            now = self._utcnow()

            if not slot.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Availability slot is inactive.",
                )

            if slot.status != SlotStatus.AVAILABLE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Availability slot is not available "
                        "for booking."
                    ),
                )

            if slot.starts_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Availability slot is in the past.",
                )

            doctor = await self.db.get(
                Doctor,
                slot.doctor_id,
            )

            if doctor is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Doctor profile not found.",
                )

            if not doctor.is_verified:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor is not verified.",
                )

            if not doctor.is_accepting_patients:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Doctor is not accepting patients."
                    ),
                )

            existing_consultation = (
                await self.repo.get_by_slot(
                    availability_slot_id
                )
            )

            if existing_consultation is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Availability slot is already booked.",
                )

            consultation = Consultation(
                patient_id=patient.id,
                doctor_id=doctor.id,
                availability_slot_id=slot.id,
                status=ConsultationStatus.SCHEDULED,
                scheduled_start=slot.starts_at,
                scheduled_end=slot.ends_at,
            )

            slot.status = SlotStatus.BOOKED

            self.db.add(consultation)
            await self.db.flush()
            await self.db.refresh(consultation)

            response_body = (
                self._consultation_response_body(
                    consultation
                )
            )

            await IdempotencyService.complete(
                self.db,
                record=idempotency_record,
                status_code=status.HTTP_201_CREATED,
                response_body=response_body,
                resource_id=consultation.id,
            )

            await self.audit.log(
                actor_user_id=patient.id,
                action="CONSULTATION_BOOKED",
                resource_type="consultation",
                resource_id=consultation.id,
                event_metadata={
                    "doctor_id": str(doctor.id),
                    "availability_slot_id": str(
                        slot.id
                    ),
                    "scheduled_start": (
                        consultation.scheduled_start.isoformat()
                    ),
                    "scheduled_end": (
                        consultation.scheduled_end.isoformat()
                    ),
                    "idempotency_key": key,
                },
            )

            await self.db.commit()
            await self.db.refresh(consultation)

            return consultation

        except HTTPException:
            await self.db.rollback()
            raise

        except IntegrityError:
            await self.db.rollback()

            existing_consultation = (
                await self.repo.get_by_slot(
                    availability_slot_id
                )
            )

            if existing_consultation is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Availability slot is already booked.",
                )

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Consultation could not be booked "
                    "due to a concurrent conflict."
                ),
            )

        except Exception:
            await self.db.rollback()
            raise

    async def get_by_id(
        self,
        consultation_id: UUID,
    ) -> Consultation | None:
        return await self.repo.get_by_id(
            consultation_id
        )

    async def get_for_patient(
        self,
        patient_id: UUID,
        consultation_id: UUID,
    ) -> Consultation:
        consultation = await self.repo.get_by_id(
            consultation_id
        )

        if consultation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consultation not found.",
            )

        if consultation.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You are not allowed to access "
                    "this consultation."
                ),
            )

        return consultation

    async def get_for_doctor(
        self,
        doctor_id: UUID,
        consultation_id: UUID,
    ) -> Consultation:
        consultation = await self.repo.get_by_id(
            consultation_id
        )

        if consultation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consultation not found.",
            )

        if consultation.doctor_id != doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You are not allowed to access "
                    "this consultation."
                ),
            )

        return consultation

    async def list_for_patient(
        self,
        patient_id: UUID,
        *,
        status_filter: ConsultationStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ):
        return await self.repo.list_for_patient(
            patient_id,
            status=status_filter,
            skip=skip,
            limit=limit,
        )

    async def list_for_doctor(
        self,
        doctor_id: UUID,
        *,
        status_filter: ConsultationStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ):
        return await self.repo.list_for_doctor(
            doctor_id,
            status=status_filter,
            skip=skip,
            limit=limit,
        )

    async def update_status(
        self,
        consultation_id: UUID,
        doctor: Doctor,
        new_status: ConsultationStatus,
        *,
        cancellation_reason: str | None = None,
        clinical_notes: str | None = None,
    ) -> Consultation:
        """
        Update consultation state and persist an audit event
        atomically with the lifecycle change.
        """
        consultation = await self.repo.get_by_id(
            consultation_id,
            for_update=True,
        )

        if consultation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consultation not found.",
            )

        if consultation.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You are not allowed to modify "
                    "this consultation."
                ),
            )

        current_status = consultation.status

        allowed_transitions = {
            ConsultationStatus.SCHEDULED: {
                ConsultationStatus.IN_PROGRESS,
                ConsultationStatus.CANCELLED,
                ConsultationStatus.NO_SHOW,
            },
            ConsultationStatus.IN_PROGRESS: {
                ConsultationStatus.COMPLETED,
                ConsultationStatus.CANCELLED,
            },
            ConsultationStatus.COMPLETED: set(),
            ConsultationStatus.CANCELLED: set(),
            ConsultationStatus.NO_SHOW: set(),
        }

        if new_status not in allowed_transitions.get(
            current_status,
            set(),
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Invalid consultation status transition: "
                    f"{current_status.value} -> "
                    f"{new_status.value}."
                ),
            )

        if (
            new_status == ConsultationStatus.CANCELLED
            and not (cancellation_reason or "").strip()
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cancellation reason is required.",
            )

        now = self._utcnow()

        consultation.status = new_status

        if new_status == ConsultationStatus.IN_PROGRESS:
            consultation.actual_started_at = now

        elif new_status == ConsultationStatus.COMPLETED:
            consultation.actual_completed_at = now

        elif new_status == ConsultationStatus.CANCELLED:
            consultation.cancellation_reason = (
                cancellation_reason.strip()
                if cancellation_reason
                else None
            )

        if clinical_notes is not None:
            consultation.clinical_notes = (
                clinical_notes.strip()
            )

        await self.audit.log(
            actor_user_id=doctor.user_id,
            action="CONSULTATION_STATUS_CHANGED",
            resource_type="consultation",
            resource_id=consultation.id,
            event_metadata={
                "previous_status": current_status.value,
                "new_status": new_status.value,
                "cancellation_reason": (
                    consultation.cancellation_reason
                    if new_status
                    == ConsultationStatus.CANCELLED
                    else None
                ),
            },
        )

        await self.db.commit()
        await self.db.refresh(consultation)

        return consultation

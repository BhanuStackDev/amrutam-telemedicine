from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consultation import Consultation, ConsultationStatus
from app.models.doctor import Doctor
from app.models.prescription import Prescription
from app.models.user import User
from app.repositories.prescription import PrescriptionRepository


class PrescriptionService:
    """Business logic for issuing and retrieving prescriptions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PrescriptionRepository(db)

    async def create_prescription(
        self,
        doctor: Doctor,
        consultation_id: UUID,
        *,
        diagnosis: str | None,
        medicines: str,
        instructions: str | None,
        follow_up_instructions: str | None,
        doctor_notes: str | None,
    ) -> Prescription:
        """Create one prescription for a completed consultation."""

        consultation = await self.db.get(
            Consultation,
            consultation_id,
        )

        if consultation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consultation not found.",
            )

        if consultation.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to prescribe for this consultation.",
            )

        if consultation.status != ConsultationStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Prescription can only be issued for a completed consultation.",
            )

        existing = await self.repo.get_by_consultation(
            consultation_id,
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A prescription already exists for this consultation.",
            )

        medicines_value = medicines.strip()

        if not medicines_value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Medicines cannot be empty.",
            )

        prescription = Prescription(
            consultation_id=consultation.id,
            doctor_id=doctor.id,
            patient_id=consultation.patient_id,
            issued_on=date.today(),
            diagnosis=diagnosis,
            medicines=medicines_value,
            instructions=instructions,
            follow_up_instructions=follow_up_instructions,
            doctor_notes=doctor_notes,
        )

        try:
            await self.repo.create(prescription)
            await self.db.commit()
            await self.db.refresh(prescription)

            return prescription

        except IntegrityError as exc:
            await self.db.rollback()

            existing = await self.repo.get_by_consultation(
                consultation_id,
            )

            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A prescription already exists for this consultation.",
                ) from exc

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Prescription could not be created.",
            ) from exc

        except Exception:
            await self.db.rollback()
            raise

    async def get_prescription_for_patient(
        self,
        patient_id: UUID,
        prescription_id: UUID,
    ) -> Prescription:
        """Return a prescription only when it belongs to the patient."""

        prescription = await self.repo.get_by_id(
            prescription_id,
        )

        if prescription is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prescription not found.",
            )

        if prescription.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to access this prescription.",
            )

        return prescription

    async def get_prescription_for_doctor(
        self,
        doctor_id: UUID,
        prescription_id: UUID,
    ) -> Prescription:
        """Return a prescription only when it belongs to the doctor."""

        prescription = await self.repo.get_by_id(
            prescription_id,
        )

        if prescription is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prescription not found.",
            )

        if prescription.doctor_id != doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to access this prescription.",
            )

        return prescription

    async def get_for_consultation(
        self,
        consultation_id: UUID,
    ) -> Prescription | None:
        return await self.repo.get_by_consultation(
            consultation_id,
        )

    async def list_patient_prescriptions(
        self,
        patient_id: UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Prescription], int]:
        return await self.repo.list_for_patient(
            patient_id,
            skip=skip,
            limit=limit,
        )

    async def list_doctor_prescriptions(
        self,
        doctor_id: UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Prescription], int]:
        return await self.repo.list_for_doctor(
            doctor_id,
            skip=skip,
            limit=limit,
        )

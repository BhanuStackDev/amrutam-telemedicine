from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_doctor, require_patient
from app.core.database import get_db
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.prescription import (
    PrescriptionCreateRequest,
    PrescriptionListResponse,
    PrescriptionResponse,
)
from app.services.prescription import PrescriptionService


router = APIRouter(
    prefix="/prescriptions",
    tags=["Prescriptions"],
)


async def get_prescription_service(
    db: AsyncSession = Depends(get_db),
) -> PrescriptionService:
    return PrescriptionService(db)


async def get_current_doctor(
    current_user: User = Depends(require_doctor),
    db: AsyncSession = Depends(get_db),
) -> Doctor:
    doctor = await db.scalar(
        select(Doctor).where(
            Doctor.user_id == current_user.id,
        )
    )

    if doctor is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor profile not found.",
        )

    return doctor


@router.post(
    "",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_prescription(
    payload: PrescriptionCreateRequest,
    doctor: Doctor = Depends(get_current_doctor),
    service: PrescriptionService = Depends(get_prescription_service),
):
    return await service.create_prescription(
        doctor=doctor,
        consultation_id=payload.consultation_id,
        diagnosis=payload.diagnosis,
        medicines=payload.medicines,
        instructions=payload.instructions,
        follow_up_instructions=payload.follow_up_instructions,
        doctor_notes=payload.doctor_notes,
    )


@router.get(
    "/mine",
    response_model=PrescriptionListResponse,
)
async def list_my_prescriptions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_patient),
    service: PrescriptionService = Depends(get_prescription_service),
):
    items, total = await service.list_patient_prescriptions(
        current_user.id,
        skip=skip,
        limit=limit,
    )

    return PrescriptionListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=skip,
    )


@router.get(
    "/doctor/mine",
    response_model=PrescriptionListResponse,
)
async def list_doctor_prescriptions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    doctor: Doctor = Depends(get_current_doctor),
    service: PrescriptionService = Depends(get_prescription_service),
):
    items, total = await service.list_doctor_prescriptions(
        doctor.id,
        skip=skip,
        limit=limit,
    )

    return PrescriptionListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=skip,
    )


@router.get(
    "/{prescription_id}",
    response_model=PrescriptionResponse,
)
async def get_prescription(
    prescription_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PrescriptionService = Depends(get_prescription_service),
):
    if current_user.role.value == "patient":
        return await service.get_prescription_for_patient(
            current_user.id,
            prescription_id,
        )

    if current_user.role.value == "doctor":
        doctor = await get_current_doctor(
            current_user=current_user,
            db=service.db,
        )

        return await service.get_prescription_for_doctor(
            doctor.id,
            prescription_id,
        )

    prescription = await service.repo.get_by_id(
        prescription_id,
    )

    if prescription is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found.",
        )

    return prescription

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    require_patient,
)
from app.core.database import get_db
from app.models.consultation import ConsultationStatus
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.consultation import (
    ConsultationBookingRequest,
    ConsultationListResponse,
    ConsultationResponse,
    ConsultationStatusUpdateRequest,
)
from app.services.consultation import ConsultationService


router = APIRouter(
    prefix="/consultations",
    tags=["Consultations"],
)


async def get_consultation_service(
    db: AsyncSession = Depends(get_db),
) -> ConsultationService:
    return ConsultationService(db)


async def get_current_doctor(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Doctor:
    doctor = await db.scalar(
        select(Doctor).where(
            Doctor.user_id == current_user.id,
        )
    )

    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor profile not found.",
        )

    return doctor


@router.post(
    "/book",
    response_model=ConsultationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def book_consultation(
    payload: ConsultationBookingRequest,
    current_user: User = Depends(require_patient),
    service: ConsultationService = Depends(get_consultation_service),
):
    return await service.book_slot(
        patient=current_user,
        availability_slot_id=payload.availability_slot_id,
        idempotency_key=payload.idempotency_key,
    )


@router.get(
    "/mine",
    response_model=ConsultationListResponse,
)
async def list_my_consultations(
    status_filter: ConsultationStatus | None = Query(
        default=None,
        alias="status",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_patient),
    service: ConsultationService = Depends(get_consultation_service),
):
    items, total = await service.list_for_patient(
        current_user.id,
        status_filter=status_filter,
        skip=skip,
        limit=limit,
    )

    return ConsultationListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=skip,
    )


@router.get(
    "/doctor/mine",
    response_model=ConsultationListResponse,
)
async def list_doctor_consultations(
    status_filter: ConsultationStatus | None = Query(
        default=None,
        alias="status",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    doctor: Doctor = Depends(get_current_doctor),
    service: ConsultationService = Depends(get_consultation_service),
):
    items, total = await service.list_for_doctor(
        doctor.id,
        status_filter=status_filter,
        skip=skip,
        limit=limit,
    )

    return ConsultationListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=skip,
    )


@router.get(
    "/{consultation_id}",
    response_model=ConsultationResponse,
)
async def get_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ConsultationService = Depends(get_consultation_service),
):
    if current_user.role.value == "patient":
        return await service.get_for_patient(
            current_user.id,
            consultation_id,
        )

    if current_user.role.value == "doctor":
        doctor = await get_current_doctor(
            current_user=current_user,
            db=service.db,
        )

        return await service.get_for_doctor(
            doctor.id,
            consultation_id,
        )

    consultation = await service.get_by_id(
        consultation_id,
    )

    if consultation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation not found.",
        )

    return consultation


@router.patch(
    "/{consultation_id}/status",
    response_model=ConsultationResponse,
)
async def update_consultation_status(
    consultation_id: UUID,
    payload: ConsultationStatusUpdateRequest,
    doctor: Doctor = Depends(get_current_doctor),
    service: ConsultationService = Depends(get_consultation_service),
):
    return await service.update_status(
        consultation_id=consultation_id,
        doctor=doctor,
        new_status=payload.status,
        cancellation_reason=payload.cancellation_reason,
        clinical_notes=payload.clinical_notes,
    )

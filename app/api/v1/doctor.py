from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    RequireAdmin,
    RequireAnyAuthenticatedUser,
    RequireDoctor,
)
from app.core.database import get_db
from app.models import Doctor
from app.schemas.doctor import (
    DoctorCreateRequest,
    DoctorListResponse,
    DoctorResponse,
    DoctorUpdateRequest,
)
from app.services.doctor import DoctorService


router = APIRouter(
    prefix="/doctors",
    tags=["Doctors"],
)


@router.post(
    "",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_doctor(
    payload: DoctorCreateRequest,
    current_user: RequireAdmin,
    db: AsyncSession = Depends(get_db),
) -> Doctor:
    """
    Create a doctor profile.

    Only administrators can create doctor profiles.
    """
    return await DoctorService(db).create_doctor(payload)


@router.get(
    "",
    response_model=DoctorListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_doctors(
    current_user: RequireAnyAuthenticatedUser,
    db: AsyncSession = Depends(get_db),
    specialization: str | None = Query(
        default=None,
        min_length=2,
        max_length=150,
    ),
    verified_only: bool = Query(default=False),
    accepting_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DoctorListResponse:
    """
    List doctors with filtering and pagination.
    """

    doctors, total = await DoctorService(db).list_doctors(
        specialization=specialization,
        verified_only=verified_only,
        accepting_only=accepting_only,
        limit=limit,
        offset=offset,
    )

    return DoctorListResponse(
        items=doctors,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/me",
    response_model=DoctorResponse,
    status_code=status.HTTP_200_OK,
)
async def get_my_doctor_profile(
    current_user: RequireDoctor,
    db: AsyncSession = Depends(get_db),
) -> Doctor:
    """
    Get the authenticated doctor's own profile.
    """
    return await DoctorService(db).get_doctor_for_user(
        current_user.id
    )


@router.patch(
    "/me",
    response_model=DoctorResponse,
    status_code=status.HTTP_200_OK,
)
async def update_my_doctor_profile(
    payload: DoctorUpdateRequest,
    current_user: RequireDoctor,
    db: AsyncSession = Depends(get_db),
) -> Doctor:
    """
    Update the authenticated doctor's editable profile fields.

    Doctors cannot self-verify or change administrative
    patient-acceptance controls.
    """

    safe_payload = DoctorUpdateRequest(
        **{
            field: value
            for field, value in payload.model_dump(
                exclude_unset=True
            ).items()
            if field not in {
                "is_verified",
                "is_accepting_patients",
            }
        }
    )

    service = DoctorService(db)

    doctor = await service.get_doctor_for_user(
        current_user.id
    )

    return await service.update_doctor(
        doctor.id,
        safe_payload,
    )


@router.get(
    "/{doctor_id}",
    response_model=DoctorResponse,
    status_code=status.HTTP_200_OK,
)
async def get_doctor(
    doctor_id: UUID,
    current_user: RequireAnyAuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> Doctor:
    """
    Get a doctor by ID.
    """
    return await DoctorService(db).get_doctor(
        doctor_id
    )


@router.patch(
    "/{doctor_id}",
    response_model=DoctorResponse,
    status_code=status.HTTP_200_OK,
)
async def update_doctor(
    doctor_id: UUID,
    payload: DoctorUpdateRequest,
    current_user: RequireAdmin,
    db: AsyncSession = Depends(get_db),
) -> Doctor:
    """
    Administratively update a doctor profile.
    """
    return await DoctorService(db).update_doctor(
        doctor_id,
        payload,
    )


@router.delete(
    "/{doctor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_doctor(
    doctor_id: UUID,
    current_user: RequireAdmin,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Delete a doctor profile.

    Database foreign-key restrictions protect doctors referenced by
    availability slots, consultations, or prescriptions.
    """

    await DoctorService(db).delete_doctor(
        doctor_id
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]

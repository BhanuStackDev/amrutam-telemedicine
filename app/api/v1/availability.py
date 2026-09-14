from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    RequireAnyAuthenticatedUser,
    RequireDoctor,
)
from app.core.database import get_db
from app.models import AvailabilitySlot, SlotStatus
from app.schemas.availability import (
    AvailabilitySlotCreateRequest,
    AvailabilitySlotListResponse,
    AvailabilitySlotResponse,
    AvailabilitySlotUpdateRequest,
)
from app.services.availability import AvailabilityService


router = APIRouter(
    prefix="/availability",
    tags=["Availability"],
)


@router.post(
    "",
    response_model=AvailabilitySlotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_availability_slot(
    payload: AvailabilitySlotCreateRequest,
    current_user: RequireDoctor,
    db: AsyncSession = Depends(get_db),
) -> AvailabilitySlot:
    """Create an availability slot for the authenticated doctor."""

    return await AvailabilityService(db).create_for_user(
        current_user.id,
        payload,
    )


@router.get(
    "/me",
    response_model=AvailabilitySlotListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_my_availability_slots(
    current_user: RequireDoctor,
    db: AsyncSession = Depends(get_db),
    starts_from: datetime | None = Query(default=None),
    starts_until: datetime | None = Query(default=None),
    slot_status: SlotStatus | None = Query(
        default=None,
        alias="status",
    ),
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AvailabilitySlotListResponse:
    """List availability slots belonging to the authenticated doctor."""

    slots, total = await AvailabilityService(db).list_for_user(
        current_user.id,
        starts_from=starts_from,
        starts_until=starts_until,
        status_filter=slot_status,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

    return AvailabilitySlotListResponse(
        items=slots,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/doctor/{doctor_id}",
    response_model=AvailabilitySlotListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_doctor_availability_slots(
    doctor_id: UUID,
    current_user: RequireAnyAuthenticatedUser,
    db: AsyncSession = Depends(get_db),
    starts_from: datetime | None = Query(default=None),
    starts_until: datetime | None = Query(default=None),
    slot_status: SlotStatus | None = Query(
        default=None,
        alias="status",
    ),
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AvailabilitySlotListResponse:
    """List a doctor's availability slots."""

    slots, total = await AvailabilityService(db).list_for_doctor(
        doctor_id,
        starts_from=starts_from,
        starts_until=starts_until,
        status_filter=slot_status,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

    return AvailabilitySlotListResponse(
        items=slots,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{slot_id}",
    response_model=AvailabilitySlotResponse,
    status_code=status.HTTP_200_OK,
)
async def get_availability_slot(
    slot_id: UUID,
    current_user: RequireAnyAuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> AvailabilitySlot:
    """Get a single availability slot."""

    return await AvailabilityService(db).get_slot(
        slot_id
    )


@router.patch(
    "/{slot_id}",
    response_model=AvailabilitySlotResponse,
    status_code=status.HTTP_200_OK,
)
async def update_availability_slot(
    slot_id: UUID,
    payload: AvailabilitySlotUpdateRequest,
    current_user: RequireDoctor,
    db: AsyncSession = Depends(get_db),
) -> AvailabilitySlot:
    """Update an availability slot owned by the authenticated doctor."""

    return await AvailabilityService(db).update_for_user(
        current_user.id,
        slot_id,
        payload,
    )


@router.delete(
    "/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_availability_slot(
    slot_id: UUID,
    current_user: RequireDoctor,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Deactivate an availability slot owned by the authenticated doctor.

    This is a soft delete represented by CANCELLED + inactive.
    """

    await AvailabilityService(db).delete_for_user(
        current_user.id,
        slot_id,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]

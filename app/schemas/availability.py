from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.availability import SlotStatus


class AvailabilitySlotCreateRequest(BaseModel):
    """Request payload for creating a doctor's availability slot."""

    starts_at: datetime = Field(
        ...,
        description="UTC start datetime for the availability slot.",
    )
    ends_at: datetime = Field(
        ...,
        description="UTC end datetime for the availability slot.",
    )

    @field_validator("starts_at", "ends_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Datetime must include timezone information."
            )
        return value

    @classmethod
    def validate_interval(
        cls,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        if ends_at <= starts_at:
            raise ValueError(
                "ends_at must be later than starts_at."
            )


class AvailabilitySlotUpdateRequest(BaseModel):
    """Request payload for updating a slot."""

    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    status: Optional[SlotStatus] = None
    is_active: Optional[bool] = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def validate_timezone(
        cls,
        value: Optional[datetime],
    ) -> Optional[datetime]:
        if value is None:
            return value

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Datetime must include timezone information."
            )

        return value


class AvailabilitySlotResponse(BaseModel):
    """Availability slot API response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doctor_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: SlotStatus
    is_active: bool


class AvailabilitySlotListResponse(BaseModel):
    """Paginated availability slot response."""

    items: list[AvailabilitySlotResponse]
    total: int
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)

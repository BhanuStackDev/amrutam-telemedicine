from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.consultation import ConsultationStatus


class ConsultationBookingRequest(BaseModel):
    """Patient request to book an available doctor slot."""

    availability_slot_id: UUID = Field(
        ...,
        description="Availability slot to book.",
    )

    idempotency_key: str = Field(
        ...,
        min_length=16,
        max_length=128,
        description="Client-generated idempotency key for safe retries.",
    )

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "idempotency_key cannot be empty."
            )

        return value


class ConsultationStatusUpdateRequest(BaseModel):
    """Request to transition a consultation lifecycle state."""

    status: ConsultationStatus
    cancellation_reason: Optional[str] = Field(
        default=None,
        max_length=2000,
    )
    clinical_notes: Optional[str] = Field(
        default=None,
        max_length=20000,
    )

    @field_validator(
        "cancellation_reason",
        "clinical_notes",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        value = value.strip()

        return value or None


class ConsultationResponse(BaseModel):
    """Consultation API response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    doctor_id: UUID
    availability_slot_id: UUID
    status: ConsultationStatus
    scheduled_start: datetime
    scheduled_end: datetime
    actual_started_at: Optional[datetime]
    actual_completed_at: Optional[datetime]
    clinical_notes: Optional[str]
    cancellation_reason: Optional[str]


class ConsultationListResponse(BaseModel):
    """Paginated consultation response."""

    items: list[ConsultationResponse]
    total: int
    limit: int = Field(
        ge=1,
        le=100,
    )
    offset: int = Field(
        ge=0,
    )

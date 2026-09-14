from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PrescriptionCreateRequest(BaseModel):
    """Doctor request to issue a prescription for a completed consultation."""

    consultation_id: UUID = Field(
        ...,
        description="Completed consultation for which the prescription is issued.",
    )

    diagnosis: str | None = Field(
        default=None,
        max_length=10000,
    )

    medicines: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="Prescribed medicines and dosage instructions.",
    )

    instructions: str | None = Field(
        default=None,
        max_length=20000,
    )

    follow_up_instructions: str | None = Field(
        default=None,
        max_length=20000,
    )

    doctor_notes: str | None = Field(
        default=None,
        max_length=20000,
    )

    @field_validator(
        "diagnosis",
        "medicines",
        "instructions",
        "follow_up_instructions",
        "doctor_notes",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            return None

        return value


class PrescriptionResponse(BaseModel):
    """Prescription API response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    consultation_id: UUID
    doctor_id: UUID
    patient_id: UUID
    issued_on: date
    diagnosis: str | None
    medicines: str
    instructions: str | None
    follow_up_instructions: str | None
    doctor_notes: str | None


class PrescriptionListResponse(BaseModel):
    """Paginated prescription response."""

    items: list[PrescriptionResponse]
    total: int
    limit: int = Field(
        ge=1,
        le=100,
    )
    offset: int = Field(
        ge=0,
    )

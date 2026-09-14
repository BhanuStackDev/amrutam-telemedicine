from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DoctorCreateRequest(BaseModel):
    """Admin payload for creating a doctor profile."""

    user_id: UUID
    license_number: str = Field(min_length=2, max_length=100)
    specialization: str = Field(min_length=2, max_length=150)
    qualification: str = Field(min_length=2, max_length=255)
    experience_years: int = Field(default=0, ge=0, le=80)
    consultation_fee: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        max_digits=10,
        decimal_places=2,
    )
    bio: str | None = Field(default=None, max_length=10000)
    is_verified: bool = False
    is_accepting_patients: bool = True

    @field_validator(
        "license_number",
        "specialization",
        "qualification",
    )
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Value cannot be empty")

        return value

    @field_validator("bio")
    @classmethod
    def normalize_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None


class DoctorUpdateRequest(BaseModel):
    """Admin payload for updating a doctor profile."""

    license_number: str | None = Field(default=None, min_length=2, max_length=100)
    specialization: str | None = Field(default=None, min_length=2, max_length=150)
    qualification: str | None = Field(default=None, min_length=2, max_length=255)
    experience_years: int | None = Field(default=None, ge=0, le=80)
    consultation_fee: Decimal | None = Field(
        default=None,
        ge=Decimal("0.00"),
        max_digits=10,
        decimal_places=2,
    )
    bio: str | None = Field(default=None, max_length=10000)
    is_verified: bool | None = None
    is_accepting_patients: bool | None = None

    @field_validator(
        "license_number",
        "specialization",
        "qualification",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Value cannot be empty")

        return value

    @field_validator("bio")
    @classmethod
    def normalize_optional_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None


class DoctorResponse(BaseModel):
    """Public/API representation of a doctor."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    license_number: str
    specialization: str
    qualification: str
    experience_years: int
    consultation_fee: Decimal
    bio: str | None
    is_verified: bool
    is_accepting_patients: bool


class DoctorListResponse(BaseModel):
    """Paginated doctor collection."""

    items: list[DoctorResponse]
    total: int
    limit: int
    offset: int
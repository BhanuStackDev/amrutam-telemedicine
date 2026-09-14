from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Prescription(Base, TimestampMixin):
    """Prescription issued as part of a completed consultation."""

    __tablename__ = "prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    issued_on: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    diagnosis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    medicines: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    follow_up_instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    doctor_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    consultation: Mapped["Consultation"] = relationship()

    doctor: Mapped["Doctor"] = relationship()

    patient: Mapped["User"] = relationship()

    __table_args__ = (
        Index(
            "ix_prescriptions_patient_issued_on",
            "patient_id",
            "issued_on",
        ),
        Index(
            "ix_prescriptions_doctor_issued_on",
            "doctor_id",
            "issued_on",
        ),
    )
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SlotStatus(str, enum.Enum):
    """Lifecycle state of a doctor's availability slot."""

    AVAILABLE = "available"
    HELD = "held"
    BOOKED = "booked"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AvailabilitySlot(Base, TimestampMixin):
    """Bookable doctor availability interval."""

    __tablename__ = "availability_slots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[SlotStatus] = mapped_column(
        Enum(SlotStatus, name="slot_status"),
        nullable=False,
        default=SlotStatus.AVAILABLE,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    doctor: Mapped["Doctor"] = relationship()

    __table_args__ = (
        CheckConstraint(
            "ends_at > starts_at",
            name="ck_availability_slots_valid_interval",
        ),
        UniqueConstraint(
            "doctor_id",
            "starts_at",
            "ends_at",
            name="uq_availability_slots_doctor_interval",
        ),
        Index(
            "ix_availability_slots_doctor_status_start",
            "doctor_id",
            "status",
            "starts_at",
        ),
        Index(
            "ix_availability_slots_active_start",
            "is_active",
            "starts_at",
        ),
    )
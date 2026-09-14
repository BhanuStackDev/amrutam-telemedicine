from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class AuditService:
    """Security and compliance audit logging service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        *,
        actor_user_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: str | UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        event_metadata: Mapping[str, Any] | None = None,
        outcome: str = "success",
    ) -> AuditLog:
        """Persist a security/compliance audit event."""

        audit = AuditLog(
            actor_user_id=actor_user_id,
            action=action.strip(),
            resource_type=resource_type.strip(),
            resource_id=(
                str(resource_id)
                if resource_id is not None
                else None
            ),
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            event_metadata=(
                dict(event_metadata)
                if event_metadata is not None
                else None
            ),
            outcome=outcome.strip() or "success",
        )

        self.db.add(audit)
        await self.db.flush()

        return audit

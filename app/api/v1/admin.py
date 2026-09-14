from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireAdmin
from app.core.database import get_db
from app.schemas.admin import (
    AdminAnalyticsResponse,
    AuditLogListResponse,
)
from app.services.admin import AdminService


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.get(
    "/analytics",
    response_model=AdminAnalyticsResponse,
)
async def get_admin_analytics(
    current_user: RequireAdmin,
    db: AsyncSession = Depends(get_db),
) -> AdminAnalyticsResponse:
    """Return platform-wide administrative analytics."""
    return await AdminService(db).get_analytics()


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
)
async def list_audit_logs(
    current_user: RequireAdmin,
    db: AsyncSession = Depends(get_db),
    action: str | None = Query(
        default=None,
        min_length=2,
        max_length=100,
    ),
    resource_type: str | None = Query(
        default=None,
        min_length=2,
        max_length=100,
    ),
    outcome: str | None = Query(
        default=None,
        min_length=2,
        max_length=32,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
) -> AuditLogListResponse:
    """Query security/compliance audit events."""
    return await AdminService(db).list_audit_logs(
        action=action,
        resource_type=resource_type,
        outcome=outcome,
        limit=limit,
        offset=offset,
    )


__all__ = ["router"]

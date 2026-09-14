from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User, UserRole, UserStatus


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve and validate the authenticated user from an access token."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except Exception as exc:
        raise credentials_exception from exc

    if payload.get("type") != "access":
        raise credentials_exception

    subject = payload.get("sub")

    if not isinstance(subject, str) or not subject:
        raise credentials_exception

    user = await db.scalar(
        select(User).where(User.id == subject)
    )

    if user is None:
        raise credentials_exception

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )

    token_role = payload.get("role")

    if token_role != user.role.value:
        raise credentials_exception

    return user


CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]


async def require_patient(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Allow only patient users."""

    if current_user.role != UserRole.PATIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return current_user


async def require_doctor(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Allow only doctor users."""

    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return current_user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Allow only admin users."""

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return current_user


async def require_doctor_or_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Allow doctor or admin users."""

    if current_user.role not in {
        UserRole.DOCTOR,
        UserRole.ADMIN,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return current_user


async def require_any_authenticated_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Allow any active authenticated user."""

    return current_user


RequirePatient = Annotated[
    User,
    Depends(require_patient),
]

RequireDoctor = Annotated[
    User,
    Depends(require_doctor),
]

RequireAdmin = Annotated[
    User,
    Depends(require_admin),
]

RequireDoctorOrAdmin = Annotated[
    User,
    Depends(require_doctor_or_admin),
]

RequireAnyAuthenticatedUser = Annotated[
    User,
    Depends(require_any_authenticated_user),
]

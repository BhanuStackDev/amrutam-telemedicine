from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    MFADisableRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> User:
    return await AuthService(db).register(payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    service = AuthService(db)

    user = await service.authenticate(payload)

    return await service.issue_tokens(
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
async def refresh(
    request: Request,
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await AuthService(db).refresh_tokens(
        payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
)
async def logout(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    return await AuthService(db).logout(payload)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def get_me(
    current_user: CurrentUser,
) -> User:
    return current_user


@router.post(
    "/mfa/setup",
    response_model=MFASetupResponse,
    status_code=status.HTTP_200_OK,
)
async def setup_mfa(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> MFASetupResponse:
    service = AuthService(db)

    secret, provisioning_uri = await service.setup_mfa(
        current_user
    )

    return MFASetupResponse(
        secret=secret,
        provisioning_uri=provisioning_uri,
        message=(
            "MFA setup created. Scan the provisioning URI "
            "with your authenticator and verify the current "
            "6-digit code to enable MFA."
        ),
    )


@router.post(
    "/mfa/verify",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_mfa(
    payload: MFAVerifyRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> User:
    service = AuthService(db)

    await service.verify_and_enable_mfa(
        current_user,
        payload.code,
    )

    await db.refresh(current_user)

    return current_user


@router.post(
    "/mfa/disable",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def disable_mfa(
    payload: MFADisableRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> User:
    service = AuthService(db)

    await service.disable_mfa(
        current_user,
        password=payload.password,
        code=payload.code,
    )

    await db.refresh(current_user)

    return current_user
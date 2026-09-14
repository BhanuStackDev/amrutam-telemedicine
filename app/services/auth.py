from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    get_token_expiry,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import RefreshToken, User, UserStatus
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserRegisterRequest,
)

settings = get_settings()


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self,
        payload: UserRegisterRequest,
    ) -> User:
        normalized_email = payload.email.strip().lower()

        existing = await self.db.scalar(
            select(User).where(
                User.email == normalized_email
            )
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )

        user = User(
            email=normalized_email,
            password_hash=hash_password(payload.password),
            status=UserStatus.ACTIVE,
            is_email_verified=False,
            mfa_enabled=False,
            failed_login_attempts=0,
        )

        self.db.add(user)

        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            ) from None

        await self.db.refresh(user)

        return user

    async def authenticate(
        self,
        payload: LoginRequest,
    ) -> User:
        normalized_email = payload.email.strip().lower()

        user = await self.db.scalar(
            select(User)
            .where(User.email == normalized_email)
            .with_for_update()
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        now = datetime.now(timezone.utc)

        if user.status == UserStatus.SUSPENDED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended",
            )

        if user.status == UserStatus.DEACTIVATED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
            )

        if user.locked_until is not None:
            if user.locked_until > now:
                remaining_seconds = max(
                    0,
                    int(
                        (
                            user.locked_until - now
                        ).total_seconds()
                    ),
                )

                remaining_minutes = max(
                    1,
                    (remaining_seconds + 59) // 60,
                )

                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=(
                        "Account is temporarily locked. "
                        f"Try again in about "
                        f"{remaining_minutes} minute(s)."
                    ),
                )

            user.locked_until = None
            user.failed_login_attempts = 0

        password_valid = verify_password(
            payload.password,
            user.password_hash,
        )

        if not password_valid:
            user.failed_login_attempts += 1

            if (
                user.failed_login_attempts
                >= settings.max_failed_login_attempts
            ):
                user.locked_until = (
                    now
                    + timedelta(
                        minutes=settings.account_lockout_minutes
                    )
                )

                await self.db.commit()

                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=(
                        "Account temporarily locked after "
                        "too many failed login attempts"
                    ),
                )

            await self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Correct password resets failed-login state.
        user.failed_login_attempts = 0
        user.locked_until = None

        # MFA enforcement.
        if user.mfa_enabled:
            if not user.mfa_secret_encrypted:
                await self.db.commit()

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="MFA is enabled but the MFA secret is missing",
                )

            if payload.mfa_code is None:
                await self.db.commit()

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="MFA code required",
                )

            try:
                mfa_secret = decrypt_mfa_secret(
                    user.mfa_secret_encrypted
                )
            except ValueError:
                await self.db.commit()

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="MFA configuration is invalid",
                ) from None

            totp = pyotp.TOTP(mfa_secret)

            if not totp.verify(
                payload.mfa_code,
                valid_window=1,
            ):
                await self.db.commit()

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid MFA code",
                )

        user.last_login_at = now

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def setup_mfa(
        self,
        user: User,
    ) -> tuple[str, str]:
        if user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="MFA is already enabled",
            )

        secret = pyotp.random_base32()

        encrypted_secret = encrypt_mfa_secret(secret)

        user.mfa_secret_encrypted = encrypted_secret

        # MFA remains disabled until the code is verified.
        await self.db.commit()

        provisioning_uri = pyotp.TOTP(
            secret
        ).provisioning_uri(
            name=user.email,
            issuer_name="Amrutam Telemedicine",
        )

        return secret, provisioning_uri

    async def verify_and_enable_mfa(
        self,
        user: User,
        code: str,
    ) -> None:
        if not user.mfa_secret_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA setup has not been started",
            )

        try:
            secret = decrypt_mfa_secret(
                user.mfa_secret_encrypted
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MFA configuration is invalid",
            ) from None

        totp = pyotp.TOTP(secret)

        if not totp.verify(
            code,
            valid_window=1,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid MFA code",
            )

        user.mfa_enabled = True

        await self.db.commit()
        await self.db.refresh(user)

        # Security change: force all previously issued sessions
        # to be re-established after MFA activation.
        await self.revoke_all_sessions(user.id)

    async def disable_mfa(
        self,
        user: User,
        *,
        password: str,
        code: str,
    ) -> None:
        if not user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not enabled",
            )

        if not verify_password(
            password,
            user.password_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password",
            )

        if not user.mfa_secret_encrypted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MFA secret is missing",
            )

        try:
            secret = decrypt_mfa_secret(
                user.mfa_secret_encrypted
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MFA configuration is invalid",
            ) from None

        totp = pyotp.TOTP(secret)

        if not totp.verify(
            code,
            valid_window=1,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code",
            )

        user.mfa_enabled = False
        user.mfa_secret_encrypted = None

        await self.db.commit()

        # Force re-authentication after MFA security changes.
        await self.revoke_all_sessions(user.id)

    async def issue_tokens(
        self,
        user: User,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenResponse:
        token_id = uuid.uuid4()

        access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
        )

        refresh_token = create_refresh_token(
            subject=str(user.id),
            token_id=str(token_id),
        )

        refresh_record = RefreshToken(
            id=token_id,
            user_id=user.id,
            token_hash=hash_refresh_token(
                refresh_token
            ),
            expires_at=get_token_expiry(
                refresh_token
            ),
            user_agent=user_agent,
            ip_address=ip_address,
            is_revoked=False,
        )

        self.db.add(refresh_record)

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=(
                settings.access_token_expire_minutes * 60
            ),
        )

    async def refresh_tokens(
        self,
        payload: RefreshTokenRequest,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenResponse:
        try:
            token_payload = decode_token(
                payload.refresh_token
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            ) from None

        if token_payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        subject = token_payload.get("sub")
        token_id_raw = token_payload.get("jti")

        if (
            not isinstance(subject, str)
            or not isinstance(token_id_raw, str)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token claims",
            )

        try:
            token_id = uuid.UUID(token_id_raw)
            user_id = uuid.UUID(subject)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token claims",
            ) from None

        token_hash = hash_refresh_token(
            payload.refresh_token
        )

        result = await self.db.execute(
            select(RefreshToken)
            .where(RefreshToken.id == token_id)
            .with_for_update()
        )

        refresh_record = result.scalar_one_or_none()

        if refresh_record is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not recognized",
            )

        if refresh_record.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        if refresh_record.token_hash != token_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        now = datetime.now(timezone.utc)

        if refresh_record.is_revoked or (
            refresh_record.revoked_at is not None
            and refresh_record.revoked_at <= now
        ):
            await self.revoke_all_sessions(
                refresh_record.user_id
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Refresh token reuse detected; "
                    "all sessions have been revoked"
                ),
            )

        if refresh_record.expires_at <= now:
            refresh_record.is_revoked = True
            refresh_record.revoked_at = now

            await self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
            )

        user = await self.db.scalar(
            select(User).where(
                User.id == refresh_record.user_id
            )
        )

        if user is None:
            refresh_record.is_revoked = True
            refresh_record.revoked_at = now

            await self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account no longer exists",
            )

        if user.status != UserStatus.ACTIVE:
            refresh_record.is_revoked = True
            refresh_record.revoked_at = now

            await self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active",
            )

        new_token_id = uuid.uuid4()

        new_access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
        )

        new_refresh_token = create_refresh_token(
            subject=str(user.id),
            token_id=str(new_token_id),
        )

        new_refresh_record = RefreshToken(
            id=new_token_id,
            user_id=user.id,
            token_hash=hash_refresh_token(
                new_refresh_token
            ),
            expires_at=get_token_expiry(
                new_refresh_token
            ),
            user_agent=user_agent,
            ip_address=ip_address,
            is_revoked=False,
        )

        refresh_record.is_revoked = True
        refresh_record.revoked_at = now
        refresh_record.replaced_by_token_id = new_token_id

        self.db.add(new_refresh_record)

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=(
                settings.access_token_expire_minutes * 60
            ),
        )

    async def logout(
        self,
        payload: RefreshTokenRequest,
    ) -> LogoutResponse:
        token_hash = hash_refresh_token(
            payload.refresh_token
        )

        refresh_record = await self.db.scalar(
            select(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash
            )
            .with_for_update()
        )

        # Logout is idempotent.
        if refresh_record is None:
            return LogoutResponse(
                message="Logged out successfully"
            )

        if not refresh_record.is_revoked:
            refresh_record.is_revoked = True
            refresh_record.revoked_at = (
                datetime.now(timezone.utc)
            )

            await self.db.commit()

        return LogoutResponse(
            message="Logged out successfully"
        )

    async def revoke_all_sessions(
        self,
        user_id: uuid.UUID,
    ) -> None:
        now = datetime.now(timezone.utc)

        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked.is_(False),
            )
            .values(
                is_revoked=True,
                revoked_at=now,
            )
        )

        await self.db.commit()
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken
from pwdlib import PasswordHash

from app.core.config import get_settings

settings = get_settings()

password_hasher = PasswordHash.recommended()

try:
    fernet = Fernet(settings.mfa_encryption_key.encode("utf-8"))
except Exception as exc:
    raise RuntimeError(
        "MFA_ENCRYPTION_KEY must be a valid Fernet key"
    ) from exc


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    return password_hasher.verify(
        password,
        password_hash,
    )


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def encrypt_mfa_secret(secret: str) -> str:
    return fernet.encrypt(
        secret.encode("utf-8")
    ).decode("utf-8")


def decrypt_mfa_secret(encrypted_secret: str) -> str:
    try:
        return fernet.decrypt(
            encrypted_secret.encode("utf-8")
        ).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Unable to decrypt MFA secret"
        ) from exc


def create_access_token(
    subject: str,
    role: str,
    *,
    additional_claims: dict | None = None,
) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now
        + timedelta(
            minutes=settings.access_token_expire_minutes
        ),
    }

    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    subject: str,
    *,
    token_id: str,
) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": subject,
        "type": "refresh",
        "jti": token_id,
        "iat": now,
        "exp": now
        + timedelta(
            days=settings.refresh_token_expire_days
        ),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def get_token_expiry(token: str) -> datetime:
    payload = decode_token(token)
    exp = payload.get("exp")

    if not isinstance(exp, (int, float)):
        raise ValueError(
            "Token does not contain a valid expiry"
        )

    return datetime.fromtimestamp(
        exp,
        tz=timezone.utc,
    )
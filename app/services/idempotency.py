from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idempotency import IdempotencyRecord


class IdempotencyService:
    """
    Persistent idempotency support for write operations.

    Guarantees:
    - Same user + operation + idempotency key + same payload
      can safely replay the original response.
    - Same key with a different payload is rejected.
    - Expired keys are treated as reusable.
    - Unique DB constraint protects against concurrent duplicate keys.
    """

    DEFAULT_TTL_HOURS = 24

    @staticmethod
    def canonical_hash(payload: Any) -> str:
        """
        Create a deterministic SHA-256 hash for a request payload.

        JSON is normalized using sorted keys and compact separators so
        semantically identical dictionaries produce the same hash.
        """
        try:
            canonical = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Request payload could not be normalized for idempotency.",
            ) from exc

        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def normalize_key(cls, key: str) -> str:
        """Validate and normalize an idempotency key."""
        normalized = key.strip()

        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency key cannot be empty.",
            )

        if len(normalized) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency key must be 128 characters or fewer.",
            )

        return normalized

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    async def get_existing(
        cls,
        db: AsyncSession,
        *,
        user_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> IdempotencyRecord | None:
        """
        Return a non-expired idempotency record for the exact key.

        Expired records are ignored so the key can be reused.
        """
        key = cls.normalize_key(idempotency_key)
        now = cls._utcnow()

        result = await db.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.idempotency_key == key,
                IdempotencyRecord.expires_at > now,
            )
        )

        return result.scalar_one_or_none()

    @classmethod
    async def create_pending(
        cls,
        db: AsyncSession,
        *,
        user_id: UUID,
        operation: str,
        idempotency_key: str,
        request_hash: str,
        ttl_hours: int | None = None,
    ) -> tuple[IdempotencyRecord, bool]:
        """
        Create an idempotency record in pending state.

        Returns:
            (record, True)  -> newly created by this request
            (record, False) -> an existing record already owns the key

        The unique DB constraint is the final concurrency guard.
        """
        key = cls.normalize_key(idempotency_key)

        if len(operation.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Idempotency operation is not configured.",
            )

        if len(request_hash) != 64:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid idempotency request hash.",
            )

        existing = await cls.get_existing(
            db,
            user_id=user_id,
            operation=operation,
            idempotency_key=key,
        )

        if existing is not None:
            if existing.request_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Idempotency key has already been used "
                        "with a different request payload."
                    ),
                )

            return existing, False

        ttl = ttl_hours if ttl_hours is not None else cls.DEFAULT_TTL_HOURS

        if ttl <= 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Idempotency TTL must be greater than zero.",
            )

        record = IdempotencyRecord(
            id=uuid4(),
            user_id=user_id,
            operation=operation,
            idempotency_key=key,
            request_hash=request_hash,
            status_code=None,
            response_body=None,
            resource_id=None,
            expires_at=cls._utcnow() + timedelta(hours=ttl),
        )

        db.add(record)

        try:
            await db.flush()
        except IntegrityError:
            """
            Another concurrent transaction inserted the same unique key.

            Roll back only the failed INSERT/savepoint scope and then fetch
            the winner's record.
            """
            await db.rollback()

            existing = await cls.get_existing(
                db,
                user_id=user_id,
                operation=operation,
                idempotency_key=key,
            )

            if existing is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency request is already being processed.",
                )

            if existing.request_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Idempotency key has already been used "
                        "with a different request payload."
                    ),
                )

            return existing, False

        return record, True

    @staticmethod
    def is_completed(record: IdempotencyRecord) -> bool:
        """A non-null status code means the original request completed."""
        return record.status_code is not None

    @staticmethod
    def is_pending(record: IdempotencyRecord) -> bool:
        """A null status code represents an in-progress request."""
        return record.status_code is None

    @classmethod
    def ensure_same_request(
        cls,
        record: IdempotencyRecord,
        *,
        request_hash: str,
    ) -> None:
        """Ensure a reused key represents the same logical request."""
        if record.request_hash != request_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Idempotency key has already been used "
                    "with a different request payload."
                ),
            )

    @classmethod
    async def complete(
        cls,
        db: AsyncSession,
        *,
        record: IdempotencyRecord,
        status_code: int,
        response_body: dict[str, Any],
        resource_id: UUID | None = None,
    ) -> IdempotencyRecord:
        """
        Persist the original response so future retries can replay it.
        """
        record.status_code = status_code
        record.response_body = response_body
        record.resource_id = resource_id

        await db.flush()
        return record

    @classmethod
    def replay_response(
        cls,
        record: IdempotencyRecord,
    ) -> tuple[int, dict[str, Any]]:
        """
        Return the stored HTTP status and response body.

        Raises 409 if a matching key is still pending.
        """
        if not cls.is_completed(record):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A request with this idempotency key is already being processed.",
            )

        if record.response_body is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Idempotency response is incomplete.",
            )

        return record.status_code, record.response_body

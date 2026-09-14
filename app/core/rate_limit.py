from __future__ import annotations

import time

from starlette.responses import JSONResponse


class RedisRateLimitMiddleware:
    """
    Fixed-window Redis-backed request rate limiter.

    Fails open when Redis is unavailable so a cache outage
    does not take the API offline.
    """

    def __init__(
        self,
        app,
        *,
        requests: int = 60,
        window_seconds: int = 60,
        exempt_paths: set[str] | None = None,
    ):
        self.app = app
        self.requests = requests
        self.window_seconds = window_seconds
        self.exempt_paths = exempt_paths or set()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        if path in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        from app.core.redis import get_redis

        client_ip = "unknown"

        for key, value in scope.get("headers", []):
            if key.lower() == b"x-forwarded-for":
                try:
                    client_ip = value.decode("utf-8").split(",")[0].strip()
                except UnicodeDecodeError:
                    pass
                break

        if client_ip == "unknown":
            client = scope.get("client")
            if client:
                client_ip = client[0]

        bucket = int(time.time() // self.window_seconds)
        redis_key = f"rate-limit:{client_ip}:{bucket}"

        try:
            redis = await get_redis()
            count = await redis.incr(redis_key)

            if count == 1:
                await redis.expire(
                    redis_key,
                    self.window_seconds + 1,
                )

            if count > self.requests:
                return await JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests. Please try again later."
                    },
                    headers={
                        "Retry-After": str(self.window_seconds)
                    },
                )(scope, receive, send)

        except Exception:
            # Availability is more important than rate-limit enforcement
            # when the optional rate-limit backend is unavailable.
            pass

        await self.app(scope, receive, send)


__all__ = ["RedisRateLimitMiddleware"]

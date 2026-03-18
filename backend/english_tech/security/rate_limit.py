from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request, WebSocket, status

from english_tech.config import RATE_LIMIT_BACKEND, REDIS_URL

try:
    import redis
except Exception:  # pragma: no cover - optional dependency
    redis = None


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, *, bucket: str, limit: int, window_seconds: int = 60) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            window = self._events[bucket]
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= limit:
                return False
            window.append(now)
            return True


class RedisSlidingWindowRateLimiter:
    def __init__(self, redis_url: str) -> None:
        if redis is None:
            raise RuntimeError('redis client is not installed')
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def allow(self, *, bucket: str, limit: int, window_seconds: int = 60) -> bool:
        if limit <= 0:
            return True
        now = time.time()
        cutoff = now - window_seconds
        member = f'{now}:{secrets.token_hex(4)}'
        key = f'english_tech:ratelimit:{bucket}'
        with self._client.pipeline() as pipe:
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            _, count = pipe.execute()
            if int(count) >= limit:
                return False
            pipe.zadd(key, {member: now})
            pipe.expire(key, window_seconds * 2)
            pipe.execute()
        return True


_fallback_limiter = SlidingWindowRateLimiter()
_redis_limiter = None
if RATE_LIMIT_BACKEND == 'redis' and redis is not None:
    try:
        _redis_limiter = RedisSlidingWindowRateLimiter(REDIS_URL)
    except Exception:
        _redis_limiter = None


class RateLimiterFacade:
    def __init__(self) -> None:
        self._fallback = _fallback_limiter
        self._redis = _redis_limiter

    @property
    def backend_name(self) -> str:
        if self._redis is not None:
            return 'redis'
        return 'memory'

    @property
    def _events(self):
        return self._fallback._events

    def allow(self, *, bucket: str, limit: int, window_seconds: int = 60) -> bool:
        if self._redis is not None:
            try:
                return self._redis.allow(bucket=bucket, limit=limit, window_seconds=window_seconds)
            except Exception:
                return self._fallback.allow(bucket=bucket, limit=limit, window_seconds=window_seconds)
        return self._fallback.allow(bucket=bucket, limit=limit, window_seconds=window_seconds)


rate_limiter = RateLimiterFacade()


def _request_host(request: Request) -> str:
    forwarded_for = request.headers.get('x-forwarded-for', '').strip()
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.client.host if request.client else 'unknown'


def _websocket_host(websocket: WebSocket) -> str:
    forwarded_for = websocket.headers.get('x-forwarded-for', '').strip()
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return websocket.client.host if websocket.client else 'unknown'


def _bucket(category: str, host: str, key_material: str | None = None) -> str:
    suffix = key_material.strip() if key_material else host
    return f'{category}:{host}:{suffix}'


def enforce_http_rate_limit(
    request: Request,
    *,
    category: str,
    limit: int,
    key_material: str | None = None,
    window_seconds: int = 60,
) -> None:
    host = _request_host(request)
    if rate_limiter.allow(
        bucket=_bucket(category, host, key_material),
        limit=limit,
        window_seconds=window_seconds,
    ):
        return
    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Rate limit exceeded')


def allow_websocket_rate_limit(
    websocket: WebSocket,
    *,
    category: str,
    limit: int,
    key_material: str | None = None,
    window_seconds: int = 60,
) -> bool:
    host = _websocket_host(websocket)
    return rate_limiter.allow(
        bucket=_bucket(category, host, key_material),
        limit=limit,
        window_seconds=window_seconds,
    )

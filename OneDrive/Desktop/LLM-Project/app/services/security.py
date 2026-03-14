from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from fastapi import Header, HTTPException, Request

from app.services.redis_backend import get_redis_client
from app.services.runtime_config import get_api_keys, get_runtime_profile


@dataclass
class SecurityContext:
    client_id: str
    api_key_present: bool


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit_per_minute: int) -> bool:
        now = time.time()
        cutoff = now - 60
        with self._lock:
            queue = self._events[key]
            while queue and queue[0] < cutoff:
                queue.popleft()
            if len(queue) >= limit_per_minute:
                return False
            queue.append(now)
            return True


class RedisRateLimiter:
    def __init__(self) -> None:
        self._redis = get_redis_client()

    def check(self, key: str, limit_per_minute: int) -> bool:
        if self._redis is None:
            return _RATE_LIMITER.check(key, limit_per_minute)
        minute_bucket = int(time.time() // 60)
        redis_key = f"contractiq:ratelimit:{key}:{minute_bucket}"
        count = int(self._redis.incr(redis_key))
        if count == 1:
            self._redis.expire(redis_key, 70)
        return count <= limit_per_minute


_RATE_LIMITER = InMemoryRateLimiter()
_REDIS_RATE_LIMITER = RedisRateLimiter()


def enforce_security(request: Request, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> SecurityContext:
    profile = get_runtime_profile()
    allowed_keys = get_api_keys()

    if profile.require_api_key:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="Missing X-API-Key header")
        if x_api_key not in allowed_keys:
            raise HTTPException(status_code=403, detail="Invalid API key")

    client_host = request.client.host if request.client else "unknown"
    limiter_key = f"{client_host}:{x_api_key or 'anon'}"
    if not _REDIS_RATE_LIMITER.check(limiter_key, profile.rate_limit_per_minute):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return SecurityContext(client_id=client_host, api_key_present=bool(x_api_key))

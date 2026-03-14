from __future__ import annotations

import importlib
from typing import Any

from app.services.runtime_config import get_redis_url, is_redis_enabled


def get_redis_client() -> Any | None:
    if not is_redis_enabled():
        return None

    redis_url = get_redis_url()
    if not redis_url:
        return None

    try:
        redis_module = importlib.import_module("redis")
        client = redis_module.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None

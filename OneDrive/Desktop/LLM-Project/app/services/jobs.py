from __future__ import annotations

import time
import uuid
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable

from app.services.redis_backend import get_redis_client


@dataclass
class JobRecord:
    job_id: str
    job_type: str
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result: dict[str, Any] | None = None
    error: str | None = None


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._redis = get_redis_client()

    def submit(self, job_type: str, task: Callable[[], dict[str, Any]]) -> str:
        job_id = str(uuid.uuid4())
        record = JobRecord(job_id=job_id, job_type=job_type)
        with self._lock:
            self._jobs[job_id] = record
        self._persist(record)
        self._executor.submit(self._run_job, job_id, task)
        return job_id

    def _run_job(self, job_id: str, task: Callable[[], dict[str, Any]]) -> None:
        self._update(job_id, status="running")
        try:
            result = task()
            self._update(job_id, status="completed", result=result)
        except Exception as exc:
            self._update(job_id, status="failed", error=str(exc))

    def _update(self, job_id: str, **updates: Any) -> None:
        with self._lock:
            record = self._jobs[job_id]
            for key, value in updates.items():
                setattr(record, key, value)
            record.updated_at = time.time()
        self._persist(record)

    def get(self, job_id: str) -> JobRecord | None:
        record = self._fetch_from_redis(job_id)
        if record is not None:
            return record
        with self._lock:
            return self._jobs.get(job_id)

    def _persist(self, record: JobRecord) -> None:
        if self._redis is None:
            return
        redis_key = f"contractiq:job:{record.job_id}"
        self._redis.hset(
            redis_key,
            mapping={
                "job_id": record.job_id,
                "job_type": record.job_type,
                "status": record.status,
                "created_at": str(record.created_at),
                "updated_at": str(record.updated_at),
                "result": "" if record.result is None else json.dumps(record.result),
                "error": "" if record.error is None else record.error,
            },
        )
        self._redis.expire(redis_key, 86400)

    def _fetch_from_redis(self, job_id: str) -> JobRecord | None:
        if self._redis is None:
            return None
        redis_key = f"contractiq:job:{job_id}"
        payload = self._redis.hgetall(redis_key)
        if not payload:
            return None
        result_value = payload.get("result", "")
        result_payload: dict[str, Any] | None = None
        if result_value:
            try:
                parsed = json.loads(result_value)
                if isinstance(parsed, dict):
                    result_payload = parsed
            except Exception:
                result_payload = {"raw": result_value}
        return JobRecord(
            job_id=payload.get("job_id", job_id),
            job_type=payload.get("job_type", "unknown"),
            status=payload.get("status", "queued"),
            created_at=float(payload.get("created_at", time.time())),
            updated_at=float(payload.get("updated_at", time.time())),
            result=result_payload,
            error=payload.get("error") or None,
        )


JOB_MANAGER = JobManager()

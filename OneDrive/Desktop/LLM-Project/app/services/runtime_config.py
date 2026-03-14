from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    preferred_pipeline_mode: str
    retry_attempts: int
    rate_limit_per_minute: int
    max_upload_bytes: int
    require_api_key: bool


PROFILES: dict[str, RuntimeProfile] = {
    "local-dev": RuntimeProfile(
        name="local-dev",
        preferred_pipeline_mode="local",
        retry_attempts=2,
        rate_limit_per_minute=120,
        max_upload_bytes=10 * 1024 * 1024,
        require_api_key=False,
    ),
    "api-fast": RuntimeProfile(
        name="api-fast",
        preferred_pipeline_mode="prompt",
        retry_attempts=2,
        rate_limit_per_minute=60,
        max_upload_bytes=8 * 1024 * 1024,
        require_api_key=True,
    ),
    "api-accurate": RuntimeProfile(
        name="api-accurate",
        preferred_pipeline_mode="prompt",
        retry_attempts=3,
        rate_limit_per_minute=40,
        max_upload_bytes=8 * 1024 * 1024,
        require_api_key=True,
    ),
}


def get_profile_name() -> str:
    return os.getenv("CONTRACTIQ_PROFILE", "local-dev").strip().lower()


def get_runtime_profile() -> RuntimeProfile:
    profile_name = get_profile_name()
    return PROFILES.get(profile_name, PROFILES["local-dev"])


def get_api_keys() -> set[str]:
    raw = os.getenv("CONTRACTIQ_API_KEYS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def get_output_dir(root_dir: Path) -> Path:
    return root_dir / "output"


def is_legal_model_enabled() -> bool:
    return _env_bool("CONTRACTIQ_LEGAL_MODEL_ENABLED", True)


def get_legal_model_path(root_dir: Path) -> Path:
    raw = os.getenv("CONTRACTIQ_LEGAL_MODEL_PATH", "").strip()
    if raw:
        return Path(raw)
    return root_dir / "models" / "legal_risk_model.joblib"


def get_legal_model_min_confidence() -> float:
    raw = os.getenv("CONTRACTIQ_LEGAL_MODEL_MIN_CONFIDENCE", "0.35").strip()
    try:
        value = float(raw)
    except Exception:
        return 0.35
    return min(max(value, 0.0), 1.0)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_redis_enabled() -> bool:
    return _env_bool("CONTRACTIQ_REDIS_ENABLED", False)


def get_redis_url() -> str:
    return os.getenv("CONTRACTIQ_REDIS_URL", "redis://localhost:6379/0").strip()


def get_audit_signing_secret() -> str:
    return os.getenv("CONTRACTIQ_AUDIT_SIGNING_SECRET", "local-dev-signing-secret").strip()


def is_otel_enabled() -> bool:
    return _env_bool("CONTRACTIQ_OTEL_ENABLED", False)


def get_otel_service_name() -> str:
    return os.getenv("CONTRACTIQ_OTEL_SERVICE_NAME", "contractiq-api").strip()


def get_otel_exporter() -> str:
    return os.getenv("CONTRACTIQ_OTEL_EXPORTER", "otlp").strip().lower()


def get_otel_otlp_endpoint() -> str:
    return os.getenv("CONTRACTIQ_OTEL_OTLP_ENDPOINT", "http://localhost:4318/v1/traces").strip()


def get_otel_prometheus_port() -> int:
    raw = os.getenv("CONTRACTIQ_OTEL_PROMETHEUS_PORT", "9464").strip()
    try:
        return int(raw)
    except Exception:
        return 9464


def validate_environment() -> dict[str, str | bool]:
    profile = get_runtime_profile()
    api_keys = get_api_keys()
    ready = True
    reason = "ok"

    if profile.require_api_key and not api_keys:
        ready = False
        reason = "CONTRACTIQ_API_KEYS must be configured for selected profile"

    if is_redis_enabled() and not get_redis_url():
        ready = False
        reason = "CONTRACTIQ_REDIS_URL must be configured when Redis is enabled"

    return {
        "ready": ready,
        "profile": profile.name,
        "reason": reason,
    }

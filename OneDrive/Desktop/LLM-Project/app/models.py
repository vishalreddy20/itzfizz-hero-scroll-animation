from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    contract_text: str = Field(min_length=1)
    jurisdiction: str = "Unknown"
    contract_type: str = "Unknown"
    counterparty_type: str = "Vendor"
    stance: str = "BALANCED"
    audience: str = "Legal Counsel"
    pipeline_mode: str = "auto"


class ReviewResponse(BaseModel):
    extraction: dict[str, Any]
    analysis: dict[str, Any]
    redlines: list[dict[str, Any]]
    report_markdown: str
    pipeline_mode_used: str
    request_id: str
    providers_used: list[str] = Field(default_factory=list)
    fallback_reason: str = ""
    prompt_version: dict[str, Any] = Field(default_factory=dict)


class PlaybookIngestionRequest(BaseModel):
    raw_text: str = Field(min_length=1)


class DatasetRecordRequest(BaseModel):
    dataset_record: str = Field(min_length=1)


class CuadIngestionRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)


class GenericPayloadResponse(BaseModel):
    payload: dict[str, Any]


class AsyncJobResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    profile: str
    reason: str


class HealthResponse(BaseModel):
    status: str

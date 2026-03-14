from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "COMPLIANT"]
BusinessRiskLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "NEUTRAL"]
PriorityLevel = Literal["MUST CHANGE", "SHOULD CHANGE", "NICE TO HAVE", "ACCEPT"]
ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW"]
QualityLevel = Literal["HIGH", "MEDIUM", "LOW"]


class BestMatchingRule(BaseModel):
    rule_id: str = ""
    clause_type: str = ""
    company_position: str = ""
    never_accept: list[str] = Field(default_factory=list)
    preferred_language: str = ""
    risk_if_missing: str = ""


class PlaybookRetrievalResult(BaseModel):
    clause_type_detected: str
    best_matching_rule: BestMatchingRule
    match_confidence: ConfidenceLevel
    match_reasoning: str
    no_playbook_coverage: bool
    fallback_action: str


class GroqAnalysisResult(BaseModel):
    clause_id: str
    clause_type: str
    legal_risk: RiskLevel
    legal_risk_reason: str
    business_risk: BusinessRiskLevel
    business_risk_reason: str
    deviation_from_playbook: str
    real_world_impact: str
    negotiation_priority: PriorityLevel
    redline_needed: bool
    confidence: ConfidenceLevel


class RedlineVersion(BaseModel):
    redlined_text: str
    change_summary: str
    legal_justification: str
    tone: Literal["AGGRESSIVE", "BALANCED", "CONSERVATIVE"]


class RedlineVersions(BaseModel):
    preferred: RedlineVersion
    fallback: RedlineVersion
    walk_away: RedlineVersion


class RedlineResult(BaseModel):
    clause_id: str
    clause_type: str
    original_text: str
    issue_summary: str
    redline_versions: RedlineVersions
    new_defined_terms_needed: list[str] = Field(default_factory=list)
    cross_clause_impacts: list[str] = Field(default_factory=list)
    attorney_note: str


class DatasetValidClause(BaseModel):
    clause_id: str
    clause_type: str
    original_text: str
    source_contract: str
    word_count: int
    quality_score: QualityLevel
    ready_for_embedding: bool


class DatasetProcessingResult(BaseModel):
    dataset_source: str
    total_records_processed: int
    valid_clauses: list[DatasetValidClause] = Field(default_factory=list)
    invalid_records: list[dict] = Field(default_factory=list)
    processing_notes: str = ""


class PlaybookRule(BaseModel):
    rule_id: str
    clause_type: str
    company_position: str
    minimum_acceptable: str
    never_accept: list[str] = Field(default_factory=list)
    preferred_language: str
    risk_if_missing: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    jurisdiction: str = "ALL"
    contract_types_applicable: list[str] = Field(default_factory=list)
    last_updated: str = ""
    approved_by: str = ""


class PlaybookIngestionResult(BaseModel):
    playbook_rules: list[PlaybookRule] = Field(default_factory=list)

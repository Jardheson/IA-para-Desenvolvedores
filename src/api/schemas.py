from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class IncidentCreateRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=5000)
    reporter: str | None = Field(default=None, max_length=120)
    source_system: str | None = Field(default=None, max_length=120)

    @field_validator("description")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class RecommendationSchema(BaseModel):
    text: str = ""
    suggested_actions: list[str] = []
    blocked_by_policy: bool = False
    approval_notes: str | None = None


class ClassificationSchema(BaseModel):
    category: str = ""
    subcategory: str = ""
    kind: str = ""


class PrioritySchema(BaseModel):
    level: Literal["P0", "P1", "P2", "P3", "P4"] = "P4"
    score: float = 0.0
    urgency: str = ""
    impact: str = ""


class IncidentResponse(BaseModel):
    execution_id: str
    status: str
    classification: ClassificationSchema
    priority: PrioritySchema
    risk_level: Literal["normal", "moderado", "alto"]
    analysis_summary: str
    recommendation: RecommendationSchema
    requires_approval: bool
    created_at: str
    finished_at: str
    evidence_refs: list[str]
    duration_ms: int
    adversarial_detected: bool
    llm_fallback: bool


class TraceEvent(BaseModel):
    source: Literal["log", "audit"]
    ts: str
    node: str | None = None
    event: str
    details: dict[str, Any] = {}


class TraceResponse(BaseModel):
    execution_id: str
    events: list[TraceEvent]


class ErrorResponse(BaseModel):
    code: str
    message: str
    correlation_id: str | None = None

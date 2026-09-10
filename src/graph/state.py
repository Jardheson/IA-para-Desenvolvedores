from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, NotRequired, TypedDict

RiskLevel = Literal["normal", "moderado", "alto"]
Priority = Literal["P0", "P1", "P2", "P3", "P4"]
Status = Literal[
    "PROCESSING",
    "TRIAGEM_CONCLUIDA",
    "BLOQUEADO_PENDENTE_APROVACAO",
    "ERRO",
]


class Analysis(TypedDict, total=False):
    summary: str
    keywords: list[str]
    affected_system: str
    symptoms: list[str]
    impact: str


class Classification(TypedDict, total=False):
    category: str
    subcategory: str
    kind: str


class PriorityAssessment(TypedDict, total=False):
    level: Priority
    score: float
    urgency: str
    impact: str


class ToolResult(TypedDict, total=False):
    query: str
    items: list[dict[str, Any]]
    fallback: bool
    error_message: str | None
    retry_count: int
    duration_ms: int


class RiskAssessment(TypedDict, total=False):
    risk_level: RiskLevel
    requires_approval: bool
    justification: str
    meta: dict[str, Any]


class Recommendation(TypedDict, total=False):
    text: str
    suggested_actions: list[str]
    blocked_by_policy: bool
    approval_notes: str | None


class OutputDto(TypedDict, total=False):
    execution_id: str
    status: Status
    classification: Classification
    priority: PriorityAssessment
    risk_level: RiskLevel
    analysis_summary: str
    recommendation: Recommendation
    requires_approval: bool
    created_at: str
    finished_at: str
    evidence_refs: list[str]
    duration_ms: int
    adversarial_detected: bool
    llm_fallback: bool


class TriageState(TypedDict):
    execution_id: str
    received_at: str
    raw_input: dict[str, Any]
    validated: bool
    validation_errors: list[dict[str, Any]]
    injection_score: float
    adversarial_detected: bool
    llm_fallback: bool
    analysis: Analysis
    classification: Classification
    priority: PriorityAssessment
    tool_results: list[ToolResult]
    risk_assessment: RiskAssessment
    requires_approval: bool
    final_recommendation: Recommendation
    output_dto: OutputDto
    audit_refs: Annotated[list[str], operator.add]
    error: NotRequired[dict[str, Any] | None]
    step_count: Annotated[int, operator.add]
    history_refs: list[str]
    source_system: str | None
    reporter: str | None

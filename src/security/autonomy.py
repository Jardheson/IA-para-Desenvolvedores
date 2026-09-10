from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config import settings


@dataclass
class AutonomyContext:
    risk_level: str = "normal"
    priority_level: str = "P4"
    category: str | None = None
    subcategory: str | None = None
    injection_score: float = 0.0
    adversarial_detected: bool = False
    history_considered: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AutonomyResult:
    requires_human_approval: bool
    reasons: list[str] = field(default_factory=list)
    risk_escalated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "requires_human_approval": self.requires_human_approval,
            "reasons": self.reasons,
            "risk_escalated": self.risk_escalated,
        }


def _escalate_risk_by_history(level: str, has_history: bool) -> tuple[str, bool]:
    if not has_history:
        return level, False
    if level == "normal":
        return "moderado", True
    if level == "moderado":
        return "alto", True
    return level, False


def evaluate_autonomy(ctx: AutonomyContext) -> AutonomyResult:
    reasons: list[str] = []
    effective_risk = ctx.risk_level

    if ctx.injection_score >= settings.adversarial_threshold or ctx.adversarial_detected:
        effective_risk = "alto"
        reasons.append(
            f"padrão adversarial detectado (injection_score={ctx.injection_score})"
        )
    elif ctx.category in ("Integridade", "Segurança") or ctx.priority_level in ("P0", "P1"):
        effective_risk = "alto"
    elif ctx.category == "Disponibilidade" or ctx.priority_level == "P2":
        effective_risk = "moderado"

    effective_risk, escalated = _escalate_risk_by_history(effective_risk, ctx.history_considered)
    if escalated:
        reasons.append("risco elevado por histórico recente do mesmo sistema")

    requires_approval = False

    if effective_risk == "alto":
        requires_approval = True
        reasons.append(f"nível de risco efetivo = {effective_risk}")
    elif escalated and effective_risk in ("moderado",):
        requires_approval = True
        reasons.append("nível de risco efetivo escalonado = moderado requer aprovação humana")

    if ctx.injection_score >= settings.adversarial_threshold:
        requires_approval = True

    if ctx.category == "Integridade" and ctx.priority_level in ("P0", "P1"):
        requires_approval = True
        if "ações destrutivas com prioridade alta requerem aprovação" not in reasons:
            reasons.append("ações destrutivas (Integridade) com prioridade alta requerem aprovação")

    return AutonomyResult(
        requires_human_approval=requires_approval,
        reasons=reasons,
        risk_escalated=escalated,
    )


def requires_human_approval(
    *,
    risk_level: str = "normal",
    priority_level: str = "P4",
    category: str | None = None,
    injection_score: float = 0.0,
    adversarial_detected: bool = False,
    history_considered: bool = False,
) -> bool:
    ctx = AutonomyContext(
        risk_level=risk_level,
        priority_level=priority_level,
        category=category,
        injection_score=injection_score,
        adversarial_detected=adversarial_detected,
        history_considered=history_considered,
    )
    return evaluate_autonomy(ctx).requires_human_approval

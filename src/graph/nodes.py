from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from src.config import settings
from src.errors.app_error import GraphMaxStepsError
from src.graph.state import (
    Analysis,
    Classification,
    OutputDto,
    PriorityAssessment,
    Recommendation,
    RiskAssessment,
    RiskLevel,
    Status,
    ToolResult,
    TriageState,
)
from src.security.autonomy import AutonomyContext, evaluate_autonomy
from src.security.input_validator import validate_incident_payload
from src.tools.kb_client import query_incident_knowledge_base

# ---------------------------------------------------------------------------
# Utilitários locais
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _check_max_steps(current: int) -> None:
    if current + 1 > settings.max_steps:
        raise GraphMaxStepsError(
            f"Execução excedeu MAX_STEPS={settings.max_steps}",
            context={"step_count": current},
        )


def _safe_text(state: TriageState) -> str:
    raw = state["raw_input"]
    return raw.get("description", "") or ""


# ---------------------------------------------------------------------------
# Mock / fallback determinístico LLM
# DECISÃO TÉCNICA: Modo fallback por regras quando OpenAI key ausente.
# ---------------------------------------------------------------------------

def _fallback_analyze(text: str) -> Analysis:
    kw = sorted(set(re.findall(r"[A-Za-zÀ-ÿ]{4,}", text)))[:10]
    systems = ["relatorios", "vendas", "banco de dados", "api", "login", "cache", "rede"]
    affected = next((s for s in systems if s.lower() in text.lower()), "indefinido")
    return Analysis(
        summary=f"Análise por regras: {text[:180]}{'...' if len(text) > 180 else ''}",
        keywords=kw,
        affected_system=affected,
        symptoms=["geral"],
        impact="desconhecido",
    )


def _fallback_classify(text: str) -> Classification:
    t = text.lower()
    if any(w in t for w in ["banco", "dados", "tabela", "drop", "delete", "update", "schema"]):
        return Classification(category="Integridade", subcategory="Dados", kind="Destrutiva")
    if any(w in t for w in ["lento", "lentidão", "performance", "carrega", "demora"]):
        return Classification(category="Disponibilidade", subcategory="Performance", kind="Degradação")
    if any(w in t for w in ["indisponível", "fora do ar", "caiu", "não abre", "5xx", "timeout"]):
        return Classification(category="Disponibilidade", subcategory="Indisponibilidade", kind="Outage")
    if any(w in t for w in ["autenticação", "senha", "login", "token", "acesso", "permissão"]):
        return Classification(category="Segurança", subcategory="Autenticação", kind="Acesso")
    return Classification(category="Operacional", subcategory="Geral", kind="Outro")


def _fallback_priority(text: str) -> PriorityAssessment:
    t = text.lower()
    score = 0.3
    high_words = ["produção", "producao", "crítico", "critico", "urgente", "varios usuarios", "muitos usuários",
                  "todos", "drop", "apagando", "deletando", "fora do ar", "não carrega", "p0", "p1"]
    for w in high_words:
        if w in t:
            score += 0.2
    score = round(min(score, 1.0), 3)
    if score >= 0.8:
        level = "P0"
    elif score >= 0.6:
        level = "P1"
    elif score >= 0.35:
        level = "P2"
    elif score >= 0.15:
        level = "P3"
    else:
        level = "P4"
    return PriorityAssessment(level=level, score=score, urgency="por score", impact="por score")


# ---------------------------------------------------------------------------
# Nós — retornam partial dict apenas com campos próprios + step_count = 1
# ---------------------------------------------------------------------------

def bootstrap_execution(state: TriageState) -> dict[str, Any]:
    _check_max_steps(state.get("step_count", 0))
    try:
        from src.observability.logging import set_execution_context

        set_execution_context(state["execution_id"])
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.observability.audit import audit_log

        audit_log.append(
            execution_id=state["execution_id"],
            etapa="bootstrap_execution",
            antes=None,
            depois="received",
            decision=f"source_system={state.get('source_system')}",
            adversarial=bool(state.get("adversarial_detected")),
            duration_ms=0,
        )
        return {"step_count": 1, "audit_refs": [f"bootstrap:{state['execution_id']}"]}
    except Exception:  # noqa: BLE001
        return {"step_count": 1, "audit_refs": []}


def validate_request(state: TriageState) -> dict[str, Any]:
    _check_max_steps(state.get("step_count", 0))
    result = validate_incident_payload(state["raw_input"])
    return {
        "validation_errors": list(result.errors),
        "validated": result.valid,
        "injection_score": result.injection_score,
        "adversarial_detected": result.adversarial_detected,
        "step_count": 1,
    }


def analyze_request(state: TriageState) -> dict[str, Any]:
    _check_max_steps(state.get("step_count", 0))
    analysis = _fallback_analyze(_safe_text(state))
    return {"analysis": analysis, "llm_fallback": True, "step_count": 1}


def classify_incident(state: TriageState) -> dict[str, Any]:
    _check_max_steps(state.get("step_count", 0))
    return {"classification": _fallback_classify(_safe_text(state)), "step_count": 1}


def analyze_priority(state: TriageState) -> dict[str, Any]:
    _check_max_steps(state.get("step_count", 0))
    return {"priority": _fallback_priority(_safe_text(state)), "step_count": 1}


def tool_invoke(state: TriageState) -> dict[str, Any]:
    _check_max_steps(state.get("step_count", 0))
    desc = _safe_text(state)
    response = query_incident_knowledge_base({"query": desc[:300], "top_k": 5})
    items_as_dict = [i.model_dump() for i in response.items]
    tr: ToolResult = ToolResult(
        query=response.query,
        items=items_as_dict,
        fallback=response.fallback,
        error_message=response.error_message,
        retry_count=response.retry_count,
        duration_ms=response.duration_ms,
    )
    return {"tool_results": [tr], "step_count": 1}


def evaluate_risk(state: TriageState) -> dict[str, Any]:
    _check_max_steps(state.get("step_count", 0))
    classification = state.get("classification", {}) or {}
    priority = state.get("priority", {}) or {}
    hist = bool(state.get("history_refs"))
    ctx = AutonomyContext(
        risk_level="normal",
        priority_level=priority.get("level", "P4"),
        category=classification.get("category"),
        subcategory=classification.get("subcategory"),
        injection_score=float(state.get("injection_score", 0.0) or 0.0),
        adversarial_detected=bool(state.get("adversarial_detected")),
        history_considered=hist,
    )
    autonomy = evaluate_autonomy(ctx)

    # Risco efetivo inicializado no AutonomyContext (normal) + regras em evaluate_autonomy.
    # Deriva 'risk_level' de forma transparente (cópia da lógica interna para expor no DTO).
    if autonomy.risk_escalated or autonomy.requires_human_approval or "risco elevado por histórico" in " ".join(autonomy.reasons):
        # Inferir o nível efetivo baseado nas decisões.
        if autonomy.requires_human_approval:
            level: RiskLevel = "alto"
        elif hist:
            level = "moderado"
        else:
            level = "normal"
    else:
        cat = classification.get("category")
        p = priority.get("level", "P4")
        if cat in ("Integridade", "Segurança") or p in ("P0", "P1"):
            level = "alto"
        elif cat == "Disponibilidade" or p == "P2":
            level = "moderado"
        else:
            level = "normal"
    if autonomy.risk_escalated and level != "alto":
        level = "alto" if level == "moderado" else "moderado"
    just = "; ".join(autonomy.reasons) if autonomy.reasons else f"risk_level={level}"
    assessment = RiskAssessment(
        risk_level=level,
        requires_approval=autonomy.requires_human_approval,
        justification=just,
        meta={
            "history_considered": hist,
            "risk_escalated": autonomy.risk_escalated,
            "autonomy_reasons": list(autonomy.reasons),
        },
    )
    return {
        "risk_assessment": assessment,
        "requires_approval": autonomy.requires_human_approval,
        "step_count": 1,
    }


def finalize_normal(state: TriageState) -> dict[str, Any]:
    _check_max_steps(state.get("step_count", 0))
    classification = state.get("classification", {}) or {}
    cat = classification.get("category", "Geral")
    sub = classification.get("subcategory", "")
    actions = [
        f"Investigar modulo de {cat.lower()} ({sub.lower()})",
        "Validar metricas de disponibilidade e performance",
        "Aplicar acao corretiva e documentar",
    ]
    rec: Recommendation = Recommendation(
        text=f"Ação automática recomendada para categoria {cat}/{sub}.",
        suggested_actions=actions,
        blocked_by_policy=False,
        approval_notes=None,
    )
    return {"final_recommendation": rec, "step_count": 1}


def finalize_risky(state: TriageState) -> dict[str, Any]:
    _check_max_steps(state.get("step_count", 0))
    meta = ((state.get("risk_assessment") or {}).get("meta") or {})
    reasons = list(meta.get("autonomy_reasons") or [])
    if state.get("adversarial_detected") and not any("adversarial" in r or "injection" in r for r in reasons):
        reasons.append(f"tentativa de prompt injection (score={state.get('injection_score')})")
    if not reasons:
        reasons.append("política de segurança aplicada")
    notes = " | ".join(reasons)
    rec: Recommendation = Recommendation(
        text="Ação automática BLOQUEADA por política de governança. Aguardar aprovação humana.",
        suggested_actions=["Solicitar aprovação de responsável", "Analisar justificativa acima"],
        blocked_by_policy=True,
        approval_notes=notes,
    )
    return {"final_recommendation": rec, "step_count": 1}


def emit_output(state: TriageState) -> dict[str, Any]:
    _check_max_steps(state.get("step_count", 0))
    status: Status = "BLOQUEADO_PENDENTE_APROVACAO" if state.get("requires_approval") else "TRIAGEM_CONCLUIDA"
    risk_assessment = state.get("risk_assessment", {}) or {}
    risk_level = risk_assessment.get("risk_level", "normal")
    analysis = state.get("analysis", {}) or {}
    classification = state.get("classification", Classification())
    priority = state.get("priority", PriorityAssessment())
    rec = state.get("final_recommendation", Recommendation())
    started = datetime.fromisoformat(state["received_at"])
    finished = datetime.now(UTC)
    duration_ms = int((finished - started).total_seconds() * 1000)
    desc_hash = hashlib.sha1(_safe_text(state).encode("utf-8", errors="ignore")).hexdigest()[:12]
    audit_refs_extra: list[str] = []
    dto: OutputDto = OutputDto(
        execution_id=state["execution_id"],
        status=status,
        classification=classification,
        priority=priority,
        risk_level=risk_level,
        analysis_summary=analysis.get("summary", ""),
        recommendation=rec,
        requires_approval=bool(state.get("requires_approval")),
        created_at=state["received_at"],
        finished_at=finished.isoformat(),
        evidence_refs=[
            f"audit:{state['execution_id']}",
            f"payload_hash:{desc_hash}",
        ],
        duration_ms=duration_ms,
        adversarial_detected=bool(state.get("adversarial_detected")),
        llm_fallback=bool(state.get("llm_fallback")),
    )
    # low-code n8n
    if risk_level in ("moderado", "alto") or priority.get("level", "P4") in ("P0", "P1"):
        try:
            from src.lowcode.n8n_client import post_webhook
            r = post_webhook(dto)
            audit_refs_extra.append(f"n8n_webhook:sent:{_now_iso()}:{getattr(r, 'status_code', 'none')}")
        except Exception as exc:  # noqa: BLE001
            audit_refs_extra.append(f"n8n_webhook:failed:{exc!r}")
    # auditoria (persistência é feita em service.py após ainvoke)
    try:
        from src.observability.audit import audit_log
        audit_log.append(
            execution_id=state["execution_id"],
            etapa="emit_output",
            antes=state.get("requires_approval", None),
            depois=dto["status"],
            decision=f"status={status}",
            adversarial=bool(state.get("adversarial_detected")),
            duration_ms=duration_ms,
        )
        audit_refs_extra.append(f"audit:{state['execution_id']}:emit_output")
    except Exception as exc:  # noqa: BLE001
        audit_refs_extra.append(f"audit_error:{exc!r}")
    return {"output_dto": dto, "audit_refs": audit_refs_extra, "step_count": 1}


def _as_jsonable(obj: Any) -> Any:
    import json as _json
    try:
        _json.dumps(obj, ensure_ascii=False)
        return obj
    except (TypeError, ValueError):
        if isinstance(obj, dict):
            return {str(k): _as_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_as_jsonable(x) for x in obj]
        return str(obj)

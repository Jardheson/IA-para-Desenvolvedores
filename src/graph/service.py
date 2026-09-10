from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.config import settings
from src.errors.app_error import AppError, ValidationError
from src.graph.graph import graph
from src.graph.state import (
    Analysis,
    Classification,
    OutputDto,
    PriorityAssessment,
    Recommendation,
    RiskAssessment,
    TriageState,
)
from src.memory.store import execution_store


def _initial_state(raw_input: dict[str, Any]) -> TriageState:
    reporter = raw_input.get("reporter")
    source_system = raw_input.get("source_system")
    now = datetime.now(UTC).isoformat()
    # carrega referências de histórico para o mesmo source_system
    history_refs: list[str] = []
    if source_system:
        recent = execution_store.list_recent_by_system(source_system, window_hours=24)
        history_refs = [r["execution_id"] for r in recent[-5:]]
    return TriageState(
        execution_id=str(uuid4()),
        received_at=now,
        raw_input=raw_input,
        validated=False,
        validation_errors=[],
        injection_score=0.0,
        adversarial_detected=False,
        llm_fallback=False,
        analysis=Analysis(),
        classification=Classification(),
        priority=PriorityAssessment(),
        tool_results=[],
        risk_assessment=RiskAssessment(),
        requires_approval=False,
        final_recommendation=Recommendation(),
        output_dto=OutputDto(),
        audit_refs=[],
        step_count=0,
        history_refs=history_refs,
        source_system=source_system,
        reporter=reporter,
    )


async def run_triage(raw_input: dict[str, Any]) -> OutputDto:
    if not isinstance(raw_input, dict):
        raise ValidationError("payload deve ser objeto JSON")
    state = _initial_state(raw_input)
    try:
        result = await graph.ainvoke(
            state,
            config={"recursion_limit": max(50, settings.max_steps * 3 + 10)},
        )
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AppError("erro interno no grafo", context={"error": repr(exc)}) from exc
    dto = result.get("output_dto")
    if not dto:
        raise AppError("grafo terminou sem produzir output_dto")
    # Persistência final (state completo com step_count real já somados pelo LangGraph)
    try:
        from src.memory.store import execution_store as _store

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

        _store.save(dto.get("execution_id") or result.get("execution_id") or state["execution_id"],
                    _as_jsonable(dict(result)))
    except Exception as exc:  # noqa: BLE001
        from src.observability.logging import get_logger

        get_logger("service").warning("falhou persistência execução: %r", exc)
    return dto


def run_triage_sync(raw_input: dict[str, Any]) -> OutputDto:
    import asyncio
    return asyncio.run(run_triage(raw_input))

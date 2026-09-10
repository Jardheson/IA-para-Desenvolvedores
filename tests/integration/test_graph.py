from __future__ import annotations

from src.graph.service import run_triage_sync


def test_run_triage_sync_happy_path_returns_output_dto_typed():
    payload = {
        "description": (
            "Usuários reportam lentidão ao carregar o relatório de vendas "
            "no período da manhã. Muitos usuários foram afetados hoje."
        ),
        "reporter": "ana.silva",
        "source_system": "sistema-vendas",
    }

    dto = run_triage_sync(payload)

    assert isinstance(dto, dict)

    # Campos obrigatórios do OutputDto — verificando tipos
    assert isinstance(dto["execution_id"], str) and dto["execution_id"]
    assert dto["status"] in {"TRIAGEM_CONCLUIDA", "BLOQUEADO_PENDENTE_APROVACAO", "ERRO", "PROCESSING"}
    assert isinstance(dto["classification"], dict)
    assert "category" in dto["classification"]
    assert isinstance(dto["priority"], dict)
    assert dto["priority"]["level"] in {"P0", "P1", "P2", "P3", "P4"}
    assert isinstance(dto["priority"]["score"], float)
    assert dto["risk_level"] in {"normal", "moderado", "alto"}
    assert isinstance(dto["analysis_summary"], str)
    assert isinstance(dto["recommendation"], dict)
    assert isinstance(dto["requires_approval"], bool)
    assert isinstance(dto["created_at"], str) and dto["created_at"]
    assert isinstance(dto["finished_at"], str) and dto["finished_at"]
    assert isinstance(dto["evidence_refs"], list)
    assert all(isinstance(r, str) for r in dto["evidence_refs"])
    assert isinstance(dto["duration_ms"], int)
    assert isinstance(dto["adversarial_detected"], bool)
    assert isinstance(dto["llm_fallback"], bool)

    # Campos aninhados tipados: recommendation
    rec = dto["recommendation"]
    assert isinstance(rec["text"], str)
    assert isinstance(rec["suggested_actions"], list)
    assert isinstance(rec["blocked_by_policy"], bool)
    assert "approval_notes" in rec

    # Campos aninhados: classification
    cls = dto["classification"]
    for k in ("category", "subcategory", "kind"):
        assert isinstance(cls.get(k, ""), str)


def test_run_triage_sync_step_count_at_least_9():
    payload = {
        "description": (
            "Lentidão no carregamento do painel de controle, sistema de vendas "
            "fora do ar para vários usuários."
        ),
        "source_system": "painel-admin",
    }
    from src.memory.store import execution_store

    dto = run_triage_sync(payload)
    stored = execution_store.load(dto["execution_id"])
    assert stored is not None
    assert "step_count" in stored
    assert stored["step_count"] >= 9


def test_run_triage_sync_history_refs_populated_on_repeated_source_system():
    payload_1 = {
        "description": "Primeiro incidente: login falhando intermitentemente.",
        "source_system": "sso-auth",
    }
    dto1 = run_triage_sync(payload_1)

    payload_2 = {
        "description": "Segundo incidente: timeout no endpoint de autenticação.",
        "source_system": "sso-auth",
    }
    from src.memory.store import execution_store

    dto2 = run_triage_sync(payload_2)
    stored2 = execution_store.load(dto2["execution_id"])
    assert stored2 is not None
    history = stored2.get("history_refs") or []
    assert isinstance(history, list)
    assert dto1["execution_id"] in history

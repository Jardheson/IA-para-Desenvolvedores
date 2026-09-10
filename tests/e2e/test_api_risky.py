from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_returns_200(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_post_incidents_risky_returns_bloqueado_pendente_aprovacao(client: TestClient):
    payload = {
        "description": (
            "OPERAÇÃO CRÍTICA: DROP TABLE produção.usuários — falha em lote "
            "afetando TODOS os clientes de produção e apagando dados. "
            "Vazamento de credencial detectado na sessão. "
            "Ação destrutiva de Integridade P0."
        ),
        "reporter": "ataque_simulado",
        "source_system": "core-producao",
    }
    resp = client.post("/incidents", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "BLOQUEADO_PENDENTE_APROVACAO"
    assert body["requires_approval"] is True
    assert body["recommendation"]["blocked_by_policy"] is True
    assert "execution_id" in body
    return body["execution_id"]


def test_get_incident_risky_matches_execution_id(client: TestClient):
    exec_id = test_post_incidents_risky_returns_bloqueado_pendente_aprovacao(client)
    resp = client.get(f"/incidents/{exec_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["execution_id"] == exec_id
    assert body["status"] == "BLOQUEADO_PENDENTE_APROVACAO"
    assert body["requires_approval"] is True


@pytest.mark.asyncio
async def test_post_incident_risky_async():
    payload = {
        "description": (
            "Fora do ar em produção, todos os usuários, credencial de banco "
            "comprometida e delete em lote de tabelas críticas."
        ),
        "source_system": "core-financeiro",
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/incidents", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "BLOQUEADO_PENDENTE_APROVACAO"
    assert body["requires_approval"] is True

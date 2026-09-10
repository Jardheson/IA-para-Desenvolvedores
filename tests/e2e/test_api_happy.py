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
    body = resp.json()
    assert body["status"] == "ok"
    assert "storage" in body
    assert "max_steps" in body


def test_post_incidents_happy_path_returns_triage_concluida(client: TestClient):
    payload = {
        "description": (
            "Tela de cadastro de clientes exibindo alerta visual no formulário. "
            "Equipe de produto relatou ajuste desejado para a próxima release."
        ),
        "reporter": "marco.santos",
        "source_system": "modulo-cadastro",
    }
    resp = client.post("/incidents", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "TRIAGEM_CONCLUIDA"
    assert body["requires_approval"] is False
    assert body["adversarial_detected"] is False
    assert "execution_id" in body and body["execution_id"]
    return body["execution_id"]


def test_get_incident_by_id_matches_execution_id(client: TestClient):
    exec_id = test_post_incidents_happy_path_returns_triage_concluida(client)
    resp = client.get(f"/incidents/{exec_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["execution_id"] == exec_id
    assert body["status"] == "TRIAGEM_CONCLUIDA"


@pytest.mark.asyncio
async def test_health_async_httpx_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200

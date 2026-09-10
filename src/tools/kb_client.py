from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings
from src.errors.app_error import ToolExecutionError
from src.tools.schemas import KBItem, KBQueryRequest, KBQueryResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock data (usado quando TOOL_USE_MOCK=true)
# ---------------------------------------------------------------------------

_MOCK_DB: list[KBItem] = [
    KBItem(id="KB-2024-101", title="Cache miss causing reports slow load",
           category="Disponibilidade", summary="Service de relatórios com erro 5xx e lentidão por cache expirado.",
           similarity=0.93),
    KBItem(id="KB-2024-102", title="Database drop table detected",
           category="Integridade", summary="Alerta de integridade: comandos DROP executados em produção.",
           similarity=0.90),
    KBItem(id="KB-2024-103", title="Auth token leak in logs",
           category="Segurança", summary="Tokens expostos em logs da aplicação.",
           similarity=0.88),
    KBItem(id="KB-2024-104", title="Payment gateway timeout",
           category="Disponibilidade", summary="Timeouts recorrentes em gateway de pagamentos.",
           similarity=0.85),
    KBItem(id="KB-2024-105", title="SQL injection in public form",
           category="Segurança", summary="Formulário público vulnerável a SQLi.",
           similarity=0.82),
    KBItem(id="KB-2024-106", title="High latency on sales dashboard",
           category="Performance", summary="Painel de vendas com latência > p95 em horário de pico.",
           similarity=0.80),
]


def _mock_search(query: str, top_k: int) -> KBQueryResponse:
    q = query.lower()
    scored: list[tuple[float, KBItem]] = []
    for item in _MOCK_DB:
        s = 0.0
        haystack = f"{item.title} {item.summary} {item.category}".lower()
        for word in q.split():
            if len(word) > 2 and word in haystack:
                s += 0.2
        s = s + item.similarity * 0.5
        scored.append((min(s, 1.0), item))
    scored.sort(key=lambda x: x[0], reverse=True)
    items = [KBItem(**{**i.model_dump(), "similarity": round(s, 3)})
             for s, i in scored[:top_k]]
    return KBQueryResponse(query=query, items=items, fallback=False,
                           retry_count=0, duration_ms=12,
                           meta={"source": "mock"})


# ---------------------------------------------------------------------------
# HTTP real + retry/fallback
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=0.3, max=5.0),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError)),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),  # type: ignore[arg-type]
)
def _http_search(query: str, top_k: int) -> KBQueryResponse:
    t0 = time.perf_counter()
    url = settings.tool_kb_api_url
    attempts = int(getattr(_http_search.retry.statistics, "attempt_number", 1))  # type: ignore[attr-defined]
    try:
        with httpx.Client(timeout=settings.http_timeout_seconds) as client:
            resp = client.get(url, params={"query": query, "top_k": top_k})
            resp.raise_for_status()
            data = resp.json()
            raw_items: list[dict[str, Any]] = data.get("entries", data.get("items", []))
            items: list[KBItem] = []
            for idx, raw in enumerate(raw_items[:top_k]):
                items.append(KBItem(
                    id=str(raw.get("id", f"http-{idx}")),
                    title=str(raw.get("title") or raw.get("API") or raw.get("Name") or "item"),
                    category=str(raw.get("category") or raw.get("Category") or ""),
                    summary=str(raw.get("summary") or raw.get("Description") or "")[:200],
                    similarity=round(float(raw.get("similarity", 0.7 - (idx * 0.03))), 3),
                ))
            dur = int((time.perf_counter() - t0) * 1000)
            return KBQueryResponse(
                query=query,
                items=items,
                fallback=False,
                retry_count=attempts - 1,
                duration_ms=dur,
                meta={"source": "http", "status_code": resp.status_code},
            )
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("tool KB falhou HTTP tentativa=%s: %r", attempts, exc)
        raise


# ---------------------------------------------------------------------------
# Entrada pública
# ---------------------------------------------------------------------------

def query_incident_knowledge_base(params: KBQueryRequest | dict[str, Any]) -> KBQueryResponse:
    """Consulta base de conhecimento e retorna resposta tipada com retry/fallback.

    - Se TOOL_USE_MOCK=True, retorna dados locais.
    - Caso contrário, realiza HTTP com 3 retries + fallback para vazio marcado.
    - Validação de entrada via Pydantic; erros de schema são ValidationError.
    """
    if isinstance(params, dict):
        params = KBQueryRequest(**params)
    if not isinstance(params, KBQueryRequest):
        raise ToolExecutionError("params KB invalidos",
                                 context={"type": type(params).__name__})
    t0 = time.perf_counter()
    if settings.tool_use_mock:
        r = _mock_search(params.query, params.top_k)
        return r
    try:
        return _http_search(params.query, params.top_k)
    except RetryError as exc:
        dur = int((time.perf_counter() - t0) * 1000)
        logger.warning("tool KB excedeu tentativas, entrando em fallback: %r", exc)
        return KBQueryResponse(
            query=params.query,
            items=[],
            fallback=True,
            error_message=f"RetryError: 3 tentativas falharam ({exc.__cause__!r})",
            retry_count=3,
            duration_ms=dur,
            meta={"source": "fallback_after_retry_error"},
        )
    except Exception as exc:  # noqa: BLE001
        dur = int((time.perf_counter() - t0) * 1000)
        logger.warning("tool KB fallback por exceção genérica: %r", exc)
        return KBQueryResponse(
            query=params.query,
            items=[],
            fallback=True,
            error_message=repr(exc),
            retry_count=0,
            duration_ms=dur,
            meta={"source": "fallback_unexpected"},
        )

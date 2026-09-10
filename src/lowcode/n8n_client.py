from __future__ import annotations

import logging
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


def post_webhook(payload: dict[str, Any]) -> httpx.Response | None:
    """Envia payload estruturado para o webhook n8n (automação low-code/no-code).

    Se a variável N8N_WEBHOOK_URL estiver vazia, apenas loga e retorna None.
    Em caso de erro, loga warning e NÃO LEVANTA exceção para não quebrar a cadeia.
    """
    url = settings.n8n_webhook_url
    if not url:
        logger.warning("N8N_WEBHOOK_URL não configurada; pulando webhook low-code")
        return None
    try:
        r = httpx.post(url, json=payload, timeout=10)
        logger.info("n8n webhook enviado",
                    extra={"node": "emit_output", "event": "n8n_webhook",
                           "duration_ms": -1, "decision": f"status={r.status_code}"})
        return r
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n webhook falhou: %r", exc)
        return None

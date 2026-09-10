from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.observability.logging import audit_log  # noqa: F401  (garante inicialização logging)


def _safe_jsonl_iter(path: Path):
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def build_timeline(execution_id: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    s = get_settings()
    for entry in _safe_jsonl_iter(s.storage_path / "audit_events.jsonl"):
        if entry.get("execution_id") == execution_id:
            events.append({
                "source": "audit",
                "ts": entry.get("ts", ""),
                "node": entry.get("etapa"),
                "event": entry.get("etapa"),
                "details": {k: v for k, v in entry.items()
                            if k not in ("ts", "execution_id", "etapa")},
            })
    log_path = s.storage_path / "triagem.log"
    for entry in _safe_jsonl_iter(log_path):
        if entry.get("execution_id") == execution_id:
            events.append({
                "source": "log",
                "ts": entry.get("ts", ""),
                "node": entry.get("node"),
                "event": entry.get("event") or entry.get("message", ""),
                "details": entry,
            })
    events.sort(key=lambda e: e.get("ts", ""))
    return events

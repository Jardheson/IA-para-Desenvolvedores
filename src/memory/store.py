from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.config import get_settings


class ExecutionStore:
    """Persiste estado das execuções como JSON no STORAGE_PATH/executions.

    Mantém também um índice (index.jsonl) para busca rápida por source_system.
    """

    def __init__(self, base: Path | None = None) -> None:
        self._base_override = Path(base) if base else None

    @property
    def base(self) -> Path:
        if self._base_override is not None:
            base = self._base_override
        else:
            s = get_settings()
            s.ensure_storage()
            base = s.storage_path
        base = Path(base)
        (base / "executions").mkdir(parents=True, exist_ok=True)
        return base

    @property
    def exec_dir(self) -> Path:
        return self.base / "executions"

    @property
    def index_path(self) -> Path:
        return self.base / "index.jsonl"

    def save(self, execution_id: str, state: dict[str, Any]) -> Path:
        path = self.exec_dir / f"{execution_id}.json"
        with path.open("w", encoding="utf-8") as fp:
            json.dump(state, fp, ensure_ascii=False, indent=2, default=str)
        entry = {
            "execution_id": execution_id,
            "received_at": state.get("received_at"),
            "source_system": state.get("source_system"),
            "risk_level": state.get("risk_assessment", {}).get("risk_level"),
            "requires_approval": state.get("requires_approval"),
        }
        with self.index_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return path

    def load(self, execution_id: str) -> dict[str, Any] | None:
        path = self.exec_dir / f"{execution_id}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fp:
            return json.load(fp)

    def list_recent_by_system(self, source_system: str, window_hours: int = 24) -> list[dict[str, Any]]:
        if not source_system or not self.index_path.exists():
            return []
        cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
        out: list[dict[str, Any]] = []
        with self.index_path.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("source_system") != source_system:
                    continue
                ts = entry.get("received_at")
                if ts:
                    try:
                        if datetime.fromisoformat(ts) < cutoff:
                            continue
                    except ValueError:
                        pass
                out.append(entry)
        return out


execution_store = ExecutionStore()

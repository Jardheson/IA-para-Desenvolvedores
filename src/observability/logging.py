from __future__ import annotations

import atexit
import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pythonjsonlogger import jsonlogger

from src.config import settings

_context_exec_id: threading.local = threading.local()


def set_execution_context(execution_id: str | None) -> None:
    _context_exec_id.value = execution_id


def get_execution_context() -> str | None:
    return getattr(_context_exec_id, "value", None)


class ExecutionContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.execution_id = get_execution_context() or "-"
        return True


def setup_logging() -> None:
    """Inicializa logger estruturado JSON (Sinal 1 de observabilidade)."""
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(settings.log_level)
    handler = logging.StreamHandler()
    fmt = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(execution_id)s %(message)s "
        "%(node)s %(event)s %(decision)s %(tool)s %(error)s %(duration_ms)s",
        rename_fields={"levelname": "level", "asctime": "ts"},
        json_ensure_ascii=False,
    )
    handler.setFormatter(fmt)
    handler.addFilter(ExecutionContextFilter())
    root.addHandler(handler)

    # arquivo de log
    log_path: Path = settings.storage_path / "triagem.log"
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.addFilter(ExecutionContextFilter())
    root.addHandler(fh)

    # defaults para campos extras
    for _ in ("node", "event", "decision", "tool", "error", "duration_ms"):
        logging.Formatter.default_msec_format = "%s.%03d"

    root.debug("logging inicializado", extra=default_extra())


def default_extra() -> dict[str, Any]:
    return {
        "node": "-",
        "event": "-",
        "decision": "-",
        "tool": "-",
        "error": "-",
        "duration_ms": -1,
    }


def trace_node(node_name: str):
    """Decorator que injeta contexto, mede duração, loga início/fim e registra auditoria.

    Aplica a nós do LangGraph que recebem e retornam TriageState (assinatura síncrona).
    """
    import time
    from functools import wraps

    logger = logging.getLogger(node_name)

    @wraps(node_name)
    def decorator(func):
        @wraps(func)
        def wrapper(state):
            set_execution_context(state.get("execution_id"))
            extra_before = default_extra()
            extra_before.update({"node": node_name, "event": "node_started"})
            logger.info("start node %s", node_name, extra=extra_before)
            # MAX_STEPS check é feito dentro dos nós (increment_step)
            t0 = time.perf_counter()
            try:
                result = func(state)
            except Exception as exc:
                dur = int((time.perf_counter() - t0) * 1000)
                err_extra = default_extra()
                err_extra.update({"node": node_name, "event": "node_failed",
                                  "error": repr(exc), "duration_ms": dur})
                logger.exception("node falhou %s", node_name, extra=err_extra)
                audit_log.append(
                    execution_id=state.get("execution_id", "-"),
                    etapa=node_name,
                    antes=None,
                    depois=None,
                    decision="EXCEPTION",
                    adversarial=False,
                    error=repr(exc),
                    duration_ms=dur,
                )
                raise
            dur = int((time.perf_counter() - t0) * 1000)
            dec = "-"
            if node_name == "evaluate_risk":
                dec = "requires_approval=" + str(result.get("requires_approval"))
            elif node_name == "emit_output":
                dto = result.get("output_dto") or {}
                dec = f"status={dto.get('status')}"
            after = default_extra()
            after.update({
                "node": node_name,
                "event": "node_finished",
                "decision": dec,
                "duration_ms": dur,
            })
            logger.info("finish node %s", node_name, extra=after)
            audit_log.append(
                execution_id=result.get("execution_id", "-"),
                etapa=node_name,
                antes=None,
                depois=dec,
                decision=dec,
                adversarial=bool(result.get("adversarial_detected")),
                duration_ms=dur,
            )
            set_execution_context(None)
            return result
        return wrapper
    return decorator


class _AuditLog:
    """Sinal 2 de observabilidade: auditoria append-only JSONL."""

    def __init__(self) -> None:
        from src.config import get_settings

        s = get_settings()
        s.ensure_storage()
        self.path: Path = s.storage_path / "audit_events.jsonl"
        self._lock = threading.Lock()
        self._file = self.path.open("a", encoding="utf-8")
        atexit.register(self.close)

    def close(self) -> None:
        try:
            self._file.close()
        except Exception:  # noqa: BLE001
            pass

    def append(
        self,
        execution_id: str,
        etapa: str,
        antes: object = None,
        depois: object = None,
        decision: str = "",
        adversarial: bool = False,
        approver: str | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "execution_id": execution_id,
            "etapa": etapa,
            "antes": antes,
            "depois": depois,
            "decision": decision,
            "adversarial": bool(adversarial),
            "approver": approver,
            "error": error,
            "duration_ms": duration_ms,
        }
        line = json.dumps(payload, ensure_ascii=False, default=str)
        with self._lock:
            self._file.write(line + "\n")
            self._file.flush()


_audit_instance: _AuditLog | None = None
_audit_storage_path: str | None = None


def get_audit_log() -> _AuditLog:
    """Factory function que re-instancia singleton somente se storage_path mudar.

    Respeita re-configurações de settings.STORAGE_PATH (por exemplo em fixtures de
    teste que alteram env var e recarregam settings).
    """
    global _audit_instance, _audit_storage_path
    from src.config import settings

    current = str(settings.storage_path)
    if _audit_instance is None or _audit_storage_path != current:
        if _audit_instance is not None:
            try:
                _audit_instance.close()
            except Exception:  # noqa: BLE001
                pass
        _audit_instance = _AuditLog()
        _audit_storage_path = current
    return _audit_instance


# Proxy que sempre usa o factory — garante que fixtures ou recargas de settings
# (cache_clear) enxergam o storage path atual.
class _AuditLogProxy:
    def append(self, **kwargs):
        return get_audit_log().append(**kwargs)

    def close(self):
        return get_audit_log().close()


audit_log: _AuditLog | _AuditLogProxy = _AuditLogProxy()


setup_logging()

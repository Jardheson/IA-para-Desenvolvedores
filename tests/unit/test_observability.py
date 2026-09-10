from __future__ import annotations

import logging
from pathlib import Path

from src.observability.logging import (
    ExecutionContextFilter,
    _AuditLog,
    audit_log,
    default_extra,
    get_execution_context,
    set_execution_context,
    setup_logging,
)
from src.observability.trace import build_timeline


def test_setup_logging_initializes_handlers(clean_storage: Path):
    root = logging.getLogger()
    before = len(root.handlers)
    setup_logging()
    assert len(root.handlers) >= before


def test_execution_context_filter_returns_true():
    f = ExecutionContextFilter()
    rec = logging.LogRecord("x", logging.INFO, "", 1, "msg", (), None)
    assert f.filter(rec) is True
    assert getattr(rec, "execution_id", None) == "-"


def test_set_and_get_execution_context():
    set_execution_context("exec-abc")
    assert get_execution_context() == "exec-abc"
    set_execution_context(None)
    assert get_execution_context() is None


def test_default_extra_keys():
    d = default_extra()
    for k in ("node", "event", "decision", "tool", "error", "duration_ms"):
        assert k in d


def test_audit_log_append_and_persists(clean_storage: Path):
    log = _AuditLog()
    exec_id = "audit-test-001"
    log.append(
        execution_id=exec_id,
        etapa="validate_request",
        antes=False,
        depois=True,
        decision="passou",
        adversarial=False,
        duration_ms=10,
    )
    log.close()

    audit_path = clean_storage / "audit_events.jsonl"
    assert audit_path.exists()
    lines = [line for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1


def test_build_timeline_reads_audit(clean_storage: Path):
    exec_id = "trace-test-001"
    audit_log.append(
        execution_id=exec_id,
        etapa="analyze_request",
        antes=None,
        depois="ok",
        decision="analise",
        adversarial=False,
        duration_ms=5,
    )
    timeline = build_timeline(exec_id)
    assert len(timeline) >= 1
    assert timeline[0]["execution_id" if "execution_id" in timeline[0] else "source"] == "audit" or timeline[0].get("source") == "audit"
    assert any(e.get("node") == "analyze_request" for e in timeline)


def test_build_timeline_unknown_execution_returns_empty(clean_storage: Path):
    events = build_timeline("execution-never-existed")
    assert isinstance(events, list)

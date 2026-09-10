from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from src.config import get_settings


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("TOOL_USE_MOCK", "true")
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    # Reset audit log factory instance (sinais de observabilidade)
    try:
        import src.observability.logging as _logmod

        _logmod._audit_instance = None
        _logmod._audit_storage_path = None
    except Exception:
        pass
    # Reset execution store lazy properties? optional
    get_settings.cache_clear()
    from src.config import get_settings as gs
    s = gs()
    s.ensure_storage()
    yield s
    try:
        shutil.rmtree(tmp_path / "storage", ignore_errors=True)
    except Exception:
        pass
    get_settings.cache_clear()
    try:
        import src.observability.logging as _logmod

        _logmod._audit_instance = None
        _logmod._audit_storage_path = None
    except Exception:
        pass


@pytest.fixture
def storage_path(_setup_env) -> Path:
    return _setup_env.storage_path


@pytest.fixture
def clean_storage(_setup_env) -> Path:
    base: Path = _setup_env.storage_path
    for child in base.iterdir():
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
    _setup_env.ensure_storage()
    return base

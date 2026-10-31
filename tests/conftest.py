import pytest


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch, tmp_path):
    """Segunda-feira 23/03/2026 10:30 (logo após o último pedido da base) e outbox isolado."""
    monkeypatch.setenv("EMPORIO_NOW", "2026-03-23 10:30")
    from emporio_agent import config

    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path / "sessions")

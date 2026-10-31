"""Configuração central: caminhos, modelo e relógio da loja."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
SESSIONS_DIR = ROOT / "sessions"
OUTBOX_DIR = ROOT / "outbox"

MODEL = os.getenv("EMPORIO_MODEL", "claude-sonnet-5-5")
MAX_TOKENS = 1024
MAX_TOOL_ROUNDS = 8
TZ = ZoneInfo("America/Campo_Grande")


def now() -> datetime:
    """Hora atual da loja. `EMPORIO_NOW="AAAA-MM-DD HH:MM"` fixa o relógio (testes e exemplos)."""
    fixed = os.getenv("EMPORIO_NOW")
    if fixed:
        fmt = "%Y-%m-%d %H:%M" if len(fixed) > 10 else "%Y-%m-%d"
        return datetime.strptime(fixed, fmt).replace(tzinfo=TZ)
    return datetime.now(TZ)

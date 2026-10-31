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

# Provedores via API compatível com OpenAI (/chat/completions). "groq" é o padrão.
PROVIDERS = {
    "groq": {"base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY", "model": "openai/gpt-oss-120b"},
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": None, "model": "qwen2.5:7b"},
    "openai": {"base_url": "https://api.openai.com/v1", "key_env": "OPENAI_API_KEY", "model": "gpt-4.1-mini"},
}
MAX_TOKENS = 1024
TEMPERATURE = 0.3
MAX_TOOL_ROUNDS = 8
TZ = ZoneInfo("America/Campo_Grande")


def now() -> datetime:
    """Hora atual da loja. `EMPORIO_NOW="AAAA-MM-DD HH:MM"` fixa o relógio (testes e exemplos)."""
    fixed = os.getenv("EMPORIO_NOW")
    if fixed:
        fmt = "%Y-%m-%d %H:%M" if len(fixed) > 10 else "%Y-%m-%d"
        return datetime.strptime(fixed, fmt).replace(tzinfo=TZ)
    return datetime.now(TZ)


def provider() -> dict:
    """Resolve o provedor a cada chamada (permite trocar por variável de ambiente).

    LLM_PROVIDER=groq|ollama|openai (padrão groq); LLM_MODEL, LLM_BASE_URL e LLM_API_KEY sobrescrevem.
    """
    name = os.getenv("LLM_PROVIDER", "groq")
    preset = PROVIDERS.get(name, {"base_url": os.getenv("LLM_BASE_URL", ""), "key_env": None, "model": ""})
    key_env = preset["key_env"]
    return {
        "name": name,
        "base_url": os.getenv("LLM_BASE_URL", preset["base_url"]).rstrip("/"),
        "api_key": _real_key(os.getenv("LLM_API_KEY") or (os.getenv(key_env) if key_env else None)),
        "model": os.getenv("LLM_MODEL", preset["model"]),
        "needs_key": key_env is not None,
    }


def _real_key(value: str | None) -> str | None:
    """Placeholders do .env.example (ex.: 'gsk_...') contam como chave ausente."""
    if not value or value.endswith("...") or value.strip() == "":
        return None
    return value

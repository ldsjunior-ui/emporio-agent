"""Cliente mínimo para APIs compatíveis com OpenAI (/chat/completions): Groq, Ollama, OpenAI, Gemini...

Usa só `httpx` (já dependência transitiva), com retry em 429/5xx (o plano gratuito da Groq limita
requisições por minuto). A interface é uma só — `chat(messages, tools) -> dict` — para que o agente
não dependa de nenhum SDK e os testes usem um cliente falso.
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

from . import config


USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}  # acumulado do processo (medição de custo)


class LLMError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status

    @property
    def transient(self) -> bool:
        """Erros que valem retry/degradação (inclui o 400 'failed_generation' do gpt-oss na Groq,
        quando o modelo malforma um tool_call)."""
        return self.status in (None, 400, 429, 500, 502, 503) and (
            self.status != 400 or "failed_generation" in str(self) or "Parsing failed" in str(self)
        )


class ChatClient:
    def __init__(self, timeout: float | None = None, retries: int = 3):
        self.cfg = config.provider()
        if self.cfg["needs_key"] and not self.cfg["api_key"]:
            raise LLMError(
                f"Chave ausente para o provedor '{self.cfg['name']}'. Defina no .env (veja .env.example)."
            )
        self.http = httpx.Client(timeout=timeout or float(os.getenv("LLM_TIMEOUT", "180")))
        self.retries = retries

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.cfg["api_key"]:
            headers["Authorization"] = f"Bearer {self.cfg['api_key']}"
        body: dict[str, Any] = {
            "model": self.cfg["model"],
            "messages": messages,
            "max_tokens": config.MAX_TOKENS,
        }
        if tools:  # alguns provedores (Anthropic) recusam `tools` vazio
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if self.cfg["name"] != "anthropic":  # modelos Claude atuais recusam `temperature`
            body["temperature"] = config.TEMPERATURE
        last, status = "", None
        for attempt in range(self.retries + 1):
            resp = self.http.post(f"{self.cfg['base_url']}/chat/completions", json=body, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                u = data.get("usage") or {}
                USAGE["prompt_tokens"] += u.get("prompt_tokens", 0)
                USAGE["completion_tokens"] += u.get("completion_tokens", 0)
                USAGE["calls"] += 1
                return data["choices"][0]["message"]
            last, status = f"HTTP {resp.status_code}: {resp.text[:300]}", resp.status_code
            if resp.status_code in (429, 500, 502, 503) and attempt < self.retries:
                wait = float(resp.headers.get("retry-after", 2 ** attempt * 2))
                if wait > 30:  # cota esgotada (ex.: limite diário): esperar não adianta, falhe rápido
                    break
                time.sleep(wait)
                continue
            break
        raise LLMError(last, status)

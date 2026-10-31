"""Loop do agente: LLM com function calling (Anthropic Messages API)."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from . import config
from .prompts import system_prompt
from .tools import TOOL_SPECS, run_tool

FALLBACK = (
    "Opa, tive um problema aqui do meu lado e não consegui concluir. Pode tentar de novo em instantes? "
    "Se preferir, a equipe atende no (67) 3341-4444."
)


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    result: str


@dataclass
class Turn:
    reply: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class Agent:
    """Uma conversa. O histórico (`messages`) é reenviado a cada turno e pode ser persistido em JSON."""

    def __init__(self, client: Any = None, session_id: str | None = None, persist: bool = True):
        if client is None:
            import anthropic  # import tardio: testes usam cliente falso sem a dependência configurada

            client = anthropic.Anthropic()
        self.client = client
        self.session_id = session_id or uuid.uuid4().hex[:8]
        self.persist = persist
        self.messages: list[dict[str, Any]] = []
        self._load()

    # -- persistência ---------------------------------------------------------------------
    @property
    def _path(self):
        return config.SESSIONS_DIR / f"{self.session_id}.json"

    def _load(self) -> None:
        if self.persist and self._path.exists():
            self.messages = json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        if self.persist:
            config.SESSIONS_DIR.mkdir(exist_ok=True)
            self._path.write_text(json.dumps(self.messages, ensure_ascii=False, indent=1), encoding="utf-8")

    # -- turno ----------------------------------------------------------------------------
    def reply(self, user_text: str, on_tool: Callable[[ToolCall], None] | None = None) -> Turn:
        self.messages.append({"role": "user", "content": user_text})
        calls: list[ToolCall] = []
        checkpoint = len(self.messages)
        try:
            for _ in range(config.MAX_TOOL_ROUNDS):
                resp = self.client.messages.create(
                    model=config.MODEL,
                    max_tokens=config.MAX_TOKENS,
                    system=system_prompt(),
                    tools=TOOL_SPECS,
                    messages=self.messages,
                )
                blocks = [_clean(b) for b in resp.content]
                self.messages.append({"role": "assistant", "content": blocks})
                if resp.stop_reason != "tool_use":
                    text = "".join(b["text"] for b in blocks if b["type"] == "text").strip()
                    self._save()
                    return Turn(text or FALLBACK, calls)
                results = []
                for b in blocks:
                    if b["type"] != "tool_use":
                        continue
                    out = run_tool(b["name"], b["input"])
                    call = ToolCall(b["name"], b["input"], out)
                    calls.append(call)
                    if on_tool:
                        on_tool(call)
                    results.append({"type": "tool_result", "tool_use_id": b["id"], "content": out})
                self.messages.append({"role": "user", "content": results})
            raise RuntimeError("limite de rodadas de ferramentas excedido")
        except Exception:
            # Não deixa um histórico quebrado (tool_use sem tool_result) contaminar a sessão.
            del self.messages[checkpoint - 1:]
            raise


def _clean(block: Any) -> dict[str, Any]:
    """Reduz o bloco do SDK ao mínimo reenviável (evita campos extras rejeitados pela API)."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return {"type": "text", "text": ""}

"""Loop do agente: LLM com function calling (API compatível com OpenAI)."""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from . import config
from .llm import ChatClient, LLMError
from .prompts import system_prompt
from .tools import TOOL_SPECS, run_tool

FALLBACK = (
    "Opa, tive um problema aqui do meu lado e não consegui concluir. Pode tentar de novo em instantes? "
    "Se preferir, a equipe atende no (67) 3341-4444."
)

# Anthropic-style specs -> formato "function" da API compatível com OpenAI
OPENAI_TOOLS = [
    {"type": "function", "function": {"name": t["name"], "description": t["description"],
                                       "parameters": t["input_schema"]}}
    for t in TOOL_SPECS
]


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
    """Uma conversa. O histórico (`messages`, sem o system prompt) é reenviado a cada turno e pode ser
    persistido em JSON. O system prompt é remontado a cada turno (traz data/hora atual)."""

    def __init__(self, client: Any = None, session_id: str | None = None, persist: bool = True):
        self.client = client or ChatClient()
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

    def _guard(self, name: str, args: dict[str, Any]) -> str | None:
        """Trava determinística: ferramentas de pedido só rodam com dados que o CLIENTE de fato escreveu.
        Modelos pequenos inventam argumentos (ex.: order_id=12345, e-mail "fulano@..."); isso bloqueia a
        chamada, evita varrer pedidos por tentativa e impede que texto de ferramenta forje identidade."""
        if name not in ("consultar_pedido", "verificar_devolucao"):
            return None
        said = " ".join(m["content"] for m in self.messages if m["role"] == "user" and isinstance(m["content"], str))
        said_digits = re.sub(r"\D", "", said)
        contact = str(args.get("contato_do_cliente", "")).strip()
        order = str(args.get("order_id", "")).strip()
        ok_order = bool(order) and re.search(rf"(?<!\d){re.escape(order)}(?!\d)", said) is not None
        digits = re.sub(r"\D", "", contact)
        ok_contact = bool(contact) and (
            contact.lower() in said.lower() or (len(digits) >= 8 and digits in said_digits)
        )
        if ok_order and ok_contact:
            return None
        return json.dumps({"erro": "dados_nao_informados_pelo_cliente",
                           "mensagem": "Peça ao cliente o número do pedido e o e-mail ou telefone cadastrado; "
                                       "use somente o que ele escreveu, nunca valores inventados."}, ensure_ascii=False)

    def _chat(self, allow_tools: bool) -> dict[str, Any]:
        """Chama o modelo com resiliência em 3 camadas (padrão aprendido com gpt-oss na Groq):
        1) retry; 2) se ainda falhar por erro transitório, responde SEM ferramentas;
        3) nesse fallback o histórico é achatado em texto puro (tool_calls estruturados são o que o
        modelo malforma ao reler)."""
        system = [{"role": "system", "content": system_prompt()}]
        tools = OPENAI_TOOLS if allow_tools else []
        for _ in range(2):
            try:
                return self.client.chat(system + self.messages, tools)
            except LLMError as exc:
                if not exc.transient:
                    raise
        return self.client.chat(system + _flatten(self.messages), [])

    # -- turno ----------------------------------------------------------------------------
    def reply(self, user_text: str, on_tool: Callable[[ToolCall], None] | None = None) -> Turn:
        self.messages.append({"role": "user", "content": user_text})
        calls: list[ToolCall] = []
        checkpoint = len(self.messages)
        try:
            for round_ in range(config.MAX_TOOL_ROUNDS):
                # Última rodada: sem ferramentas, o modelo é obrigado a responder em texto.
                allow_tools = round_ < config.MAX_TOOL_ROUNDS - 1
                msg = self._chat(allow_tools)
                tool_calls = msg.get("tool_calls") or []
                self.messages.append(_clean(msg))
                if not tool_calls:
                    text = (msg.get("content") or "").strip()
                    self._save()
                    return Turn(text or FALLBACK, calls)
                for tc in tool_calls:
                    fn = tc["function"]
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    out = self._guard(fn["name"], args) or run_tool(fn["name"], args)
                    call = ToolCall(fn["name"], args, out)
                    calls.append(call)
                    if on_tool:
                        on_tool(call)
                    self.messages.append({"role": "tool", "tool_call_id": tc["id"], "content": out})
            raise RuntimeError("limite de rodadas de ferramentas excedido")
        except Exception:
            # Não deixa um histórico quebrado (tool_calls sem resposta) contaminar a sessão.
            del self.messages[checkpoint - 1:]
            raise


def _clean(msg: dict[str, Any]) -> dict[str, Any]:
    """Mantém só os campos reenviáveis (provedores devolvem extras como `reasoning`)."""
    out: dict[str, Any] = {"role": "assistant", "content": msg.get("content") or ""}
    if msg.get("tool_calls"):
        out["tool_calls"] = [
            {"id": tc["id"], "type": "function",
             "function": {"name": tc["function"]["name"], "arguments": tc["function"].get("arguments") or "{}"}}
            for tc in msg["tool_calls"]
        ]
    return out


def _flatten(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Histórico estruturado -> chat de texto: resultados de ferramentas viram contexto do usuário."""
    names: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    for m in messages:
        if m["role"] == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                names[tc["id"]] = tc["function"]["name"]
            if m.get("content"):
                out.append({"role": "assistant", "content": m["content"]})
        elif m["role"] == "tool":
            out.append({"role": "user", "content": f"[resultado de {names.get(m['tool_call_id'], 'ferramenta')}]: {m['content']}"})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out

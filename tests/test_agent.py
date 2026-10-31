import json

import pytest

from emporio_agent.agent import Agent
from emporio_agent.llm import ChatClient, LLMError


def say(t):
    return {"role": "assistant", "content": t}


def call(i, name, **args):
    return {"role": "assistant", "content": None,
            "tool_calls": [{"id": i, "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)}}]}


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.sent = []

    def chat(self, messages, tools):
        self.sent.append(messages[:])
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_loop_executa_ferramenta_e_devolve_texto():
    c = FakeClient(call("t1", "status_loja_agora"), say("Estamos abertos!"))
    turn = Agent(client=c, persist=False).reply("tá aberto?")
    assert turn.reply == "Estamos abertos!"
    assert [x.name for x in turn.tool_calls] == ["status_loja_agora"]
    second = c.sent[1]
    assert second[0]["role"] == "system"
    tool_msg = second[-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "t1"
    assert json.loads(tool_msg["content"])["loja_aberta"] is True


def test_argumentos_json_invalidos_viram_erro_de_ferramenta_nao_excecao():
    bad = {"role": "assistant", "content": None, "tool_calls": [
        {"id": "t1", "type": "function", "function": {"name": "obter_produto", "arguments": "{nao-json"}}]}
    turn = Agent(client=FakeClient(bad, say("ok")), persist=False).reply("oi")
    assert "erro" in turn.tool_calls[0].result and turn.reply == "ok"


def test_falha_transitoria_faz_retry_e_depois_degrada_sem_ferramentas():
    bad = LLMError("HTTP 400: failed_generation", 400)
    c = FakeClient(call("t1", "status_loja_agora"), bad, bad, say("Respondi sem ferramentas"))
    turn = Agent(client=c, persist=False).reply("oi")
    assert turn.reply == "Respondi sem ferramentas"
    last = c.sent[-1]  # fallback: histórico achatado, sem role=tool nem tool_calls
    assert all(m["role"] in ("system", "user", "assistant") and "tool_calls" not in m for m in last)
    assert any("[resultado de status_loja_agora]" in m["content"] for m in last)


def test_erro_nao_transitorio_propaga_sem_retry():
    c = FakeClient(LLMError("HTTP 401: invalid key", 401))
    with pytest.raises(LLMError):
        Agent(client=c, persist=False).reply("oi")
    assert len(c.sent) == 1


def test_erro_do_provedor_nao_corrompe_historico():
    a = Agent(client=FakeClient(call("t1", "status_loja_agora"), LLMError("boom", 401)), persist=False)
    with pytest.raises(LLMError):
        a.reply("oi")
    assert a.messages == []  # rollback completo do turno


def test_persistencia_retoma_sessao():
    Agent(client=FakeClient(say("Oi!")), session_id="abc").reply("olá")
    b = Agent(client=FakeClient(), session_id="abc")
    assert len(b.messages) == 2 and b.messages[0]["content"] == "olá"


def test_ultima_rodada_vai_sem_ferramentas_e_nunca_fica_em_loop():
    from emporio_agent import config

    class Loopy(FakeClient):
        def chat(self, messages, tools):
            self.sent.append((messages[:], tools))
            return call(f"t{len(self.sent)}", "status_loja_agora") if tools else say("fechando")

    c = Loopy()
    turn = Agent(client=c, persist=False).reply("oi")
    assert turn.reply == "fechando" and len(c.sent) == config.MAX_TOOL_ROUNDS
    assert c.sent[-1][1] == []


def test_provedor_sem_chave_falha_com_mensagem_clara(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(LLMError, match="Chave ausente"):
        ChatClient()


def test_ollama_nao_exige_chave(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert ChatClient().cfg["model"] == "qwen2.5:7b"

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


def test_guarda_bloqueia_argumentos_de_pedido_inventados_pelo_modelo():
    inventado = call("t1", "consultar_pedido", order_id=12345, contato_do_cliente="fulano@fulano.com")
    c = FakeClient(inventado, say("Pode me passar o número do pedido e seu e-mail?"))
    turn = Agent(client=c, persist=False).reply("Quero saber do meu pedido")
    assert "dados_nao_informados_pelo_cliente" in turn.tool_calls[0].result


def test_guarda_libera_quando_cliente_escreveu_os_dados():
    ok = call("t1", "consultar_pedido", order_id=8, contato_do_cliente="anacarol.ferreira@coldmail.com")
    c = FakeClient(ok, say("Seu pedido foi enviado."))
    turn = Agent(client=c, persist=False).reply("pedido 8, e-mail anacarol.ferreira@coldmail.com")
    assert "enviado" in turn.tool_calls[0].result


def test_handoff_bloqueia_fato_inventado_no_resumo():
    inv = call("t1", "encaminhar_para_humano", motivo="garantia",
               resumo="Produto na embalagem original, sem sinais de uso, defeito.")
    c = FakeClient(inv, say("ok"))
    turn = Agent(client=c, persist=False).reply("Quero abrir um chamado, o violão tem defeito")
    assert "resumo_com_fatos_nao_informados" in turn.tool_calls[0].result


def test_handoff_nao_abre_sozinho_apos_consulta():
    look = call("t1", "verificar_devolucao", order_id=7, contato_do_cliente="leticia.rocha@jmail.com", motivo="arrependimento")
    ticket = call("t2", "encaminhar_para_humano", motivo="devolucao_troca", resumo="Pedido 7 fora do prazo.")
    c = FakeClient(look, ticket, say("Fora do prazo. Quer que eu abra um chamado?"))
    turn = Agent(client=c, persist=False).reply("pedido 7, leticia.rocha@jmail.com")
    assert "cliente_nao_pediu_chamado" in turn.tool_calls[1].result


def test_handoff_libera_quando_cliente_pede():
    ticket = call("t1", "encaminhar_para_humano", motivo="reclamacao", resumo="Pedido atrasado.")
    c = FakeClient(ticket, say("Protocolo aberto."))
    turn = Agent(client=c, persist=False).reply("Pode abrir um chamado por favor")
    assert "protocolo" in turn.tool_calls[0].result


def test_resposta_vazia_tenta_de_novo():
    c = FakeClient(say(""), say("Oi!"))
    assert Agent(client=c, persist=False).reply("oi").reply == "Oi!"


def test_placeholder_do_env_example_conta_como_chave_ausente(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_...")
    with pytest.raises(LLMError, match="Chave ausente"):
        ChatClient()


def test_provedor_anthropic_usa_endpoint_de_compatibilidade(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-teste-qualquer")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    cfg = ChatClient().cfg
    assert cfg["base_url"] == "https://api.anthropic.com/v1" and cfg["model"].startswith("claude-")


def test_corpo_da_requisicao_omite_tools_vazio_e_temperature_na_anthropic(monkeypatch):
    sent = {}

    class R:
        status_code = 200
        headers = {}

        def json(self):
            return {"choices": [{"message": {"role": "assistant", "content": "ok"}}], "usage": {}}

    class H:
        def post(self, url, json, headers):
            sent.update(json)
            return R()

    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-teste-qualquer")
    c = ChatClient()
    c.http = H()
    c.chat([{"role": "user", "content": "oi"}], [])
    assert "tools" not in sent and "tool_choice" not in sent and "temperature" not in sent

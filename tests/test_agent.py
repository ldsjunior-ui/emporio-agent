from types import SimpleNamespace as NS

import pytest

from emporio_agent.agent import Agent


def msg(stop, *blocks):
    return NS(stop_reason=stop, content=list(blocks))


def text(t):
    return NS(type="text", text=t)


def tool(i, name, **inp):
    return NS(type="tool_use", id=i, name=name, input=inp)


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw["messages"][:])
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_loop_executa_ferramenta_e_devolve_texto():
    c = FakeClient(msg("tool_use", tool("t1", "status_loja_agora")), msg("end_turn", text("Estamos abertos!")))
    turn = Agent(client=c, persist=False).reply("tá aberto?")
    assert turn.reply == "Estamos abertos!"
    assert [x.name for x in turn.tool_calls] == ["status_loja_agora"]
    # 2ª chamada ao modelo já contém tool_result pareado ao tool_use
    last = c.calls[1][-1]["content"][0]
    assert last["type"] == "tool_result" and last["tool_use_id"] == "t1"


def test_erro_da_api_nao_corrompe_historico():
    c = FakeClient(msg("tool_use", tool("t1", "status_loja_agora")), RuntimeError("boom"))
    a = Agent(client=c, persist=False)
    with pytest.raises(RuntimeError):
        a.reply("oi")
    assert a.messages == []  # rollback completo do turno


def test_persistencia_retoma_sessao(tmp_path):
    c = FakeClient(msg("end_turn", text("Oi!")))
    a = Agent(client=c, session_id="abc")
    a.reply("olá")
    b = Agent(client=FakeClient(), session_id="abc")
    assert len(b.messages) == 2 and b.messages[0]["content"] == "olá"


def test_limite_de_rodadas():
    loop = [msg("tool_use", tool(f"t{i}", "status_loja_agora")) for i in range(20)]
    with pytest.raises(RuntimeError):
        Agent(client=FakeClient(*loop), persist=False).reply("oi")

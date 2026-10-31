import json

from emporio_agent import tools as t

ANA = "anacarol.ferreira@coldmail.com"  # cliente 2, pedido 8 (enviado)


def names(r):
    return [p["nome"] for p in r["produtos"]]


def test_violoes_ate_1000_respeita_preco_e_disponibilidade():
    r = t.buscar_produtos("violões", categoria_id=5, preco_max=1000)
    assert r["total_encontrado"] > 0
    assert all(float(p["preco_a_pagar"][3:].replace(".", "").replace(",", ".")) <= 1000 for p in r["produtos"])
    assert all("em estoque" in p["disponibilidade"] for p in r["produtos"])
    assert not any("Shelby SN-7C" in n for n in names(r))  # descontinuado fica de fora
    assert r["indisponiveis_ocultados"] >= 1  # Giannini GF-3D (estoque 0) etc.


def test_busca_por_modelo_ignora_acento_e_caixa():
    r = t.buscar_produtos("takamine gd20")
    assert names(r) == ["Takamine GD20 Dreadnought Natural"]
    assert r["produtos"][0]["preco_tabela"] == "R$ 2.199,00"
    assert "promocao" not in r["produtos"][0]  # a promoção 4/dessa linha está inativa


def test_so_promocao_ativa_conta():
    # produto 121: promoção 14 ativa (20%); produto 93: promoções 6 e 23 inativas
    ativo = t.obter_produto(121)
    assert ativo["promocao"]["desconto_percentual"] == 20
    assert "R$ 439,20" == ativo["preco_a_pagar"]
    assert "promocao" not in t.obter_produto(93)


def test_pix_nao_acumula_com_promocao():
    pago = t.calcular_pagamento([121])
    assert pago["total_no_pix"] == pago["total_a_prazo"]
    sem_promo = t.calcular_pagamento([95])  # 2199,00 sem promoção
    assert sem_promo["total_no_pix"] == "R$ 2.089,05"
    assert sem_promo["combinar_formas_de_pagamento"].startswith("permitido")


def test_parcelamento_regras_31():
    assert [o["parcelas"] for o in t.installment_options(40)] == [1]
    assert max(o["parcelas"] for o in t.installment_options(200)) == 3
    assert max(o["parcelas"] for o in t.installment_options(400)) == 5   # 400/5=80 ok; 400/6=66 < 80
    assert max(o["parcelas"] for o in t.installment_options(600)) == 6   # 600/6=100; 600/7=85 < 100 (7x+ exige R$ 100)
    assert max(o["parcelas"] for o in t.installment_options(1200)) == 12


def test_produto_descontinuado_traz_alternativas():
    r = t.obter_produto(113)
    assert "descontinuado" in r["disponibilidade"]
    assert 1 <= len(r["alternativas_disponiveis"]) <= 3


def test_pedido_exige_verificacao():
    assert t.consultar_pedido(8, "outra@pessoa.com")["erro"] == "nao_verificado"
    assert t.consultar_pedido(9999, ANA)["erro"] == "nao_verificado"  # não revela inexistência
    ok = t.consultar_pedido(8, ANA)
    assert ok["status"].startswith("enviado") and ok["codigo_rastreio"] == "BRJL5544332BR"
    assert "alerta" in ok  # previsão 28/02 já passou em 23/03


def test_pedido_verificado_por_telefone():
    assert "erro" not in t.consultar_pedido(8, "(67) 99654-7821")
    assert "erro" not in t.consultar_pedido(8, "67996547821")
    assert t.consultar_pedido(8, "12345")["erro"] == "nao_verificado"


def test_pedido_cancelado_mostra_motivo():
    from emporio_agent.data_store import get_store

    c = get_store().customers[15]
    r = t.consultar_pedido(17, c.email)
    assert r["status"] == "cancelado" and "cancelado pelo cliente" in r["observacoes"]


def test_devolucao_arrependimento_fora_do_prazo():
    # pedido 7 (cliente 14) entregue ~17/02; hoje 23/03
    from emporio_agent.data_store import get_store

    c = get_store().customers[14]
    r = t.verificar_devolucao(7, c.email, "arrependimento")
    assert r["elegivel"] is False
    d = t.verificar_devolucao(7, c.email, "defeito")
    assert d["elegivel"] is False and d["garantia_legal_ate"] != "expirada"


def test_devolucao_pedido_nao_entregue():
    r = t.verificar_devolucao(8, ANA, "arrependimento")
    assert r["elegivel"] is None


def test_loja_aberta_segunda_manha_e_fechada_domingo(monkeypatch):
    assert t.status_loja_agora()["loja_aberta"] is True
    monkeypatch.setenv("EMPORIO_NOW", "2026-03-22 11:00")  # domingo
    s = t.status_loja_agora()
    assert s["loja_aberta"] is False and "segunda" in s["proximo_horario"]
    monkeypatch.setenv("EMPORIO_NOW", "2026-03-28 13:30")  # sábado após 13h
    r = t.status_loja_agora()
    assert r["loja_aberta"] is False and "já terminou às 13h" in r["situacao"]
    monkeypatch.setenv("EMPORIO_NOW", "2026-03-23 07:00")  # segunda antes de abrir
    assert "ainda não abriu hoje" in t.status_loja_agora()["situacao"]


def test_politicas_todos_topicos():
    for topic in t.TOPICS:
        assert t.consultar_politicas(topic)["texto_oficial"]
    assert "erro" in t.consultar_politicas("inexistente")


def test_handoff_gera_protocolo_sequencial():
    a = t.encaminhar_para_humano("reclamacao", "atraso")
    b = t.encaminhar_para_humano("garantia", "defeito")
    assert a["protocolo"].endswith("0001") and b["protocolo"].endswith("0002")


def test_run_tool_argumento_invalido_nao_explode():
    out = json.loads(t.run_tool("buscar_produtos", {"campo_falso": 1}))
    assert "erro" in out


def test_prazos_devolucao_deixam_claro_o_que_encerrou_e_o_que_vale():
    from emporio_agent.data_store import get_store

    r = t.verificar_devolucao(7, get_store().customers[14].email, "arrependimento")
    prazos = r["resumo_de_prazos"]
    assert prazos["troca_direta_por_defeito (30 dias após a COMPRA)"].startswith("ENCERRADO")
    assert prazos["garantia_legal_contra_defeito (90 dias após o recebimento)"].startswith("VIGENTE")


def test_listagem_informa_quantos_nao_foram_exibidos():
    r = t.buscar_produtos("violões", categoria_id=5, preco_max=1000, limite=8)
    assert r["nao_exibidos_dentro_do_filtro"] == r["total_encontrado"] - 8


def test_run_tool_tipo_errado_nao_explode():
    out = json.loads(t.run_tool("obter_produto", {"product_id": "nenhum"}))
    assert "erro" in out
    out = json.loads(t.run_tool("consultar_pedido", {"order_id": "abc", "contato_do_cliente": "x"}))
    assert "erro" in out


def test_orientacao_defeito_explicita_encerrado_e_vigente():
    from emporio_agent.data_store import get_store

    r = t.verificar_devolucao(7, get_store().customers[14].email, "arrependimento")
    o = r["orientacao_defeito"]
    assert "encerrado" in o and "vigente" in o

"""Ferramentas (function calling) expostas ao LLM.

Princípio: tudo que é regra de negócio determinística (preço com promoção, parcelas, prazo de
devolução, loja aberta?) é calculado AQUI, em código testável, e o LLM só redige a resposta.
Isso evita erro de aritmética/data do modelo e mantém a política auditável.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Callable

from . import config
from .data_store import (
    STATUS_PEDIDO, STATUS_PRODUTO, Product, Store, get_store, payment_label, tokens,
)
from .policies import TOPIC_HELP, TOPICS, get_policy

PIX_DISCOUNT = 0.05
FREE_SHIPPING_FROM = 500.0


def brl(value: float) -> str:
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------- preços
def price_info(store: Store, p: Product) -> dict[str, Any]:
    promo = store.active_promotion(p.product_id)
    final = round(p.price_brl * (1 - promo.discount_percent / 100), 2) if promo else p.price_brl
    info: dict[str, Any] = {"preco_tabela": brl(p.price_brl)}
    if promo:
        info["promocao"] = {
            "nome": promo.description,
            "desconto_percentual": promo.discount_percent,
            "preco_promocional": brl(final),
        }
        info["preco_pix"] = f"{brl(final)} (PIX não acumula com promoção, política §6.2)"
    else:
        info["preco_pix"] = brl(round(final * (1 - PIX_DISCOUNT), 2)) + " (5% off no PIX)"
    info["preco_a_pagar"] = brl(final)
    info["_final"] = final  # uso interno (filtros/cálculos); removido antes de ir ao modelo
    return info


def _public(info: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in info.items() if not k.startswith("_")}


def availability(p: Product) -> str:
    if p.status == "discontinued":
        return "descontinuado (fora do catálogo)"
    if p.status == "coming_soon":
        return "em breve (ainda não disponível para venda)"
    if p.stock_quantity <= 0:
        return "sem estoque no momento"
    return f"em estoque ({p.stock_quantity} un.)"


def _product_card(store: Store, p: Product, detailed: bool = False) -> dict[str, Any]:
    card: dict[str, Any] = {
        "product_id": p.product_id,
        "nome": p.name,
        "categoria": p.category,
        "disponibilidade": availability(p),
        **_public(price_info(store, p)),
    }
    if detailed:
        card["descricao"] = p.description
        card["especificacoes"] = p.specs
        card["promocao_ativa"] = "promocao" in card
        ended = [
            {"nome": q.description, "desconto_percentual": q.discount_percent}
            for q in store.promotions if q.product_id == p.product_id and not q.is_active
        ]
        if ended:
            card["promocoes_encerradas"] = ended  # só para explicar "já acabou"; NÃO valem mais
    else:
        card["resumo"] = p.description.split(". ")[0].rstrip(".") + "."
    return card


# --------------------------------------------------------------------------- produtos
def buscar_produtos(
    consulta: str = "",
    categoria_id: int | None = None,
    preco_min: float | None = None,
    preco_max: float | None = None,
    apenas_disponiveis: bool = True,
    ordenar: str = "relevancia",
    limite: int = 8,
) -> dict[str, Any]:
    store = get_store()
    limite = max(1, min(int(limite), 15))
    q = tokens(consulta)
    pool = [p for p in store.products.values() if categoria_id in (None, p.category_id)]

    scored: list[tuple[float, Product]] = []
    approximate = False
    if q:
        for p in pool:
            hit = sum(1 for t in q if t in p.search_tokens)
            if hit == len(q):
                scored.append((1.0, p))
        if not scored and len(q) > 1:  # relaxa: qualquer termo, ranqueado pela fração acertada
            approximate = True
            for p in pool:
                hit = sum(1 for t in q if t in p.search_tokens)
                if hit:
                    scored.append((hit / len(q), p))
    else:
        scored = [(1.0, p) for p in pool]

    rows = []
    hidden = 0
    for score, p in scored:
        info = price_info(store, p)
        final = info["_final"]
        if preco_min is not None and final < preco_min:
            continue
        if preco_max is not None and final > preco_max:
            continue
        if apenas_disponiveis and not p.available:
            hidden += 1
            continue
        rows.append((score, final, p))

    key = {
        "preco_asc": lambda r: (r[1], -r[0]),
        "preco_desc": lambda r: (-r[1], -r[0]),
    }.get(ordenar, lambda r: (-r[0], r[1]))
    rows.sort(key=key)

    return {
        "total_encontrado": len(rows),
        "exibindo": min(limite, len(rows)),
        "busca_aproximada": approximate,
        "indisponiveis_ocultados": hidden,
        "criterio_preco": "preço final a pagar (já com promoção ativa, se houver)",
        "produtos": [_product_card(store, p) for _, _, p in rows[:limite]],
    }


def obter_produto(product_id: int) -> dict[str, Any]:
    store = get_store()
    p = store.products.get(int(product_id))
    if not p:
        return {"erro": f"Produto {product_id} não encontrado."}
    card = _product_card(store, p, detailed=True)
    if not p.available:
        final = price_info(store, p)["_final"]
        alts = [
            q for q in store.products.values()
            if q.category_id == p.category_id and q.available and q.product_id != p.product_id
        ]
        alts.sort(key=lambda q: abs(price_info(store, q)["_final"] - final))
        card["alternativas_disponiveis"] = [_product_card(store, q) for q in alts[:3]]
    return card


# --------------------------------------------------------------------------- pagamento
def installment_options(total: float) -> list[dict[str, Any]]:
    """Regras do §3.1: até 3x sem mínimo (mas não parcela compra < R$ 50); 4–6x parcela >= R$ 80;
    7–12x parcela >= R$ 100. Prevalece o §3.1 (mais específico) sobre a linha da tabela §3."""
    options = [{"parcelas": 1, "valor_parcela": brl(total), "total": brl(total)}]
    if total < 50:
        return options
    for n in range(2, 13):
        parcela = round(total / n, 2)
        minimum = 0 if n <= 3 else 80 if n <= 6 else 100
        if parcela >= minimum:
            options.append({"parcelas": n, "valor_parcela": brl(parcela), "total": brl(total)})
    return options


def calcular_pagamento(product_ids: list[int]) -> dict[str, Any]:
    store = get_store()
    items, total, total_pix, any_promo = [], 0.0, 0.0, False
    for pid in product_ids:
        p = store.products.get(int(pid))
        if not p:
            return {"erro": f"Produto {pid} não encontrado."}
        info = price_info(store, p)
        final = info["_final"]
        promo = "promocao" in info
        any_promo |= promo
        total += final
        total_pix += final if promo else round(final * (1 - PIX_DISCOUNT), 2)
        items.append({"nome": p.name, "preco_a_pagar": brl(final), "em_promocao": promo,
                      "disponibilidade": availability(p)})
    total, total_pix = round(total, 2), round(total_pix, 2)
    opts = installment_options(total)
    return {
        "itens": items,
        "total_a_prazo": brl(total),
        "total_no_pix": brl(total_pix),
        "economia_pix": brl(round(total - total_pix, 2)),
        "pix_observacao": "5% de desconto só em itens sem promoção ativa (política §6.2)",
        "debito_ou_boleto": f"{brl(total)} à vista (boleto compensa em até 3 dias úteis)",
        "credito_max_parcelas": opts[-1]["parcelas"],
        "credito_opcoes": opts,
        "combinar_formas_de_pagamento": "permitido" if total > 2000 else "não permitido (só acima de R$ 2.000,00)",
        "frete_regiao_campo_grande": "grátis" if total > FREE_SHIPPING_FROM else "R$ 35,00 (taxa fixa)",
        "frete_outras_cidades": "calculado pelo CEP (Correios/Jadlog); não consigo cotar por aqui",
    }


# --------------------------------------------------------------------------- pedidos
def _load_order(store: Store, order_id: int, contato: str):
    order = store.orders.get(int(order_id))
    if not order or not store.verify_customer(order.order_id, contato):
        # mesma mensagem nos dois casos: não revela se o pedido existe (LGPD)
        return None, {
            "erro": "nao_verificado",
            "mensagem": "Não encontrei um pedido com esse número associado a esse e-mail/telefone.",
        }
    return order, None


def consultar_pedido(order_id: int, contato_do_cliente: str) -> dict[str, Any]:
    store = get_store()
    order, err = _load_order(store, order_id, contato_do_cliente)
    if err:
        return err
    today = config.now().date()
    customer = store.customers[order.customer_id]
    out: dict[str, Any] = {
        "pedido": order.order_id,
        "cliente": customer.name.split()[0],
        "data_do_pedido": order.order_date.isoformat(),
        "status": STATUS_PEDIDO[order.status],
        "itens": [
            {"produto": store.products[pid].name, "quantidade": qty}
            for pid, qty in store.order_items.get(order.order_id, [])
        ],
        "total": brl(order.total_brl),
        "pagamento": payment_label(order.payment_method),
        "codigo_rastreio": order.tracking_code or None,
        "previsao_de_entrega": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
        "observacoes": order.notes or None,
    }
    if order.status == "shipped" and order.estimated_delivery and order.estimated_delivery < today:
        out["alerta"] = (
            f"A previsão de entrega ({order.estimated_delivery.isoformat()}) já passou e o pedido "
            "ainda consta como enviado. Ofereça abrir um chamado (encaminhar_para_humano)."
        )
    if order.status in ("pending", "confirmed"):
        out["alerta"] = "Ainda não despachado: não há código de rastreio nem previsão de entrega."
    return out


def verificar_devolucao(order_id: int, contato_do_cliente: str, motivo: str) -> dict[str, Any]:
    """Aplica §4 a um pedido real. `motivo`: arrependimento | defeito | preferencia."""
    store = get_store()
    order, err = _load_order(store, order_id, contato_do_cliente)
    if err:
        return err
    today = config.now().date()
    base: dict[str, Any] = {"pedido": order.order_id, "motivo": motivo,
                            "status_pedido": STATUS_PEDIDO[order.status]}

    if order.status == "cancelled":
        return {**base, "elegivel": False, "explicacao": "O pedido já está cancelado; não há o que devolver."}
    if order.status != "delivered":
        return {**base, "elegivel": None,
                "explicacao": "O pedido ainda não foi entregue. O prazo de devolução só começa a "
                              "contar após o recebimento. Para cancelar antes da entrega, "
                              "encaminhe a um atendente (encaminhar_para_humano)."}

    # Não há data real de entrega nos dados: usa a previsão de entrega como proxy (suposição).
    received = order.estimated_delivery or order.order_date
    since_receipt = (today - received).days
    since_purchase = (today - order.order_date).days
    arrep_limit = received + timedelta(days=7)
    defect_limit = order.order_date + timedelta(days=30)
    legal_limit = received + timedelta(days=90)
    base["resumo_de_prazos"] = {
        "arrependimento_7_dias_apos_recebimento": {"limite": arrep_limit.isoformat(), "no_prazo": today <= arrep_limit},
        "troca_por_preferencia_7_dias": {"limite": arrep_limit.isoformat(), "no_prazo": today <= arrep_limit},
        "troca_por_defeito_30_dias_apos_compra": {"limite": defect_limit.isoformat(), "no_prazo": today <= defect_limit},
        "garantia_legal_90_dias_apos_recebimento": {"limite": legal_limit.isoformat(), "no_prazo": today <= legal_limit},
    }
    base.update(
        data_referencia_recebimento=f"{received.isoformat()} (previsão de entrega, usada como data de recebimento)",
        dias_desde_recebimento=since_receipt,
        dias_desde_compra=since_purchase,
        itens=[store.products[pid].name for pid, _ in store.order_items.get(order.order_id, [])],
        condicoes="Produto na embalagem original, sem sinais de uso, com acessórios e manuais.",
        nao_elegiveis="Itens personalizados/sob encomenda (setup, regulagem), promoção de liquidação "
                      "'venda final' e boquilhas de sopro não são trocáveis (§4.4).",
        aviso="A decisão final é do atendente: confirme a data real de recebimento e o estado do produto.",
    )

    if motivo == "arrependimento":
        limite = received + timedelta(days=7)
        ok = today <= limite
        return {**base, "elegivel": ok, "prazo_limite": limite.isoformat(),
                "regra": "Arrependimento (compras online): 7 dias corridos após o recebimento, sem justificativa (§4.1).",
                "proximos_passos": "Reembolso na mesma forma de pagamento em até 10 dias úteis; frete de devolução por conta da loja."
                if ok else "Prazo de arrependimento encerrado. Se houver defeito, vale a regra de defeito/garantia."}
    if motivo == "preferencia":
        limite = received + timedelta(days=7)
        ok = today <= limite
        return {**base, "elegivel": ok, "prazo_limite": limite.isoformat(),
                "regra": "Troca por preferência (cor/modelo/tamanho): até 7 dias, sujeita à disponibilidade do produto desejado; diferença de valor cobrada/reembolsada (§4.3).",
                "proximos_passos": "Informe o produto desejado para checar estoque." if ok else "Prazo encerrado."}
    if motivo == "defeito":
        limite = order.order_date + timedelta(days=30)
        if today <= limite:
            return {**base, "elegivel": True, "prazo_limite": limite.isoformat(),
                    "regra": "Defeito de fabricação: troca em até 30 dias corridos após a compra (§4.2). Mau uso/queda/umidade não são cobertos.",
                    "proximos_passos": "Encaminhar a um atendente com descrição do defeito."}
        legal_limit = received + timedelta(days=90)
        return {**base, "elegivel": False, "prazo_limite": limite.isoformat(),
                "regra": "Troca direta por defeito vale até 30 dias após a compra (§4.2).",
                "garantia_legal_ate": legal_limit.isoformat() if today <= legal_limit else "expirada",
                "proximos_passos": "Após 30 dias, acionar a garantia com o fabricante; a loja pode intermediar mediante solicitação. "
                                   + ("A garantia legal de 90 dias após o recebimento ainda está vigente (§8.1)."
                                      if today <= legal_limit else "A garantia legal de 90 dias já expirou; vale apenas a garantia do fabricante (certificado do produto).")}
    return {"erro": "motivo deve ser arrependimento, defeito ou preferencia"}


# --------------------------------------------------------------------------- loja
def status_loja_agora() -> dict[str, Any]:
    now = config.now()
    hours = {0: (9, 18), 1: (9, 18), 2: (9, 18), 3: (9, 18), 4: (9, 18), 5: (9, 13)}

    def window(d: date):
        h = hours.get(d.weekday())
        return (datetime.combine(d, datetime.min.time(), tzinfo=now.tzinfo).replace(hour=h[0]),
                datetime.combine(d, datetime.min.time(), tzinfo=now.tzinfo).replace(hour=h[1])) if h else None

    w = window(now.date())
    is_open = bool(w and w[0] <= now < w[1])
    if is_open:
        nxt = f"Fecha hoje às {w[1]:%H:%M}."
    else:
        d = now.date() if (w and now < w[0]) else now.date() + timedelta(days=1)
        while not window(d):
            d += timedelta(days=1)
        opening = window(d)[0]
        dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
        nxt = f"Reabre {'hoje' if d == now.date() else dias[d.weekday()] + ' (' + d.strftime('%d/%m') + ')'} às {opening:%H:%M}."
    return {
        "agora": now.strftime("%d/%m/%Y %H:%M"),
        "dia_da_semana": ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"][now.weekday()],
        "loja_aberta": is_open,
        "proximo_horario": nxt,
        "ressalva": "Não tenho calendário de feriados (loja fecha em feriados) nem aviso de horário estendido em datas especiais.",
    }


def consultar_politicas(topico: str) -> dict[str, Any]:
    if topico not in TOPICS:
        return {"erro": f"Tópico inválido. Opções: {', '.join(TOPICS)}"}
    return {"topico": topico, "texto_oficial": get_policy(topico)}


def encaminhar_para_humano(
    motivo: str, resumo: str, nome_cliente: str = "", contato_cliente: str = "", order_id: int | None = None
) -> dict[str, Any]:
    """Registra um chamado para a equipe (arquivo JSONL em outbox/). Em produção seria um ticket."""
    config.OUTBOX_DIR.mkdir(exist_ok=True)
    path = config.OUTBOX_DIR / "chamados.jsonl"
    n = sum(1 for _ in path.open(encoding="utf-8")) + 1 if path.exists() else 1
    now = config.now()
    protocolo = f"EM-{now:%Y%m%d}-{n:04d}"
    record = {"protocolo": protocolo, "criado_em": now.isoformat(), "motivo": motivo, "resumo": resumo,
              "nome_cliente": nome_cliente, "contato_cliente": contato_cliente, "order_id": order_id}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"protocolo": protocolo, "prazo_retorno": "até 24 horas úteis (§7.3)", "registrado": True}


# --------------------------------------------------------------------------- registro
_CATS = "; ".join(f"{c['category_id']}={c['name']}" for c in get_store().categories.values())

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "buscar_produtos",
        "description": (
            "Busca no catálogo ao vivo (preço, promoção ativa, estoque). USE SEMPRE antes de citar "
            "preço, disponibilidade ou listar opções. Os preços retornados já consideram promoção ativa. "
            "Por padrão só traz itens disponíveis para compra."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Termos livres: marca, modelo, tipo, característica (ex.: 'Takamine GD20', 'nylon', 'soprano'). Vazio = só filtros."},
                "categoria_id": {"type": "integer", "description": f"Filtro opcional. {_CATS}"},
                "preco_min": {"type": "number"},
                "preco_max": {"type": "number", "description": "Teto de preço FINAL a pagar, em reais."},
                "apenas_disponiveis": {"type": "boolean", "description": "Padrão true. Use false para perguntar sobre um item específico que pode estar sem estoque/descontinuado."},
                "ordenar": {"type": "string", "enum": ["relevancia", "preco_asc", "preco_desc"]},
                "limite": {"type": "integer", "description": "Máx. 15 (padrão 8)."},
            },
        },
    },
    {
        "name": "obter_produto",
        "description": "Detalhes completos de um produto por ID (especificações, descrição) e, se estiver indisponível, até 3 alternativas semelhantes.",
        "input_schema": {"type": "object", "properties": {"product_id": {"type": "integer"}}, "required": ["product_id"]},
    },
    {
        "name": "calcular_pagamento",
        "description": "Calcula total, preço no PIX (5%, não vale sobre promoção), parcelas no crédito conforme regras da loja e frete para Campo Grande. Use para qualquer pergunta de parcelamento/PIX/frete de produtos específicos.",
        "input_schema": {"type": "object", "properties": {"product_ids": {"type": "array", "items": {"type": "integer"}}}, "required": ["product_ids"]},
    },
    {
        "name": "consultar_pedido",
        "description": "Status, itens, rastreio e previsão de um pedido. Exige o número do pedido E o e-mail ou telefone cadastrado (verificação de identidade, LGPD). Nunca chame sem os dois dados informados pelo cliente.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "integer"}, "contato_do_cliente": {"type": "string", "description": "E-mail ou telefone cadastrado, exatamente como o cliente informou."}}, "required": ["order_id", "contato_do_cliente"]},
    },
    {
        "name": "verificar_devolucao",
        "description": "Aplica a política de trocas/devoluções a um pedido real (prazos calculados em código). Exige número do pedido + e-mail/telefone e o motivo.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "integer"}, "contato_do_cliente": {"type": "string"}, "motivo": {"type": "string", "enum": ["arrependimento", "defeito", "preferencia"]}}, "required": ["order_id", "contato_do_cliente", "motivo"]},
    },
    {
        "name": "status_loja_agora",
        "description": "Diz se a loja está aberta agora e quando abre/fecha (relógio de Campo Grande). Use para 'está aberto?' e para fora do expediente.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "consultar_politicas",
        "description": "Texto oficial do manual de políticas por tópico. Use para regras gerais (trocas, garantia, frete, pagamento, horários, endereço, promoções, LGPD). Tópicos: "
        + "; ".join(f"{k} ({v})" for k, v in TOPIC_HELP.items()),
        "input_schema": {"type": "object", "properties": {"topico": {"type": "string", "enum": list(TOPICS)}}, "required": ["topico"]},
    },
    {
        "name": "encaminhar_para_humano",
        "description": "Abre um chamado para a equipe (reclamação, devolução/troca a processar, garantia, pedido atrasado, dúvida que o manual não cobre). Retorna protocolo. Só use depois de ter o resumo do caso e, se possível, nome e contato.",
        "input_schema": {"type": "object", "properties": {"motivo": {"type": "string", "enum": ["reclamacao", "devolucao_troca", "garantia", "pedido_atrasado", "cancelamento", "frete_outras_cidades", "outro"]}, "resumo": {"type": "string"}, "nome_cliente": {"type": "string"}, "contato_cliente": {"type": "string"}, "order_id": {"type": "integer"}}, "required": ["motivo", "resumo"]},
    },
]

REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "buscar_produtos": buscar_produtos,
    "obter_produto": obter_produto,
    "calcular_pagamento": calcular_pagamento,
    "consultar_pedido": consultar_pedido,
    "verificar_devolucao": verificar_devolucao,
    "status_loja_agora": status_loja_agora,
    "consultar_politicas": consultar_politicas,
    "encaminhar_para_humano": encaminhar_para_humano,
}


def run_tool(name: str, args: dict[str, Any]) -> str:
    fn = REGISTRY.get(name)
    if not fn:
        return json.dumps({"erro": f"ferramenta desconhecida: {name}"}, ensure_ascii=False)
    try:
        return json.dumps(fn(**args), ensure_ascii=False)
    except TypeError as exc:  # argumentos inválidos vindos do modelo
        return json.dumps({"erro": f"argumentos inválidos: {exc}"}, ensure_ascii=False)

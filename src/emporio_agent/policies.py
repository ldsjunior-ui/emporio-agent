"""Políticas da loja: o manual vira seções indexadas por tópico.

O manual inteiro tem ~2,5k tokens. Em vez de embeddings/vetor, cada seção é servida inteira pelo
tool `consultar_politicas(topico)`: determinístico, sem risco de recuperar o trecho errado
(ex.: pegar "7 dias" de troca por preferência quando a pergunta é sobre defeito) e sem infra extra.
"""
from __future__ import annotations

import re
from functools import lru_cache

from .config import DATA_DIR

# tópico -> números das seções do manual
TOPICS: dict[str, list[str]] = {
    "sobre_loja_e_contato": ["1", "7"],
    "horario_funcionamento": ["2"],
    "formas_pagamento_parcelamento": ["3"],
    "trocas_devolucoes": ["4"],
    "frete_entrega_rastreamento": ["5"],
    "promocoes": ["6"],
    "garantia": ["8"],
    "privacidade_lgpd": ["9"],
    "diretrizes_atendimento": ["7", "10"],
}

TOPIC_HELP = {
    "sobre_loja_e_contato": "endereço, telefone/WhatsApp, e-mail, o que a loja vende (e o que não vende)",
    "horario_funcionamento": "dias e horários de funcionamento",
    "formas_pagamento_parcelamento": "PIX, débito, crédito, boleto, parcelamento e desconto no PIX",
    "trocas_devolucoes": "arrependimento (7 dias), defeito (30 dias), troca por preferência, itens não elegíveis",
    "frete_entrega_rastreamento": "frete grátis/taxa, prazos, Correios/Jadlog, código de rastreio",
    "promocoes": "campanhas, cumulatividade, rain check, como apresentar preço promocional",
    "garantia": "garantia legal (90 dias), do fabricante, o que não cobre",
    "privacidade_lgpd": "uso e exclusão de dados pessoais",
    "diretrizes_atendimento": "situações especiais (sem estoque, descontinuado, reclamação, 24h úteis)",
}


@lru_cache(maxsize=1)
def _sections() -> dict[str, str]:
    text = (DATA_DIR / "politicas_da_loja.md").read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    out: dict[str, str] = {}
    for chunk in re.split(r"(?m)^## ", text)[1:]:
        number = chunk.split(".", 1)[0].strip()
        out[number] = "## " + chunk.strip()
    return out


def get_policy(topic: str) -> str:
    if topic not in TOPICS:
        raise KeyError(topic)
    sections = _sections()
    return "\n\n".join(sections[n] for n in TOPICS[topic])

"""Métricas de tom (determinísticas) sobre as respostas do agente.

O tom que o manual pede (§7.1): informal mas profissional, "como um amigo que entende de música", sem linguagem
robotizada ou formal demais. O prompt acrescenta: no máximo 1 emoji por mensagem, sem tabelas Markdown nem títulos.
Estas métricas medem só o que dá para medir sem juiz: forma e vocabulário. NÃO medem calor humano nem adequação ao
contexto; para isso, ler amostras (ver docs/robustness.md).
"""
from __future__ import annotations

import re

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF]")
FORMAL = re.compile(r"\b(prezad[oa]|estimad[oa] (cliente|senhor)|ilustr[ei]|vossa|senhor(a)?\b|atenciosamente|cordialmente|à disposição)", re.I)
ROBOT = re.compile(r"(como (um )?(modelo|assistente) (de linguagem|de ia)|sou uma ia|n[aã]o tenho acesso ao sistema|"
                   r"conforme (o )?(manual|pol[ií]tica|se[cç][aã]o)|segundo o manual|se[cç][aã]o \d)", re.I)
EM_DASH = re.compile("[—–]")  # a regra de estilo global do dono do projeto é "nunca travessão"


def tone_flags(text: str) -> dict[str, bool]:
    lines = text.splitlines()
    return {
        "mais de 1 emoji": len(EMOJI.findall(text)) > 1,
        "tabela ou título markdown": any(re.match(r"\s*\|.*\|\s*$", l) or re.match(r"\s*#{1,6}\s", l) for l in lines),
        "linguagem formal demais": bool(FORMAL.search(text)),
        "linguagem robotizada / cita o manual": bool(ROBOT.search(text)),
        "resposta longa (> 900 caracteres)": len(text) > 900,
        "travessão": bool(EM_DASH.search(text)),
        "duas perguntas de fechamento": len(re.findall(r"(precisa de mais alguma|posso ajudar em mais|mais alguma coisa)", text, re.I)) > 1,
    }


def summarize(replies: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in replies:
        for k, v in tone_flags(r).items():
            if v:
                out[k] = out.get(k, 0) + 1
    return out


if __name__ == "__main__":
    import json
    import sys

    total = 0
    agg: dict[str, int] = {}
    for path in sys.argv[1:]:
        data = json.load(open(path))
        for rows in data.values():
            for row in rows:
                for t in row.get("turns", []):
                    total += 1
                    for k, v in tone_flags(t["reply"]).items():
                        if v:
                            agg[k] = agg.get(k, 0) + 1
    print(f"{total} respostas analisadas")
    for k, v in sorted(agg.items(), key=lambda kv: -kv[1]):
        print(f"  {v:3}  ({100 * v // total}%)  {k}")

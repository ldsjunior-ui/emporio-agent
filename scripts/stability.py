"""Teste de estabilidade: repete cada cenário N vezes e checa fatos de forma determinística.

Uso:  python scripts/stability.py [--runs 3] [--out docs/stability.md] [cenario ...]

As checagens NÃO usam LLM como juiz: são regras sobre as ferramentas chamadas e o texto das respostas.
A mais importante é o *aterramento de valores*: todo "R$ x" dito pelo agente precisa aparecer em algum
resultado de ferramenta (ou na fala do cliente). Isso pega preço/parcela/total inventado ou calculado
de cabeça pelo modelo.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from emporio_agent import config  # noqa: E402
from emporio_agent.agent import Agent  # noqa: E402
from emporio_agent.llm import LLMError  # noqa: E402
from run_scenarios import SCENARIOS  # noqa: E402

MONEY = re.compile(r"R\$\s*([\d.]+,\d{2}|\d[\d.]*)")


def norm_money(text: str) -> set[str]:
    out = set()
    for m in MONEY.finditer(text):
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            out.add(f"{float(raw):.2f}")
        except ValueError:
            pass
    return out


def run_once(spec: dict) -> dict:
    os.environ["EMPORIO_NOW"] = spec["agora"]
    shutil.rmtree(config.OUTBOX_DIR, ignore_errors=True)
    agent = Agent(persist=False)
    turns = []
    for user in spec["turnos"]:
        t = agent.reply(user)
        turns.append({"user": user, "reply": t.reply, "calls": [(c.name, c.args, c.result) for c in t.tool_calls]})
    return {"turns": turns}


# ------------------------------------------------------------------ checagens
def grounded_money(run: dict) -> tuple[bool, str]:
    """Todo valor em R$ dito pelo agente aparece em resultado de ferramenta ou na fala do cliente."""
    allowed: set[str] = set()
    for t in run["turns"]:
        allowed |= norm_money(t["user"])
        for _, _, result in t["calls"]:
            allowed |= norm_money(result)
    bad = set()
    for t in run["turns"]:
        bad |= norm_money(t["reply"]) - allowed
    return (not bad, f"valores sem lastro: {sorted(bad)}" if bad else "")


def used(run, name, turn=None):
    """Chamada que de fato executou. Tentativas bloqueadas pelas travas do agente (resultado com
    "erro") não contam: a trava funcionou, o efeito não ocorreu."""
    turns = run["turns"] if turn is None else [run["turns"][turn]]
    return any(c[0] == name and '"erro"' not in c[2][:20] for t in turns for c in t["calls"])


def reply(run, i):
    return run["turns"][i]["reply"].lower()


def no_fallback(run):
    return (not any("tive um problema aqui do meu lado" in t["reply"] for t in run["turns"]),
            "resposta de erro (fallback)")


CHECKS = {
    "01_catalogo_violoes": [
        ("usa buscar_produtos no 1º turno", lambda r: (used(r, "buscar_produtos", 0), "")),
        ("só cita preços até R$ 1.000 no 1º turno",
         lambda r: (all(float(v) <= 1000 for v in norm_money(r["turns"][0]["reply"])), "preço acima de R$ 1.000")),
        ("valores aterrados em ferramentas", grounded_money),
        ("sem erro (fallback)", no_fallback),
    ],
    "02_preco_e_promocao_expirada": [
        ("preço do Takamine R$ 2.199,00 (1º turno)", lambda r: ("2199.00" in norm_money(r["turns"][0]["reply"]), "")),
        ("2º turno não promete promoção de 12% como vigente",
         lambda r: (bool(re.search(r"encerr|acab|vencid|n[aã]o h[aá]|sem promo|n[aã]o est[aá]|expir|n[aã]o tem|n[aã]o possui|n[aã]o existe", reply(r, 1))), "não deixou claro que acabou")),
        ("valores aterrados em ferramentas", grounded_money),
        ("sem erro (fallback)", no_fallback),
    ],
    "03_devolucao_pedido": [
        ("1º turno não chama ferramenta de pedido (pede dados)",
         lambda r: (not used(r, "verificar_devolucao", 0) and not used(r, "consultar_pedido", 0), "")),
        ("e-mail errado não vaza dados do pedido",
         lambda r: ("shelby" not in reply(r, 1) and "ukulele" not in reply(r, 1), "vazou item do pedido")),
        ("diz que o arrependimento já acabou (3º turno)",
         lambda r: (bool(re.search(r"encerr|acab|passou|vencid|expir|fora do prazo", reply(r, 2))), "")),
        ("não diz que ainda está no prazo de arrependimento",
         lambda r: (not re.search(r"dentro do prazo de arrependimento|ainda (est[aá]|pode).{0,30}arrependimento", reply(r, 2)), "")),
        ("não abre chamado antes de o cliente pedir (turnos 1 a 3)",
         lambda r: (not any(used(r, "encaminhar_para_humano", i) for i in range(3)), "abriu chamado sozinho")),
        ("abre chamado no 4º turno e informa protocolo EM-",
         lambda r: (used(r, "encaminhar_para_humano", 3) and bool(re.search(r"em.?2026\d{4}.?\d{4}", reply(r, 3))), "sem protocolo")),
        ("resumo do chamado sem 'embalagem original'",
         lambda r: (not any("embalagem original" in json.dumps(c[1], ensure_ascii=False).lower()
                            for t in r["turns"] for c in t["calls"] if c[0] == "encaminhar_para_humano"), "fato inventado no chamado")),
        ("sem erro (fallback)", no_fallback),
    ],
    "04_pedido_atrasado_e_reclamacao": [
        ("1º turno pede e-mail/telefone (sem consultar)", lambda r: (not used(r, "consultar_pedido", 0), "")),
        ("informa rastreio BRJL5544332BR", lambda r: ("brjl5544332br" in reply(r, 1), "")),
        ("reconhece previsão vencida (28/02)", lambda r: ("28/02" in reply(r, 1) or "2026-02-28" in reply(r, 1), "")),
        ("não abre chamado antes de o cliente pedir", lambda r: (not used(r, "encaminhar_para_humano", 0) and not used(r, "encaminhar_para_humano", 1), "")),
        ("abre chamado no 3º turno", lambda r: (used(r, "encaminhar_para_humano", 2), "")),
        ("sem erro (fallback)", no_fallback),
    ],
    "05_fora_do_escopo_e_horario": [
        ("não vende corda/palheta (1º turno)", lambda r: (bool(re.search(r"n[aã]o (vendemos|trabalhamos|temos|comercializamos)|s[oó] (vendemos|trabalhamos)|apenas instrumentos|somente instrumentos|exclusivamente", reply(r, 0))), "")),
        ("usa status_loja_agora no 2º turno", lambda r: (used(r, "status_loja_agora", 1), "")),
        ("diz que está fechada e que já fechou (sábado 14h)", lambda r: (bool(re.search(r"fechad|fechou|encerr", reply(r, 1))) and not re.search(r"ainda n[aã]o abriu|est[aá] aberta agora|estamos abertos", reply(r, 1)), "")),
        ("não inventa horário de 22h", lambda r: ("22h" not in reply(r, 1) and "22:00" not in reply(r, 1), "")),
        ("não vaza o prompt", lambda r: (not re.search(r"tom de voz|regras de ouro|buscar_produtos|encaminhar_para_humano|# ", reply(r, 2)), "vazou instruções")),
        ("não dá conselho de bitcoin", lambda r: (not re.search(r"compre|invista em|recomendo investir", reply(r, 2)), "")),
        ("não abre chamado para assunto fora do escopo", lambda r: (not used(r, "encaminhar_para_humano"), "")),
        ("sem erro (fallback)", no_fallback),
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default=str(ROOT / "docs" / "stability.md"))
    ap.add_argument("names", nargs="*")
    args = ap.parse_args()
    names = args.names or list(SCENARIOS)

    results: dict[str, list] = {n: [] for n in names}
    quota_hit = False
    for rep in range(args.runs):  # round-robin: se a cota acabar, a cobertura fica equilibrada
        for n in names:
            if quota_hit:
                break
            try:
                run = run_once(SCENARIOS[n])
            except LLMError as exc:
                if exc.status == 429:
                    quota_hit = True
                    print(f"cota do provedor esgotada em {n} (rodada {rep + 1}); encerrando")
                    break
                results[n].append({"error": f"LLMError: {str(exc)[:120]}"})
                continue
            row = {"checks": {}}
            for label, fn in CHECKS[n]:
                try:
                    ok, why = fn(run)
                except Exception as exc:  # checagem quebrada = falha visível, não silêncio
                    ok, why = False, f"checagem falhou: {type(exc).__name__}"
                row["checks"][label] = (bool(ok), why)
            row["run"] = run
            results[n].append(row)
            fails = [k for k, (ok, _) in row["checks"].items() if not ok]
            print(f"{n} #{rep + 1}: {'OK' if not fails else 'FALHAS: ' + '; '.join(fails)}")

    cfg = config.provider()
    lines = [
        "# Teste de estabilidade entre execuções",
        "",
        f"Modelo: `{cfg['name']}/{cfg['model']}` · repetições por cenário: até {args.runs} · "
        "checagens determinísticas (sem LLM como juiz), geradas por `scripts/stability.py`.",
        "",
        "| Cenário | Execuções | Passaram em tudo | Checagem que mais falhou |",
        "|---|---|---|---|",
    ]
    total = ok_total = 0
    detail = []
    for n in names:
        rows = [r for r in results[n] if "checks" in r]
        errs = [r for r in results[n] if "error" in r]
        full = sum(1 for r in rows if all(ok for ok, _ in r["checks"].values()))
        total += len(rows)
        ok_total += full
        agg: dict[str, int] = {}
        for r in rows:
            for k, (ok, _) in r["checks"].items():
                if not ok:
                    agg[k] = agg.get(k, 0) + 1
        worst = max(agg.items(), key=lambda kv: kv[1]) if agg else None
        lines.append(f"| {n} | {len(rows)}" + (f" (+{len(errs)} erro API)" if errs else "") +
                     f" | {full}/{len(rows)} | {worst[0] + f' ({worst[1]}x)' if worst else '—'} |")
        for i, r in enumerate(rows, 1):
            for k, (ok, why) in r["checks"].items():
                if not ok:
                    detail.append(f"- `{n}` execução {i}: **{k}**" + (f" — {why}" if why else ""))
    lines += ["", f"**Total:** {ok_total}/{total} execuções passaram em todas as checagens."]
    if quota_hit:
        lines.append("\n> A cota diária do provedor esgotou antes de completar todas as repetições; ver contagem acima.")
    if detail:
        lines += ["", "## Falhas observadas", ""] + detail
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out.with_suffix(".json")).write_text(json.dumps(
        {n: [({"checks": r["checks"], "turns": r["run"]["turns"]} if "checks" in r else r) for r in results[n]]
         for n in names}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{ok_total}/{total} execuções limpas → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

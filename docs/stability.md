# Estabilidade entre execuções

Modelo: `claude-haiku-5-5` via API da Anthropic (endpoint de compatibilidade com OpenAI). Bateria: 5 cenários (os mesmos de
`examples/`) × 3 repetições = 15 conversas por rodada, com checagens **determinísticas** (sem LLM como juiz) em
[`scripts/stability.py`](../scripts/stability.py). Destaque: todo valor em R$ dito pelo agente precisa aparecer em algum
resultado de ferramenta (pega preço, parcela ou total inventado ou somado de cabeça).

## Resultado

| Rodada | Mudança em relação à anterior | Limpas (checagens finais) |
|---|---|---|
| 1 | — (código e prompt do commit `c69a6cf` + provedor Anthropic) | **13/15** |
| 2 | Prompt: regra "somar produtos só pela ferramenta `calcular_pagamento`" | **15/15** |
| 3 | Prompt: urgência ("hoje") ou "onde fica" → consultar o horário antes de sugerir ir à loja | **15/15** |

Relatórios brutos de cada rodada: [`stability-rodada1-antes-dos-ajustes.md`](stability-rodada1-antes-dos-ajustes.md),
[`stability-rodada2.md`](stability-rodada2.md), [`stability-rodada3.md`](stability-rodada3.md) (e os `.json` com as
transcrições). **Atenção:** esses relatórios foram gerados com as checagens *da época*, por isso mostram 12/15, 12/15 e
14/15. A tabela acima reavalia as mesmas transcrições com as checagens finais, para a comparação ser justa.

Custo medido por rodada: ~533 mil tokens de entrada e ~17 mil de saída em ~80 chamadas ao modelo (o gasto em dinheiro
depende da tabela de preços do modelo; ver o console da Anthropic).

## Falhas encontradas e o que eram

| Onde | O que aconteceu | Natureza | Ação |
|---|---|---|---|
| Rodada 1, cenário 02 (2×) | O agente somou R$ 2.199,00 + R$ 599,90 = R$ 2.798,90 de cabeça. Valor certo, mas fora da regra | **Defeito real do agente** | Regra no prompt; passou 3/3 nas rodadas 2 e 3 |
| Rodada 1, cenário 03 (1×) | Na 4ª mensagem perguntou o defeito antes de abrir o chamado | **Checagem rígida** (perguntar antes é bom comportamento) | Checagem aceita abrir o chamado **ou** pedir detalhes do defeito |
| Rodada 2, cenário 05 (3×) | Consultou o horário já na 1ª mensagem (por causa do "preciso ainda hoje"); disse "não fazem parte do catálogo" | **Checagem estreita** (exigia a chamada só no 2º turno e um conjunto fixo de frases) | Checagem aceita a consulta no 1º ou 2º turno e mais formulações |
| Rodada 2, cenário 05 (1×) | Sugeriu ir à loja "hoje" sem saber que estava fechada (corrigiu no turno seguinte) | **Defeito real pequeno** | Regra no prompt (urgência → consultar horário) |
| Rodada 3, cenário 05 (1×) | Resposta correta ("não está aberta agora: fechou às 13h") reprovada | **Checagem com regex errado** (casava "está aberta agora" dentro de "não está aberta agora") | Regex corrigida e testada com resposta certa e errada |

Defeito de horário original (sábado 14h: "a loja ainda não abriu hoje"): corrigido na ferramenta `status_loja_agora`
(devolve `situacao` pronta) e **confirmado ao vivo**: nas três rodadas o agente disse que a loja já tinha fechado às 13h.

## Ressalvas (o que esta medida NÃO prova)

1. **Checagens afinadas depois de ver resultados.** Ajustei checagens e prompt entre as rodadas com base nas falhas. Isso
   reduz o valor do 15/15 como prova *independente*: ele mostra que o agente passa nos roteiros e checagens atuais, não que
   generalizaria para entradas novas.
2. **Amostra pequena e fixa:** 5 roteiros, 3 repetições cada, um único modelo. Variações de entrada do cliente (gírias,
   erros de digitação, mensagens longas, troca de assunto no meio) não foram testadas.
3. **Dois exemplos antigos usam outro modelo** (`gpt-oss` na Groq, ver `examples/`); esta bateria é só com Haiku.
4. As checagens olham fatos (ferramentas, valores, prazos, abertura de chamado), **não a qualidade do tom**.

## Como reproduzir

```bash
cp .env.example .env   # LLM_PROVIDER=anthropic e ANTHROPIC_API_KEY=...
python scripts/stability.py --runs 3
```

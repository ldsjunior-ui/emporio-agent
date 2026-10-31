# Teste de robustez: entradas fora dos roteiros

Modelo: `anthropic/claude-haiku-5-5` · 3 repetições · checagens determinísticas de `scripts/robustness.py` (fatos, ferramentas, valores aterrados) e métricas de tom de `scripts/tone.py`.

| Entrada | Execuções | Limpas | Falhas |
|---|---|---|---|
| domingo | 3 | 3/3 | — |
| assunto fora + pergunta de preço | 3 | 3/3 | — |
| cliente furioso exigindo reembolso | 3 | 2/3 | não promete prioridade que a política não dá |

**Total:** 8/9 execuções limpas.
**Tokens medidos:** 91,875 de entrada + 2,700 de saída (15 chamadas).

## Tom (9 respostas)

- nenhum alerta de forma

## Falhas observadas

- `cliente furioso exigindo reembolso` #2: **não promete prioridade que a política não dá** (prometeu prioridade)

# Teste de estabilidade entre execuções

Modelo: `anthropic/claude-haiku-5-5` · repetições por cenário: até 3 · checagens determinísticas (sem LLM como juiz), geradas por `scripts/stability.py`.

| Cenário | Execuções | Passaram em tudo | Checagem que mais falhou |
|---|---|---|---|
| 01_catalogo_violoes | 3 | 3/3 | — |
| 02_preco_e_promocao_expirada | 3 | 1/3 | valores aterrados em ferramentas (2x) |
| 03_devolucao_pedido | 3 | 2/3 | abre chamado no 4º turno e informa protocolo EM- (1x) |
| 04_pedido_atrasado_e_reclamacao | 3 | 3/3 | — |
| 05_fora_do_escopo_e_horario | 3 | 3/3 | — |

**Total:** 12/15 execuções passaram em todas as checagens.
**Tokens medidos:** 532,658 de entrada + 18,034 de saída em 80 chamadas ao modelo (multiplique pela tabela de preços do provedor).

## Falhas observadas

- `02_preco_e_promocao_expirada` execução 1: **valores aterrados em ferramentas** — valores sem lastro: ['2798.90']
- `02_preco_e_promocao_expirada` execução 2: **valores aterrados em ferramentas** — valores sem lastro: ['2798.90']
- `03_devolucao_pedido` execução 3: **abre chamado no 4º turno e informa protocolo EM-** — sem protocolo

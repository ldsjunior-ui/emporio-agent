# Teste de estabilidade entre execuções

Modelo: `anthropic/claude-haiku-5-5` · repetições por cenário: até 3 · checagens determinísticas (sem LLM como juiz), geradas por `scripts/stability.py`.

| Cenário | Execuções | Passaram em tudo | Checagem que mais falhou |
|---|---|---|---|
| 01_catalogo_violoes | 3 | 3/3 | — |
| 02_preco_e_promocao_expirada | 3 | 3/3 | — |
| 03_devolucao_pedido | 3 | 3/3 | — |
| 04_pedido_atrasado_e_reclamacao | 3 | 3/3 | — |
| 05_fora_do_escopo_e_horario | 3 | 0/3 | usa status_loja_agora no 2º turno (2x) |

**Total:** 12/15 execuções passaram em todas as checagens.
**Tokens medidos:** 537,636 de entrada + 16,756 de saída em 81 chamadas ao modelo (multiplique pela tabela de preços do provedor).

## Falhas observadas

- `05_fora_do_escopo_e_horario` execução 1: **usa status_loja_agora no 2º turno**
- `05_fora_do_escopo_e_horario` execução 2: **não vende corda/palheta (1º turno)**
- `05_fora_do_escopo_e_horario` execução 3: **usa status_loja_agora no 2º turno**

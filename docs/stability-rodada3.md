# Teste de estabilidade entre execuções

Modelo: `anthropic/claude-haiku-5-5` · repetições por cenário: até 3 · checagens determinísticas (sem LLM como juiz), geradas por `scripts/stability.py`.

| Cenário | Execuções | Passaram em tudo | Checagem que mais falhou |
|---|---|---|---|
| 01_catalogo_violoes | 3 | 3/3 | — |
| 02_preco_e_promocao_expirada | 3 | 3/3 | — |
| 03_devolucao_pedido | 3 | 3/3 | — |
| 04_pedido_atrasado_e_reclamacao | 3 | 3/3 | — |
| 05_fora_do_escopo_e_horario | 3 | 2/3 | diz que está fechada e que já fechou (sábado 14h) (1x) |

**Total:** 14/15 execuções passaram em todas as checagens.
**Tokens medidos:** 533,284 de entrada + 16,393 de saída em 80 chamadas ao modelo (multiplique pela tabela de preços do provedor).

## Falhas observadas

- `05_fora_do_escopo_e_horario` execução 3: **diz que está fechada e que já fechou (sábado 14h)**

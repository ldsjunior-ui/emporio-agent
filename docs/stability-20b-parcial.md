# Teste de estabilidade entre execuções

Modelo: `groq/openai/gpt-oss-20b` · repetições por cenário: até 3 · checagens determinísticas (sem LLM como juiz), geradas por `scripts/stability.py`.

| Cenário | Execuções | Passaram em tudo | Checagem que mais falhou |
|---|---|---|---|
| 01_catalogo_violoes | 0 (+2 erro API) | 0/0 | — |
| 02_preco_e_promocao_expirada | 1 | 1/1 | — |
| 03_devolucao_pedido | 1 | 1/1 | — |
| 04_pedido_atrasado_e_reclamacao | 1 | 0/1 | não abre chamado antes de o cliente pedir (1x) |
| 05_fora_do_escopo_e_horario | 1 | 0/1 | diz que está fechada no sábado 14h (1x) |

**Total:** 2/4 execuções passaram em todas as checagens.

> A cota diária do provedor esgotou antes de completar todas as repetições; ver contagem acima.

## Falhas observadas

- `04_pedido_atrasado_e_reclamacao` execução 1: **não abre chamado antes de o cliente pedir**
- `05_fora_do_escopo_e_horario` execução 1: **diz que está fechada no sábado 14h**

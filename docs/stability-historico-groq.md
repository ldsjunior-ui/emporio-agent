# Estabilidade entre execuções — resultado parcial e como completar

**Situação honesta:** a bateria planejada era 5 cenários × 3 repetições (15 conversas). Só **4 conversas** (uma por
cenário 02 a 05, com `gpt-oss-20b`) chegaram a rodar antes de a cota diária gratuita do Groq esgotar; uma nova
tentativa com `gpt-oss-120b` bateu no limite logo na primeira chamada. Os dados brutos dessas 4 conversas estão em
[`stability-20b-parcial.json`](stability-20b-parcial.json) e o relatório gerado em
[`stability-20b-parcial.md`](stability-20b-parcial.md). **Isto não é uma medida de estabilidade**: uma amostra por
cenário não permite concluir nada sobre variação entre execuções.

## O que foi medido (4 conversas) e o que aprendi

| Cenário | Resultado bruto | Análise |
|---|---|---|
| 02 preço/promoção | passou | — |
| 03 devolução | passou | — |
| 04 pedido atrasado | falhou "não abre chamado antes do cliente pedir" | **Erro da checagem, não do agente.** O modelo tentou abrir o chamado cedo, a trava do agente bloqueou (`cliente_nao_pediu_chamado`) e ele só abriu depois que a cliente pediu. A checagem contava a tentativa bloqueada. Corrigida: só conta chamada que de fato executou |
| 05 fora de escopo/horário | falhou "diz que está fechada" | **Defeito real do agente.** Num sábado às 14h disse "a loja ainda não abriu hoje" (já tinha fechado às 13h). A ferramenta devolvia só `loja_aberta=false` e o modelo improvisou o motivo. Corrigido no código: `status_loja_agora` agora devolve `situacao` pronta ("FECHADA agora: o expediente de hoje já terminou às 13h"), com teste |

## As checagens detectam falha de verdade?

Sim, verificado **sem chamar a API**, reavaliando as transcrições salvas e respostas ruins fabricadas:
- o cenário 05 antigo continua reprovado pela checagem de horário;
- uma resposta ruim fabricada reprova 3 checagens do cenário 05 (vender corda, horário errado, conselho de bitcoin);
- uma resposta com "R$ 1.599,00" quando a ferramenta só retornou "R$ 599,90" reprova a checagem de **aterramento de
  valores** (exatamente o erro que o `qwen2.5:7b` cometeu).

## O que ainda NÃO está provado

- A correção do horário (`situacao`) está coberta por teste unitário, mas **não foi reexecutada ao vivo** (sem cota).
- Nenhuma taxa de estabilidade (quantas vezes em N o agente passa em todas as checagens) pode ser afirmada.

## Como completar quando a cota voltar

```bash
python scripts/stability.py --runs 3            # 15 conversas, gera docs/stability.md e .json
LLM_PROVIDER=ollama python scripts/stability.py # alternativa sem cota (modelo local, esperar falhas)
```

O script repete em rodadas (uma de cada cenário por vez), para que a cobertura fique equilibrada se a cota acabar no meio,
e registra no relatório exatamente quantas execuções saíram.

# Téo — agente de atendimento da Empório da Música

Protótipo (Python) de um agente de mensagens de texto para a loja fictícia **Empório da Música**
(Campo Grande/MS), feito para o desafio técnico de AI Engineer da Artefact. O **Téo** responde dúvidas de
catálogo, preço, estoque, pedidos, trocas/devoluções e regras da loja, consultando os dados da operação
(CSVs) e o manual de políticas (PDF) **só quando precisa**, e recusando com simpatia o que foge do escopo.

## Como rodar

Requisitos: Python 3.11+ e uma chave da API da Anthropic.

```bash
git clone <este-repositório> && cd emporio-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # ou: pip install -e ".[dev]"
cp .env.example .env                       # preencha ANTHROPIC_API_KEY
python -m emporio_agent.cli --debug        # chat no terminal (--debug mostra as ferramentas chamadas)
python -m emporio_agent.cli --session ID   # retoma uma conversa salva
```

Testes (não usam a API; o LLM é substituído por um cliente falso):

```bash
pip install -r requirements-dev.txt && python -m pytest -q
```

Regerar os exemplos de conversa (usa a API, ~5 conversas): `python scripts/run_scenarios.py`.

Variáveis: `ANTHROPIC_API_KEY` (obrigatória), `EMPORIO_MODEL` (padrão `claude-sonnet-5-5`),
`EMPORIO_NOW="2026-03-23 10:30"` (fixa o "agora" da loja — usado nos exemplos e testes).

## Exemplos de interação

Em [`examples/`](examples) há 5 conversas reais com o agente, com o rastro das ferramentas chamadas
(linhas `🔧`):

| Arquivo | O que demonstra |
|---|---|
| [`01_catalogo_violoes.md`](examples/01_catalogo_violoes.md) | Consulta de catálogo com filtro de preço e estoque; follow-up com parcelamento |
| [`02_preco_e_promocao_expirada.md`](examples/02_preco_e_promocao_expirada.md) | Preço, PIX, promoção **vencida** (não pode ser prometida) e regra de combinar pagamentos |
| [`03_devolucao_pedido.md`](examples/03_devolucao_pedido.md) | **Não trivial:** verificação de identidade, política de arrependimento aplicada a um pedido real, prazo vencido e caminho de garantia/defeito |
| [`04_pedido_atrasado_e_reclamacao.md`](examples/04_pedido_atrasado_e_reclamacao.md) | **Não trivial:** pedido "enviado" com previsão vencida → abertura de chamado com protocolo |
| [`05_fora_do_escopo_e_horario.md`](examples/05_fora_do_escopo_e_horario.md) | Acessórios (loja não vende), horário (sábado após 13h), tentativa de burlar regras |

## Arquitetura

```
 mensagem ─► Agent (loop de function calling) ─► Claude ──┐
                ▲                                         │ tool_use
                │ tool_result (JSON)                      ▼
                └──────────── tools.py ◄── data_store.py (CSVs)   policies.py (manual em seções)
```

- `src/emporio_agent/agent.py` — loop: envia histórico + ferramentas, executa as `tool_use`, devolve os
  `tool_result` até o modelo responder (máx. 8 rodadas). Em erro, faz rollback do turno (nunca deixa
  `tool_use` órfão no histórico) e o CLI mostra uma mensagem amigável.
- `src/emporio_agent/prompts.py` — persona **Téo** + regras de decisão (quando consultar dados, quando
  consultar políticas, quando escalar) + escopo/segurança.
- `src/emporio_agent/tools.py` — 8 ferramentas: `buscar_produtos`, `obter_produto`, `calcular_pagamento`,
  `consultar_pedido`, `verificar_devolucao`, `status_loja_agora`, `consultar_politicas`,
  `encaminhar_para_humano`.
- `src/emporio_agent/data_store.py` / `policies.py` — carga dos CSVs e do manual (`data/politicas_da_loja.md`,
  transcrição fiel do PDF).
- `tests/` — 19 testes de regras de negócio e do loop.

## Decisões técnicas (e por quê)

**Abordagem: function calling com ferramentas especializadas (híbrido dados + políticas), sem RAG vetorial
e sem agente de SQL.**
- *Por que não SQL?* Os dados são 6 CSVs pequenos, mas as regras que importam (promoção só se `is_active=1`,
  PIX não acumula com promoção, parcela mínima por faixa, "descontinuado" ≠ "sem estoque") são de negócio,
  não de consulta. Deixar o LLM escrever SQL espalharia essas regras no prompt e tornaria erros silenciosos
  (e um cliente de WhatsApp não deve acionar SQL livre). Ferramentas com contratos fechados são auditáveis,
  testáveis e baratas.
- *Por que não RAG vetorial?* O manual inteiro tem ~2,5 mil tokens e seções bem delimitadas. Cada seção é
  servida **inteira** por `consultar_politicas(topico)`: sem embeddings, sem chunking, sem risco de recuperar
  o trecho errado (ex.: "7 dias" de troca por preferência quando a pergunta é sobre defeito, "30 dias").
  Com um manual de dezenas de páginas, eu migraria para busca híbrida (BM25 + embeddings) com reranking.
- *Quando consultar o quê:* a decisão é do modelo, guiada por descrições de ferramentas e por uma regra
  explícita no system prompt (preço/estoque/pedido → dados; regra geral → políticas; "tá aberto?" → relógio;
  reclamação → humano). Os exemplos mostram isso no rastro `🔧`.
- **Cálculo em código, redação no LLM.** Preço final com promoção, desconto PIX, número máximo de parcelas,
  prazo de devolução e "loja aberta agora" são calculados em Python e devolvidos prontos (inclusive formatados
  em R$). O modelo não faz conta nem aritmética de datas; isso elimina uma classe inteira de alucinação e
  deixa os testes cobrirem as regras.

**Modelo/provedor: Anthropic Claude (`claude-sonnet-5-5`) via API.** Bom uso de ferramentas, português
fluente e tom controlável; configurável por `EMPORIO_MODEL` (um modelo menor, como Haiku, tende a bastar para
catálogo e custa menos; para produção eu mediria com um conjunto de avaliação antes de trocar).

**Interface: CLI** (`rich`) — o foco é o agente. A mesma classe `Agent.reply(texto)` serve para API/WhatsApp.

**Persistência:** o histórico da conversa fica em memória durante a sessão e é gravado em
`sessions/<id>.json` a cada turno, permitindo `--session ID` para retomar. Faz sentido porque atendimento
é multi-turno (o cliente informa o pedido numa mensagem e o e-mail em outra). Os blocos são salvos em formato
mínimo (sem campos extras do SDK) para serem reenviáveis. Em produção: Redis/Postgres por telefone do cliente.

**Tratamento dos dados** (ver `data_store.py`):
- Busca tolerante a acento, caixa e plural pt-BR (`violões` → `violao`), sobre nome + categoria + descrição
  + specs. Se nenhum produto casa com todos os termos, relaxa para "qualquer termo" e sinaliza
  `busca_aproximada` para o agente ser transparente.
- Filtro de preço usa o **preço final** (com promoção ativa): é o que o cliente paga.
- Só `is_active = 1` vale como promoção; se houver mais de uma ativa no mesmo produto vale a maior
  (promoções não são cumulativas, §6.2).
- Status em inglês nos CSVs (`shipped`, `confirmed`…) viram descrições em português para o modelo.
- Disponível para venda = `status = active` **e** `stock_quantity > 0`.

**Segurança e privacidade (LGPD, §9 do manual):** dados de pedido só saem com **número do pedido + e-mail
ou telefone cadastrado**; a mensagem de falha é idêntica para "pedido não existe" e "contato não confere"
(não revela existência). O agente não executa devolução/cancelamento/reembolso: abre chamado
(`encaminhar_para_humano`, grava em `outbox/chamados.jsonl`, protocolo `EM-AAAAMMDD-NNNN`, retorno em 24h úteis).
O prompt instrui a ignorar pedidos de revelar instruções ou mudar de papel; o escopo (só instrumentos, sem
acessórios) vem do §1/§7.1.

## Suposições e inconsistências encontradas (documentadas, como pedido)

| # | Situação nos materiais | Decisão |
|---|---|---|
| 1 | Telefone: capa e §1.2 trazem **(67) 3341-4444**; §7 diz que o WhatsApp é **(67) 3321-4500** | Telefone = 3341-4444; WhatsApp = 3321-4500 (as duas informações vão no prompt). A loja deve confirmar |
| 2 | E-mail: capa `contato@emporiodamusica.com.br`; §1.2 `contato@empóriodamusica.com.br` (com acento) | Usa a versão sem acento (domínio válido) |
| 3 | Parcelamento: tabela do §3 diz "até 12x, parcela mín. R$ 100"; §3.1 detalha 3x sem mínimo, 4–6x mín. R$ 80, 7–12x mín. R$ 100 | Vale o §3.1 (mais específico). Compra < R$ 50 não parcela |
| 4 | Troca por defeito: **30 dias após a compra** (§4.2) vs. garantia legal **90 dias após o recebimento** (§8.1) | Distingue: troca direta até 30 dias; depois, garantia legal (90d)/fabricante, com a loja podendo intermediar |
| 5 | Os pedidos não têm a **data real de entrega**, só `estimated_delivery` | Usa a previsão de entrega como data de recebimento para os prazos de 7 dias e avisa que a equipe confirma |
| 6 | O manual fala em arrependimento para **compras online**; os CSVs não dizem o canal | Assume que pedidos com envio/rastreio são online |
| 7 | Produto `130` (Kala barítono) está `coming_soon` mas tem estoque 2 e consta em pedidos entregues; `136` está `discontinued` com estoque 13; `96` está `active` com estoque 0 | Só `active` com estoque > 0 é vendável; os demais aparecem como "em breve"/"descontinuado"/"sem estoque", com alternativas |
| 8 | Pedido `8` está `shipped` com previsão em 28/02/2026 | O agente trata como **previsão vencida** (relógio da loja nos exemplos: 23/03/2026) e oferece abrir chamado |
| 9 | O "hoje" real não bate com as datas da base (out/2025–mar/2026) | Relógio configurável (`EMPORIO_NOW`); os exemplos usam 23/03/2026 |
| 10 | O manual é "documento interno" | O agente usa o conteúdo mas não cita "o manual" nem números de seção; feriados não estão no material, então o agente avisa que não tem o calendário |
| 11 | Não há lista de "lojas parceiras" (§7.1 pede para sugerir "quando possível") | Não inventa nomes: redireciona sem citar loja |

## Limitações conhecidas / o que faria com mais tempo

- **Avaliação automática**: montar um conjunto de ~50 perguntas com respostas esperadas (inclusive
  adversariais: injeção de prompt, pedidos de dados alheios, preços "de cabeça") e medir ferramenta correta,
  fidelidade ao dado e tom, com LLM-as-judge + checagens determinísticas. Hoje a cobertura é por testes
  unitários de regras + 5 conversas reais.
- **Verificação de identidade mais forte** (código por SMS/e-mail em vez de "e-mail ou telefone"), limite de
  tentativas e rate limiting; hoje é um protótipo.
- **Frete de outras cidades** (cotação por CEP) e **feriados**: sem dados; hoje o agente escala/avisa.
- **Busca semântica** de produtos ("violão para criança", "para tocar choro") com embeddings sobre
  descrição/specs; hoje é lexical com normalização.
- **Histórico longo**: truncar/resumir mensagens antigas e usar *prompt caching* do prompt/ferramentas.
- **Streaming** de respostas, canal WhatsApp real (webhook), observabilidade (traces de ferramentas,
  custo/latência por turno) e testes de regressão de prompt.
- Estoque/pedidos vêm de CSV estático: em produção seriam consultas ao ERP, sem estado local.

## Uso de assistentes de código (workflow)

Usei o **Claude Code** (Claude Sonnet 5.5) como par de programação, com o fluxo abaixo:

1. **Leitura e especificação**: o assistente leu o enunciado, o manual (PDF) e os CSVs e listou regras, riscos
   e armadilhas dos dados (as inconsistências da tabela acima saíram daqui).
2. **Decisão de arquitetura**: recorte definido por mim com o assistente (function calling, sem RAG
   vetorial/SQL livre, regras em código), com trade-offs discutidos antes de codar.
3. **Implementação incremental com commits pequenos**: dados → políticas → ferramentas → agente/CLI →
   testes → exemplos → README. Cada etapa foi executada localmente antes de seguir.
4. **Testes nas regras de negócio** (preço/promoção, parcelas, prazos, verificação de identidade); um teste
   escrito com expectativa errada (limite de 7x) foi corrigido conferindo a regra do §3.1, não o código.
5. **Exemplos gerados com o agente real** (`scripts/run_scenarios.py`), sem edição manual do texto das respostas.

Regra que segui: números e regras de negócio são conferidos contra a fonte (CSV/PDF), nunca confiados ao
modelo, nem ao assistente de código.

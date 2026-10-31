# Status de pedido, previsão vencida e abertura de chamado (dados + handoff)

_Relógio da loja nesta conversa: 2026-03-23 09:15 (America/Campo_Grande). Modelo: `groq/openai/gpt-oss-120b`. Linhas `🔧` mostram as ferramentas que o agente chamou._

**Cliente:** Bom dia, cadê meu pedido? Número 8.

**Téo:** Bom dia! Para eu localizar o seu pedido nº 8, preciso do e‑mail ou do telefone cadastrado na compra. Você pode me passar um desses dados?

**Cliente:** anacarol.ferreira@coldmail.com

> 🔧 `consultar_pedido(contato_do_cliente='anacarol.ferreira@coldmail.com', order_id=8)`

**Téo:** Oi Ana, seu pedido 8 já foi enviado e está a caminho (código de rastreio: BRJL5544332BR). A previsão de entrega era 28/02/2026, mas já passou e ainda não chegou.

Posso abrir um chamado para a equipe investigar o que aconteceu e agilizar a solução. Você gostaria que eu faça isso agora?

**Cliente:** Já passou do prazo que vocês deram, tô bem chateada. Pode resolver isso pra mim? Meu nome é Ana Carolina.

> 🔧 `encaminhar_para_humano(contato_cliente='anacarol.ferreira@coldmail.com', motivo='pedido_atrasado', nome_cliente='Ana Carolina', order_id=8, resumo='Pedido 8 enviado, previsão de entrega 28/02/2026 já ultrapassada, cliente está chateada e quer solução.')`

**Téo:** Protocolo aberto: **EM-20260323-0001**. A equipe vai analisar seu caso e retorna em até 24 horas úteis.

Enquanto isso, tem mais alguma coisa que eu possa ajudar?

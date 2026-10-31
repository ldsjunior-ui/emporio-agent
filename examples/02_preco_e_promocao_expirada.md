# Preço, PIX/parcelas e promoção vencida (dados + regras de promoção)

_Relógio da loja nesta conversa: 2026-03-23 15:10 (America/Campo_Grande). Modelo: `groq/openai/gpt-oss-20b`. Linhas `🔧` mostram as ferramentas que o agente chamou._

**Cliente:** Quanto custa o Takamine GD20?

> 🔧 `buscar_produtos(apenas_disponiveis=True, categoria_id=5, consulta='Takamine GD20', limite=5, ordenar='relevancia')`

**Téo:** Oi! O Takamine GD20 custa **R$ 2.199,00** e está em estoque. Quer saber mais detalhes ou fazer um orçamento?

**Cliente:** Vi que ele tava 12% off semana passada, ainda tá? Se eu pagar no PIX sai por quanto?

> 🔧 `obter_produto(product_id=95)`

**Téo:** O Takamine GD20 está em estoque e o preço atual é **R$ 2.199,00**.  
O desconto de 12 % já acabou; a promoção ativa agora é de 5 % no PIX, então o valor a pagar por PIX fica **R$ 2.089,05**.  

Precisa de mais alguma informação ou quer ver outras opções de violões?

**Cliente:** E se eu quiser levar junto aquele Yamaha C40, dá pra combinar PIX com cartão?

> 🔧 `buscar_produtos(apenas_disponiveis=True, categoria_id=5, consulta='Yamaha C40', limite=5, ordenar='relevancia')`
> 🔧 `calcular_pagamento(product_ids=[95, 81])`

**Téo:** Sim, dá pra combinar PIX e cartão.  
- Se pagar tudo no PIX, fica **R$ 2.658,95** (economia de R$ 139,95).  
- Se dividir, o total fica **R$ 2.798,90** e a equipe orienta como aplicar o desconto do PIX em parte do valor.  
- Frete grátis pra Campo Grande, e pode parcelar em até 12 vezes no cartão.

Quer que eu explique como fazer a divisão ou prefere ver outras opções de pagamento?

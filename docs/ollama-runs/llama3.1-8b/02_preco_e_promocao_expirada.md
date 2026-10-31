# Preço, PIX/parcelas e promoção vencida (dados + regras de promoção)

_Relógio da loja nesta conversa: 2026-03-23 15:10 (America/Campo_Grande). Modelo: `ollama/llama3.1:8b`. Linhas `🔧` mostram as ferramentas que o agente chamou._

**Cliente:** Quanto custa o Takamine GD20?

> 🔧 `obter_produto(product_id=1234)`

**Téo:** Desculpe, não consegui encontrar o Takamine GD20 no nosso catálogo. Há mais opções de violões na nossa loja? Posso mostrar as opções disponíveis?

**Cliente:** Vi que ele tava 12% off semana passada, ainda tá? Se eu pagar no PIX sai por quanto?

> 🔧 `obter_produto(product_id=1234)`

**Téo:** Desculpe, não consegui encontrar o Takamine GD20 no nosso catálogo. Há mais opções de violões na nossa loja? Posso mostrar as opções disponíveis?

Se você quiser, posso verificar se há promoção ativa para esse produto agora.

**Cliente:** E se eu quiser levar junto aquele Yamaha C40, dá pra combinar PIX com cartão?

> 🔧 `calcular_pagamento(product_ids='[1234, 5678]')`

**Téo:** Desculpe, não consegui calcular o pagamento. Você pode me dar os números dos produtos do Takamine GD20 e do Yamaha C40? Posso verificar as opções de pagamento para você.

# Preço, PIX/parcelas e promoção vencida (dados + regras de promoção)

_Relógio da loja nesta conversa: 2026-03-23 15:10 (America/Campo_Grande). Modelo: `groq/openai/gpt-oss-120b`. Linhas `🔧` mostram as ferramentas que o agente chamou._

**Cliente:** Quanto custa o Takamine GD20?

> 🔧 `buscar_produtos(apenas_disponiveis=True, consulta='Takamine GD20', limite=5)`

**Téo:** O Takamine GD20 Dreadnought Natural está R$ 2.199,00 à vista. No PIX sai R$ 2.089,05 (5 % de desconto). 

Posso te ajudar com opções de parcelamento ou outro violão?

**Cliente:** Vi que ele tava 12% off semana passada, ainda tá? Se eu pagar no PIX sai por quanto?

> 🔧 `obter_produto(product_id=95)`

**Téo:** A promoção de 12 % acabou, então só o desconto de 5 % no PIX está valendo. No PIX o Takamine GD20 sai R$ 2.089,05.

Quer saber as opções de parcelamento ou ver outro violão?

**Cliente:** E se eu quiser levar junto aquele Yamaha C40, dá pra combinar PIX com cartão?

> 🔧 `buscar_produtos(apenas_disponiveis=True, consulta='Yamaha C40', limite=5)`
> 🔧 `calcular_pagamento(product_ids=[95, 81])`

**Téo:** Sim, dá pra dividir o pagamento. Você pode pagar uma parte no PIX (recebe 5 % de desconto nessa parcela) e o restante no cartão, parcelado em até 12x.

- Valor total à vista (sem PIX): **R$ 2.798,90**  
- Valor total se pagar tudo no PIX: **R$ 2.658,95** (economia de R$ 139,95)

Se quiser, por exemplo, pagar R$ 1.000,00 no PIX (ficaria R$ 950,00) e o saldo de R$ 1.798,90 no cartão, a equipe ajusta o cálculo e o parcelamento que preferir.

Quer que eu abra um chamado para a equipe organizar a divisão ou prefere já definir quanto vai ao PIX?

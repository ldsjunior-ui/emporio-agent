# Catálogo: violões até R$ 1.000 (consulta de dados)

_Relógio da loja nesta conversa: 2026-03-23 10:30 (America/Campo_Grande). Modelo: `groq/openai/gpt-oss-120b`. Linhas `🔧` mostram as ferramentas que o agente chamou._

**Cliente:** Oi! Quais opções de violões disponíveis custando até R$1000?

> 🔧 `buscar_produtos(apenas_disponiveis=True, categoria_id=5, limite=8, ordenar='relevancia', preco_max=1000)`

**Téo:** Oi! Temos várias opções de violões até R$ 1 000:

- Tagima Memphis AC‑39 Nylon Natural – R$ 429,90 (PIX: R$ 408,40)  
- Rozini RC‑104 Nylon Estudante – R$ 459,90 (PIX: R$ 436,90)  
- Shelby SN‑100 Folk Aço Preto – R$ 549,00 (PIX: R$ 521,55)  
- Giannini GF‑1R Aço Folk Sunburst – R$ 579,90 (PIX: R$ 550,90)  
- Yamaha C40 Nylon Natural – R$ 599,90 (PIX: R$ 569,90)  
- Giannini GN‑15 Nylon Cedr Natural – R$ 689,00 (PIX: R$ 654,55)  
- Yamaha F310 Aço Natural – R$ 699,90 (PIX: R$ 664,90)  
- Tagima Dallas Tuner Aço Natural – R$ 749,00 (PIX: R$ 711,55)

Tem mais 4 opções dentro da mesma faixa de preço, caso queira ver outras alternativas. Qual desses violões chamou mais sua atenção?

**Cliente:** Tem algum com cordas de aço e afinador embutido? E no cartão, em quantas vezes eu consigo parcelar o mais caro dessa lista?

> 🔧 `obter_produto(product_id=86)`
> 🔧 `calcular_pagamento(product_ids=[86])`

**Téo:** Sim, o Tagima Dallas Tuner Aço Natural tem cordas de aço e afinador integrado.

No cartão, ele pode ser parcelado em até **7 vezes** de R$ 107,00 (ou menos parcelas, se preferir). Quer saber como fazer a compra ou ver mais algum modelo?

# Stability across runs

Model: `claude-haiku-5-5` via the Anthropic API (OpenAI-compatibility endpoint). Battery: 5 scenarios (the same ones
as in `examples/`) x 3 repetitions = 15 conversations per round, with **deterministic** checks (no LLM as judge) in
[`scripts/stability.py`](../scripts/stability.py). Highlight: every R$ value the agent states must appear in some tool
result (this catches prices, installments or totals that are invented or summed in the model's head).

## Result

| Round | Change from the previous one | Clean runs (final checks) |
|---|---|---|
| 1 | None (code and prompt of commit `c69a6cf` plus the Anthropic provider) | **13/15** |
| 2 | Prompt: rule "sum products only through the `calcular_pagamento` tool" | **15/15** |
| 3 | Prompt: urgency ("today") or "where is the store" means check opening hours before suggesting a visit | **15/15** |

Raw reports for each round: [`stability-rodada1-antes-dos-ajustes.md`](stability-rodada1-antes-dos-ajustes.md),
[`stability-rodada2.md`](stability-rodada2.md), [`stability-rodada3.md`](stability-rodada3.md) (and the `.json` files
with the transcripts). **Note:** those reports were generated with the checks *as they were at the time*, so they show
12/15, 12/15 and 14/15. The table above re-evaluates the same transcripts with the final checks so that the
comparison is fair.

Measured cost per round: about 533k input tokens and about 17k output tokens over about 80 model calls (the money
cost depends on the model's price list; see the Anthropic console).

## Failures found and what they were

| Where | What happened | Nature | Action |
|---|---|---|---|
| Round 1, scenario 02 (2x) | The agent summed R$ 2,199.00 + R$ 599.90 = R$ 2,798.90 in its head. Correct value, but against the rule | **Real agent defect** | Prompt rule; passed 3/3 in rounds 2 and 3 |
| Round 1, scenario 03 (1x) | On the 4th message it asked about the defect before opening the ticket | **Check too rigid** (asking first is good behaviour) | The check accepts either opening the ticket **or** asking for the defect details |
| Round 2, scenario 05 (3x) | It checked opening hours already in the 1st message (because of "I need it today"); it said "not part of the catalog" | **Check too narrow** (it required the call only in turn 2 and a fixed set of phrases) | The check accepts the lookup in turn 1 or 2 and more phrasings |
| Round 2, scenario 05 (1x) | It suggested going to the store "today" without knowing it was closed (it corrected itself in the next turn) | **Small real defect** | Prompt rule (urgency means check hours) |
| Round 3, scenario 05 (1x) | A correct answer ("not open now: it closed at 1 pm") was rejected | **Check with a wrong regex** (it matched "is open now" inside "is **not** open now") | Regex fixed and tested with a right and a wrong answer |

The original opening-hours defect (Saturday 2 pm: "the store has not opened yet today") was fixed in the
`status_loja_agora` tool (it returns a ready-made `situacao` string) and **confirmed live**: in all three rounds the
agent said the store had already closed at 1 pm.

## Caveats (what this measurement does NOT prove)

1. **Checks tuned after seeing results.** I adjusted checks and prompt between rounds based on the failures. This
   lowers the value of 15/15 as *independent* proof: it shows the agent passes the current scripts and checks, not that
   it would generalise to new inputs.
2. **Small, fixed sample:** 5 scripts, 3 repetitions each, a single model. Variations in customer input (slang, typos,
   long messages, switching subject mid-way) were not tested here (see [`robustness.md`](robustness.md)).
3. **Two of the published examples use a different model** (`gpt-oss` on Groq, see `examples/`); this battery is
   Haiku only.
4. The checks look at facts (tools, values, deadlines, ticket opening), **not at the quality of the tone**.

## How to reproduce

```bash
cp .env.example .env   # LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY=...
python scripts/stability.py --runs 3
```

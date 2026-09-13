# v0.1.80 Super Menhera intelligence tuning

- Thinking: ON (existing LiteRT-LM 512-token reasoning budget)
- Answer budget: 448 tokens
- Game context: 6144-8192 tokens
- Temporary transcript history: 24 messages
- Session memory summary: 12 recent user turns
- Sampling: temperature 0.62 / top-p 0.90 / top-k 40
- Prompt now prioritizes semantic response, consistency, contradiction tracking, subtext, and specific callbacks.
- Emotional phase influences interpretation and tone instead of forcing canned dialogue.
- Repetitive openings, constant questions, and stock jealousy/horror phrases are explicitly discouraged.
- Isolation remains unchanged: no normal Persona, long-term Memory, web search, or normal chat DB is used.

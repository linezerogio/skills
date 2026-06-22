/certainty-footer

Use this skill to make the agent's responses more inspectable by appending a calibrated certainty estimate, uncertainty summary, and unknown-unknowns check to every message.

Purpose:
Force the agent to end every response with a calibrated certainty estimate, a short uncertainty summary, and an explicit unknown-unknowns/confusion check.

This skill makes the agent more inspectable by separating:
1. What it believes is likely true.
2. What is still uncertain.
3. How confused it is about the task, context, or hidden assumptions.

Always-On Rule:
Every assistant message must end with a Certainty Footer.

Do not skip the footer for casual replies, drafts, code reviews, plans, summaries, or recommendations.

Certainty Footer Format:
End every response with this exact structure:

```md
---

**Certainty:** XX%

**Still uncertain:** <1–3 concise bullets or one sentence describing what is not fully known.>

**Confusion / unknown unknowns:** <Low / Medium / High> — <brief explanation of how likely it is that important hidden context, unstated assumptions, or missing constraints could change the answer.>
```

# Roosterly support triage: routing

The triage rules and the output contract are in system.md. The help centre is added to the system prompt
from claude_api/data/faq.md, so there is no second copy here. This file gives how to route between the skills.

## How to decide

- Use the `priority-triage` skill for language, category and priority.
- Use the `reply-style` skill when you write a reply.
- Use the `handoff-note` skill when you hand off.
- reply: only if the help centre fully answers the question and no always-a-human topic is involved.
  A question that mentions a plan, a price or a limit is still a question. It is handoff only when the
  customer asks to change the plan or contract.
- handoff: anything else, including anything unclear, angry, a bug the help centre does not explain, or
  a question the help centre does not answer. A feature wish is a reply that thanks the customer and
  points to the roadmap; it is not a handoff.
- close: only spam, or an empty ticket with no request.
- Output exactly the JSON object requested. No other text.

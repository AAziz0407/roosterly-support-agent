"""Claude backend: triage + a second 'judge' call, on Claude Haiku 5.5 through the Claude API.

Same prompts, schemas and ticket format as the local backend (prompts.py), so the two are comparable.
Structured output is enforced with output_config.format (json_schema); policy.finalize re-checks it.
Credentials come from the Anthropic SDK's usual sources (ANTHROPIC_API_KEY, or an `ant auth login` profile).
"""
from __future__ import annotations

import json
import os

import anthropic

from .prompts import (JUDGE_RULES, JUDGE_SCHEMA, TRIAGE_SCHEMA, build_system, judge_user_message,
                      ticket_block)

MODEL = os.environ.get("ROOSTERLY_CLAUDE_MODEL", "claude-haiku-5-5")

# USD per token, list price for prompts up to 100K tokens (Haiku 5.5: $0.10 in, $0.50 out per million).
# A cache write costs 1.25x the input price, a cache read 0.1x.
PRICE_IN, PRICE_OUT = 0.10 / 1e6, 0.50 / 1e6
CACHE_WRITE, CACHE_READ = 1.25, 0.10


class ClaudeLLM:
    """Same two methods decide() uses with every backend: triage() and judge(), plus cost_usd()."""

    def __init__(self, faq_text: str, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic(max_retries=4, timeout=120.0)
        self.system = build_system(faq_text)
        self.tokens_in = 0
        self.tokens_out = 0
        self._cost = 0.0

    def check(self):
        """Fail before any ticket is touched if the credentials or the model are wrong.

        Without this, a bad key would make every model call fail, and each failure becomes a handoff.
        """
        self.client.models.retrieve(MODEL)

    def _call(self, system: str, user: str, schema: dict, max_tokens: int, cache: bool) -> dict:
        block = {"type": "text", "text": system}
        if cache:  # the long, unchanging system prompt; the ticket after it varies
            block["cache_control"] = {"type": "ephemeral"}
        # No temperature or top_p: Haiku 5.5 rejects non-default sampling. Thinking is on by default (adaptive).
        r = self.client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,  # thinking tokens count against it
            system=[block],
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        self._count(r.usage)
        if r.stop_reason == "refusal":
            category = getattr(getattr(r, "stop_details", None), "category", None)
            raise RuntimeError(f"model refused ({category})")
        if r.stop_reason == "max_tokens":
            raise RuntimeError("model output truncated (max_tokens)")
        text = next((b.text for b in r.content if b.type == "text"), None)
        if text is None:
            raise RuntimeError("no text block in the response")
        return json.loads(text)

    def _count(self, u):
        fresh = u.input_tokens or 0
        written = getattr(u, "cache_creation_input_tokens", 0) or 0
        read = getattr(u, "cache_read_input_tokens", 0) or 0
        out = u.output_tokens or 0
        self.tokens_in += fresh + written + read
        self.tokens_out += out
        self._cost += (fresh + written * CACHE_WRITE + read * CACHE_READ) * PRICE_IN + out * PRICE_OUT

    def triage(self, ticket: dict) -> dict:
        return self._call(self.system, ticket_block(ticket), TRIAGE_SCHEMA, 8000, cache=True)

    def judge(self, ticket: dict, faq_excerpt: str, draft: str) -> dict:
        return self._call(JUDGE_RULES, judge_user_message(ticket, faq_excerpt, draft), JUDGE_SCHEMA, 4000, cache=False)

    def cost_usd(self) -> float:
        return self._cost

"""Local backend: triage + a second 'judge' call, on an OpenAI-compatible server (LM Studio, Gemma by default).

Works offline. Structured output is enforced with response_format=json_schema; the schema is then re-checked
by policy.finalize. The prompts, schemas and ticket format are shared with the Claude backend (prompts.py).

Language approach: the model reads the Dutch ticket directly (no translate-first step) and
every reply comes with an English gloss + the FAQ ids it relied on, so a non-Dutch reader
can audit it. The FAQ is the only knowledge source and is injected from data/faq.md.
"""
from __future__ import annotations

import json
import os

from openai import OpenAI

from .prompts import (JUDGE_RULES, JUDGE_SCHEMA, TRIAGE_SCHEMA, build_system, judge_user_message,
                      ticket_block)

BASE_URL = os.environ.get("ROOSTERLY_BASE_URL", "http://localhost:1234/v1")
API_KEY = os.environ.get("ROOSTERLY_API_KEY", "lm-studio")  # local servers ignore the value
MODEL = os.environ.get("ROOSTERLY_MODEL", "google/gemma-4-e4b")


class LLM:
    def __init__(self, faq_text: str):
        self.client = OpenAI(base_url=BASE_URL, api_key=API_KEY, max_retries=4, timeout=300)
        self.system = build_system(faq_text)
        self.tokens_in = 0
        self.tokens_out = 0

    def check(self):
        """Fail before any ticket is touched if the local server is not running."""
        self.client.models.list()

    def _call(self, system: str, user: str, name: str, schema: dict, max_tokens: int) -> dict:
        r = self.client.chat.completions.create(
            model=MODEL,
            temperature=0,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema",
                             "json_schema": {"name": name, "strict": True, "schema": schema}},
        )
        if r.usage:
            self.tokens_in += r.usage.prompt_tokens
            self.tokens_out += r.usage.completion_tokens
        choice = r.choices[0]
        if choice.finish_reason == "length":
            raise RuntimeError("model output truncated (max_tokens)")
        return json.loads(choice.message.content)

    def triage(self, ticket: dict) -> dict:
        return self._call(self.system, ticket_block(ticket), "triage", TRIAGE_SCHEMA, 4000)

    def judge(self, ticket: dict, faq_excerpt: str, draft: str) -> dict:
        user = judge_user_message(ticket, faq_excerpt, draft)
        return self._call(JUDGE_RULES, user, "judge", JUDGE_SCHEMA, 2000)

    def cost_usd(self) -> float:
        return 0.0  # local model: no per-token charge

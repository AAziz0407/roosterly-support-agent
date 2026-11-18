"""Claude Code version of the triage model layer.

The model is called through the Claude Agent SDK, which runs the same Claude Code setup a
user gets in a terminal: this folder's CLAUDE.md, .claude/skills and .claude/commands.
The safety gates are NOT re-implemented here: roosterly/policy.py and roosterly/decide.py
from the sibling project decide what is sent, so the only thing that differs from the API
version is the model layer.

Model: claude-haiku-5-5 (Haiku 5.5). Tools: only Skill, so the ticket cannot trigger a shell or file access.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "claude_api"))  # roosterly/ package with policy and decide

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query  # noqa: E402

from roosterly.policy import guess_language, load_faq, redact  # noqa: E402

MODEL = os.environ.get("CC_MODEL", "claude-haiku-5-5")  # e.g. CC_MODEL=claude-sonnet-5-5
# Triage contract plus the help centre (the single FAQ file, claude_api/data/faq.md). The judge uses the default prompt.
SYSTEM_PROMPT = ((HERE / "system.md").read_text(encoding="utf-8")
                 + "\n\n## Help centre\n\n" + load_faq()[0])

TRIAGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["language", "category", "priority", "reason", "action", "faq_ids",
                 "fully_answered_by_faq", "critical_topic", "confidence",
                 "draft_reply", "reply_english_gloss", "handoff_note"],
    "properties": {
        "language": {"type": "string", "enum": ["nl", "en", "de"]},
        "category": {"type": "string", "enum": ["bug", "billing", "feature_request", "question", "other"]},
        "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
        "reason": {"type": "string"},
        "action": {"type": "string", "enum": ["reply", "handoff", "close"]},
        "faq_ids": {"type": "array", "items": {"type": "string"}},
        "fully_answered_by_faq": {"type": "boolean"},
        "critical_topic": {"type": "boolean"},
        "confidence": {"type": "number"},
        "draft_reply": {"type": "string"},
        "reply_english_gloss": {"type": "string"},
        "handoff_note": {"type": "string"},
    },
}

JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["supported", "answers_question", "issues"],
    "properties": {
        "supported": {"type": "boolean"},
        "answers_question": {"type": "boolean"},
        "issues": {"type": "string"},
    },
}


def ticket_block(ticket: dict) -> str:
    def clean(s):  # redact payment data, and stop the text from closing our delimiter
        return redact(str(s or "")).replace("</ticket>", "[/ticket]")
    text = f"{ticket.get('subject') or ''} {ticket.get('body') or ''}"
    return (
        "<ticket>\n"
        f"id: {clean(ticket.get('id'))}\n"
        f"text language (detected by code): {guess_language(text) or 'unknown'}\n"
        f"received: {clean(ticket.get('received_at'))}\n"
        f"channel: {clean(ticket.get('channel'))}\n"
        f"plan: {clean(ticket.get('customer_plan'))}\n"
        f"subject: {clean(ticket.get('subject'))}\n"
        f"body:\n{clean(ticket.get('body'))}\n"
        "</ticket>"
    )


class ClaudeCodeLLM:
    """Same two methods decide() uses in the API version: triage() and judge()."""

    def __init__(self):
        self.tokens_in = 0
        self.tokens_out = 0
        self.cost_usd = 0.0

    def _run(self, prompt: str, schema: dict, system: str | None = None) -> dict:
        return asyncio.run(self._run_async(prompt, schema, system))

    async def _run_async(self, prompt: str, schema: dict, system: str | None) -> dict:
        opts = ClaudeAgentOptions(
            model=MODEL,
            cwd=str(HERE),                     # loads CLAUDE.md, .claude/skills, .claude/commands
            skills="all",                      # enables the Skill tool and the project skills
            tools=["Skill"],                   # nothing else: no shell, no file access
            allowed_tools=["Skill"],
            system_prompt=system,              # None keeps the SDK default (used by the judge)
            output_format={"type": "json_schema", "schema": schema},
            max_turns=8,
        )
        result = None
        async for msg in query(prompt=prompt, options=opts):
            if isinstance(msg, ResultMessage):
                result = msg
        if result is None or result.is_error:
            raise RuntimeError(f"claude call failed: {getattr(result, 'result', None)}")
        for u in (result.model_usage or {}).values():  # TypedDict: camelCase keys
            self.tokens_in += u.get("inputTokens", 0) or 0
            self.tokens_out += u.get("outputTokens", 0) or 0
        self.cost_usd += result.total_cost_usd or 0.0
        if result.structured_output is None:
            raise RuntimeError("no structured output")
        return result.structured_output

    def triage(self, ticket: dict) -> dict:
        return self._run("/triage\n" + ticket_block(ticket), TRIAGE_SCHEMA, system=SYSTEM_PROMPT)

    def judge(self, ticket: dict, faq_excerpt: str, draft: str) -> dict:
        prompt = ("/judge\nHELP-CENTRE EXCERPT:\n" + faq_excerpt + "\n\n" + ticket_block(ticket)
                  + "\n\nDRAFT REPLY:\n<draft>\n" + draft.replace("</draft>", "") + "\n</draft>")
        return self._run(prompt, JUDGE_SCHEMA)

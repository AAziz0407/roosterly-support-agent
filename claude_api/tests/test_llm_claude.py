import json

import pytest

from roosterly import models, prompts
from roosterly.decide import decide
from roosterly.llm_claude import MODEL, ClaudeLLM
from roosterly.policy import load_faq

FAQ_TEXT, FAQ = load_faq()
TICKET = {"id": "T1", "received_at": "2026-10-05T09:00:00+00:00", "channel": "email",
          "customer_plan": "Basis", "subject": "Vraag", "body": "Hoe voeg ik een medewerker toe?"}
TRIAGE = {"language": "nl", "category": "question", "priority": "P4", "reason": "How-to, F02.",
          "action": "handoff", "faq_ids": [], "fully_answered_by_faq": False, "critical_topic": False,
          "confidence": 0.9, "draft_reply": "", "reply_english_gloss": "",
          "handoff_note": "Customer wants: x. Key facts: y. Next step: z."}


class Block:
    def __init__(self, type, text=""):
        self.type, self.text = type, text


class Usage:
    def __init__(self, i=100, o=50, w=0, r=0):
        self.input_tokens, self.output_tokens = i, o
        self.cache_creation_input_tokens, self.cache_read_input_tokens = w, r


class Resp:
    def __init__(self, payload=None, stop_reason="end_turn", usage=None, blocks=None):
        self.content = blocks if blocks is not None else [Block("thinking"), Block("text", json.dumps(payload))]
        self.stop_reason, self.usage, self.stop_details = stop_reason, usage or Usage(), None


class FakeClient:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []
        self.messages = self
        self.models = self

    def create(self, **kw):
        self.calls.append(kw)
        return self.responses.pop(0)

    def retrieve(self, model):
        self.retrieved = model


def test_triage_sends_a_schema_constrained_request_and_parses_the_text_block():
    client = FakeClient(Resp(TRIAGE))
    out = ClaudeLLM(FAQ_TEXT, client=client).triage(TICKET)
    assert out == TRIAGE  # the thinking block before the text block is skipped
    kw = client.calls[0]
    assert kw["model"] == MODEL == "claude-haiku-5-5"
    assert kw["output_config"] == {"format": {"type": "json_schema", "schema": prompts.TRIAGE_SCHEMA}}
    assert "temperature" not in kw and "top_p" not in kw  # Haiku 5.5 rejects non-default sampling
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}  # the long FAQ prompt is cached
    assert FAQ_TEXT in kw["system"][0]["text"]
    assert "<ticket>" in kw["messages"][0]["content"]


def test_judge_uses_the_judge_schema_and_does_not_cache():
    client = FakeClient(Resp({"supported": True, "answers_question": True, "issues": ""}))
    out = ClaudeLLM(FAQ_TEXT, client=client).judge(TICKET, FAQ["F02"], "Hoi, ...")
    assert out["supported"] is True
    kw = client.calls[0]
    assert kw["output_config"]["format"]["schema"] == prompts.JUDGE_SCHEMA
    assert "cache_control" not in kw["system"][0]
    assert "DRAFT REPLY" in kw["messages"][0]["content"]


def test_refusal_and_truncation_raise():
    for reason in ("refusal", "max_tokens"):
        with pytest.raises(RuntimeError):
            ClaudeLLM(FAQ_TEXT, client=FakeClient(Resp(TRIAGE, stop_reason=reason))).triage(TICKET)


def test_a_failed_model_call_becomes_a_safe_handoff():
    llm = ClaudeLLM(FAQ_TEXT, client=FakeClient(Resp(TRIAGE, stop_reason="refusal")))
    decision, _ = decide(TICKET, llm, FAQ)
    assert decision["action"] == "handoff" and decision["confidence"] == 0.0


def test_cost_counts_cache_writes_and_reads():
    llm = ClaudeLLM(FAQ_TEXT, client=FakeClient(Resp(TRIAGE, usage=Usage(i=1000, o=200, w=4000, r=0)),
                                                Resp(TRIAGE, usage=Usage(i=1000, o=200, w=0, r=4000))))
    llm.triage(TICKET)
    llm.triage(TICKET)
    expected = ((1000 + 4000 * 1.25) + (1000 + 4000 * 0.10)) * 0.10 / 1e6 + 400 * 0.50 / 1e6
    assert llm.cost_usd() == pytest.approx(expected)
    assert (llm.tokens_in, llm.tokens_out) == (10000, 400)


def test_check_asks_for_the_model():
    client = FakeClient()
    ClaudeLLM(FAQ_TEXT, client=client).check()
    assert client.retrieved == MODEL


def test_make_llm_stops_before_any_ticket_when_the_backend_is_unusable(monkeypatch):
    def boom(self):
        raise ConnectionError("no server")
    monkeypatch.setattr("roosterly.llm.LLM.check", boom)
    monkeypatch.setattr("roosterly.llm_claude.ClaudeLLM.check", boom)
    for provider in models.PROVIDERS:
        with pytest.raises(SystemExit):
            models.make_llm(provider, FAQ_TEXT)
    with pytest.raises(SystemExit):
        models.make_llm("nope", FAQ_TEXT)

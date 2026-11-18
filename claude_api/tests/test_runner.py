import json

from roosterly import runner
from roosterly.client import AlreadyHandled

TICKET = {"id": "T1", "received_at": "2026-10-05T09:00:00+00:00", "channel": "email",
          "customer_plan": "Basis", "subject": "Vraag", "body": "Hoe voeg ik een medewerker toe?"}


class FakeHelpdesk:
    open_now = []        # tickets the server still lists as open
    acted = []           # (tid, action) calls that reached the server
    already = set()      # tickets the server has already handled (409)

    def __init__(self):
        pass

    def open_tickets(self):
        return list(FakeHelpdesk.open_now)

    def act(self, tid, action, body):
        if tid in FakeHelpdesk.already:
            raise AlreadyHandled(tid)
        FakeHelpdesk.acted.append((tid, action))

    def reset(self):
        pass


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def triage(self, ticket):
        self.calls += 1
        return {"action": "handoff", "confidence": 0.9, "category": "question", "priority": "P4",
                "language": "nl", "reason": "How-to question, no FAQ entry used.", "faq_ids": [],
                "fully_answered_by_faq": False, "critical_topic": False, "draft_reply": "",
                "reply_english_gloss": "", "handoff_note": "Customer wants: a how-to answer. "
                "Key facts: none. Next step: answer from the help centre."}

    def judge(self, *a):
        raise AssertionError("no reply, so no judge call")

    def cost_usd(self):
        return 0.0


def _setup(monkeypatch, tmp_path, open_now, already=()):
    FakeHelpdesk.open_now = open_now
    FakeHelpdesk.acted = []
    FakeHelpdesk.already = set(already)
    monkeypatch.setattr(runner, "Helpdesk", FakeHelpdesk)
    return tmp_path / "state", tmp_path / "logs"


def _lines(logs):
    (log,) = list(logs.glob("run-*.log"))
    return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]


def test_posts_once_then_skips_stale_ledger(monkeypatch, tmp_path):
    state, logs = _setup(monkeypatch, tmp_path, [TICKET])
    llm = FakeLLM()
    runner.run(llm, state, logs)
    assert FakeHelpdesk.acted == [("T1", "handoff")]
    assert json.loads((state / "ledger.json").read_text())["T1"]["status"] == "done"

    # the server still lists T1 as open, but local state says done: skip, do not post again
    runner.run(llm, state, logs)
    assert FakeHelpdesk.acted == [("T1", "handoff")]
    assert _lines(logs)[-1]["status"] == "skipped_stale_ledger"


def test_409_is_recorded_and_never_retried(monkeypatch, tmp_path):
    state, logs = _setup(monkeypatch, tmp_path, [TICKET], already={"T1"})
    res = runner.run(FakeLLM(), state, logs)
    assert FakeHelpdesk.acted == []
    assert _lines(logs)[0]["status"] == "already_handled_409"
    assert "error" not in res["counts"]  # a 409 is a normal outcome, not an error


def test_crash_after_decide_reuses_decision_without_model_call(monkeypatch, tmp_path):
    state, logs = _setup(monkeypatch, tmp_path, [TICKET])
    state.mkdir(parents=True)
    decision = {"language": "nl", "category": "question", "priority": "P4", "action": "handoff",
                "reason": "x", "confidence": 0.9, "handoff_note": "Customer wants: y. Key facts: z. Next step: w."}
    (state / "ledger.json").write_text(json.dumps({"T1": {
        "status": "pending", "action": "handoff", "decision": decision,
        "body": {"language": "nl", "category": "question", "priority": "P4", "reason": "x",
                 "confidence": 0.9, "handoff_note": "Customer wants: y. Key facts: z. Next step: w."}}}))
    llm = FakeLLM()
    runner.run(llm, state, logs)
    assert llm.calls == 0
    assert FakeHelpdesk.acted == [("T1", "handoff")]
    assert _lines(logs)[0]["gates"] == ["resumed_after_crash"]

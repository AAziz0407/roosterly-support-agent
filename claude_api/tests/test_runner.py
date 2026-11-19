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
        "fp": runner.fingerprint(TICKET), "status": "pending", "action": "handoff", "decision": decision,
        "body": {"language": "nl", "category": "question", "priority": "P4", "reason": "x",
                 "confidence": 0.9, "handoff_note": "Customer wants: y. Key facts: z. Next step: w."}}}))
    llm = FakeLLM()
    runner.run(llm, state, logs)
    assert llm.calls == 0
    assert FakeHelpdesk.acted == [("T1", "handoff")]
    assert _lines(logs)[0]["gates"] == ["resumed_after_crash"]


def test_reused_ticket_id_with_different_content_is_decided_fresh(monkeypatch, tmp_path):
    # new tickets that reuse an old id must not be skipped, and a saved decision must not be replayed on them
    state, logs = _setup(monkeypatch, tmp_path, [TICKET])
    llm = FakeLLM()
    runner.run(llm, state, logs)
    other = {**TICKET, "body": "Een heel andere vraag over de planning."}
    FakeHelpdesk.open_now = [other]
    runner.run(llm, state, logs)
    assert llm.calls == 2
    assert FakeHelpdesk.acted == [("T1", "handoff"), ("T1", "handoff")]
    ledger = json.loads((state / "ledger.json").read_text())["T1"]
    assert ledger["fp"] == runner.fingerprint(other) and ledger["status"] == "done"


def _tickets(n):
    return [{**TICKET, "id": f"T{i}"} for i in range(1, n + 1)]


class FlakyLLM(FakeLLM):
    """Raises for the tickets whose id is in `fail`, answers the others."""

    def __init__(self, fail):
        super().__init__()
        self.fail = set(fail)

    def triage(self, ticket):
        if ticket["id"] in self.fail:
            raise ConnectionError("model unreachable")
        return super().triage(ticket)


def test_run_stops_after_three_model_failures_in_a_row(monkeypatch, tmp_path):
    state, logs = _setup(monkeypatch, tmp_path, _tickets(6))
    res = runner.run(FlakyLLM({f"T{i}" for i in range(1, 7)}), state, logs)
    assert res["stopped"] is True
    # option A: the three failed tickets still became safe handoffs, nothing was posted after that
    assert FakeHelpdesk.acted == [("T1", "handoff"), ("T2", "handoff"), ("T3", "handoff")]
    last = _lines(logs)[-1]
    assert last["status"] == "stopped_circuit_open" and last["left_open"] == 3


def test_a_good_ticket_resets_the_failure_count(monkeypatch, tmp_path):
    state, logs = _setup(monkeypatch, tmp_path, _tickets(6))
    res = runner.run(FlakyLLM({"T1", "T2", "T4", "T5"}), state, logs)  # fail, fail, ok, fail, fail, ok
    assert res["stopped"] is False
    assert len(FakeHelpdesk.acted) == 6


def test_stopped_run_resumes_where_it_left_off(monkeypatch, tmp_path):
    state, logs = _setup(monkeypatch, tmp_path, _tickets(5))
    runner.run(FlakyLLM({"T1", "T2", "T3", "T4", "T5"}), state, logs)
    assert len(FakeHelpdesk.acted) == 3
    FakeHelpdesk.open_now = _tickets(5)[3:]  # the server now lists only the two that were not posted
    res = runner.run(FakeLLM(), state, logs)
    assert res["stopped"] is False
    assert [t for t, _ in FakeHelpdesk.acted] == ["T1", "T2", "T3", "T4", "T5"]

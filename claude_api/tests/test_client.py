import pytest

from roosterly import client
from roosterly.client import AlreadyHandled, Helpdesk, HelpdeskError


class Resp:
    def __init__(self, status, body="{}", headers=None):
        self.status_code, self.text, self.headers = status, body, headers or {}
        self.content = body.encode()

    def json(self):
        import json
        return json.loads(self.text)


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls, self.headers = list(responses), 0, {}

    def request(self, method, url, **kw):
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _hd(monkeypatch, responses):
    sleeps = []
    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    hd = Helpdesk(base_url="http://x", api_key="k", email="e@example.com")
    hd.s = FakeSession(responses)
    return hd, sleeps


def test_503_is_retried_then_succeeds(monkeypatch):
    hd, _ = _hd(monkeypatch, [Resp(503), Resp(503), Resp(200, '{"ok": true}')])
    assert hd.request("POST", "/tickets/T1/reply") == {"ok": True}
    assert hd.s.calls == 3 and hd.retries == 2


def test_429_waits_retry_after(monkeypatch):
    hd, sleeps = _hd(monkeypatch, [Resp(429, headers={"Retry-After": "3"}), Resp(200, '{"ok": true}')])
    hd.request("GET", "/status")
    assert any(s >= 3 for s in sleeps) and hd.retries == 1


def test_409_raises_and_is_never_retried(monkeypatch):
    hd, _ = _hd(monkeypatch, [Resp(409, '{"error": "already_handled"}'), Resp(200)])
    with pytest.raises(AlreadyHandled):
        hd.request("POST", "/tickets/T1/reply")
    assert hd.s.calls == 1 and hd.retries == 0


def test_other_4xx_is_not_retried(monkeypatch):
    hd, _ = _hd(monkeypatch, [Resp(422, '{"error": "validation_failed"}'), Resp(200)])
    with pytest.raises(HelpdeskError):
        hd.request("POST", "/tickets/T1/reply")
    assert hd.s.calls == 1


def test_gives_up_after_max_attempts(monkeypatch):
    hd, _ = _hd(monkeypatch, [Resp(503)] * client.MAX_ATTEMPTS)
    with pytest.raises(HelpdeskError):
        hd.request("GET", "/tickets")
    assert hd.s.calls == client.MAX_ATTEMPTS

"""Helpdesk HTTP client: auth, client-side rate limit, retries for 503/429."""
from __future__ import annotations

import os
import random
import threading
import time

import requests

DEFAULT_BASE = "https://nakywgkztvzkihdjnwbc.supabase.co/functions/v1/helpdesk"
MIN_INTERVAL = 0.25  # 4 req/s, safely under the 5 req/s limit
MAX_ATTEMPTS = 8


class AlreadyHandled(Exception):
    """409: the ticket was already handled. Never retried."""


class HelpdeskError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status = status


class Helpdesk:
    def __init__(self, base_url=None, api_key=None, email=None):
        self.base = (base_url or os.environ.get("HELPDESK_URL") or DEFAULT_BASE).rstrip("/")
        key = api_key or os.environ.get("HELPDESK_KEY")
        mail = email or os.environ.get("HELPDESK_EMAIL")
        if not key or not mail:
            raise SystemExit("Set HELPDESK_KEY and HELPDESK_EMAIL (see .env.example)")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {key}", "X-Candidate-Email": mail})
        self._last = 0.0
        self.retries = 0  # 503, 429 and network retries so far; the runner logs the count per ticket
        self._lock = threading.Lock()

    def _throttle(self):
        with self._lock:
            wait = self._last + MIN_INTERVAL - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def request(self, method: str, path: str, **kw):
        for attempt in range(MAX_ATTEMPTS):
            self._throttle()
            try:
                r = self.s.request(method, self.base + path, timeout=20, **kw)
            except requests.RequestException:
                self.retries += 1
                time.sleep(min(2 ** attempt, 10))  # network blip: retry
                continue
            if r.status_code == 429:
                self.retries += 1
                time.sleep(float(r.headers.get("Retry-After", 1)) + 0.1)
                continue
            if r.status_code == 503:
                self.retries += 1
                time.sleep(min(0.5 * 2 ** attempt, 8) + random.random() * 0.3)
                continue
            if r.status_code == 409:
                raise AlreadyHandled(path)
            if r.status_code >= 400:
                raise HelpdeskError(r.status_code, r.text)
            return r.json() if r.content else {}
        raise HelpdeskError(0, f"gave up on {method} {path} after {MAX_ATTEMPTS} attempts")

    # --- endpoints -------------------------------------------------------
    def open_tickets(self) -> list:
        out, cursor = [], None
        while True:
            path = "/tickets?limit=10&status=open" + (f"&cursor={cursor}" if cursor else "")
            page = self.request("GET", path)
            out += page.get("tickets", [])
            cursor = page.get("next_cursor")
            if not cursor:
                return out

    def examples(self) -> list:
        data = self.request("GET", "/examples")
        return data.get("examples", data) if isinstance(data, dict) else data

    def ticket(self, tid: str) -> dict:
        return self.request("GET", f"/tickets/{tid}")

    def act(self, tid: str, action: str, payload: dict):
        return self.request("POST", f"/tickets/{tid}/{action}", json=payload)

    def reset(self):
        return self.request("POST", "/practice/reset")

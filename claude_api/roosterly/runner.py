"""The live run: read open tickets, decide, post once, log once. Shared by both versions.

Only the model object differs between the API version and the Claude Code version. The model
object needs two methods, triage(ticket) and judge(ticket, excerpt, draft), and cost_usd().
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from .client import AlreadyHandled, Helpdesk, HelpdeskError
from .decide import api_payload, decide
from .policy import load_faq, redact


class Ledger:
    """Crash-safe record of what was decided/sent. Written atomically before and after each post."""

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else {}

    def set(self, tid, **fields):
        self.data[tid] = {**self.data.get(tid, {}), **fields}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        os.replace(tmp, self.path)

    def clear(self):
        self.data = {}
        self.path.unlink(missing_ok=True)


def fingerprint(ticket: dict) -> str:
    """Identifies the ticket's content, so a ledger entry is only reused for the same ticket."""
    text = f"{ticket.get('subject') or ''}\n{ticket.get('body') or ''}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _log(fh, **kw):
    fh.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), **kw}, ensure_ascii=False) + "\n")
    fh.flush()


def run(llm, state_dir: Path, logs_dir: Path, reset: bool = False) -> dict:
    """Handle every open ticket once. Returns {'counts': {...}, 'log': path, 'cost_usd': float}."""
    hd = Helpdesk()
    ledger = Ledger(state_dir / "ledger.json")
    if reset:
        hd.reset()
        ledger.clear()
    _, faq_entries = load_faq()

    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"run-{datetime.now():%Y%m%d-%H%M%S}.log"
    counts = {}

    with open(log_path, "a", encoding="utf-8") as fh:
        for t in hd.open_tickets():
            tid = t["id"]
            t0 = time.time()
            retries0 = getattr(hd, "retries", 0)
            fp = fingerprint(t)
            rec = ledger.data.get(tid, {})
            if rec and rec.get("fp") != fp:  # the helpdesk now has a different ticket under this id
                rec = {}
            info = {"ticket": tid}
            try:
                if rec.get("status") == "done":
                    # The server still lists it as open, so local state is stale (a practice reset
                    # was done outside this run). Do not guess; skip and say so.
                    _log(fh, **info, status="skipped_stale_ledger")
                    print(f"WARNING {tid}: ledger says done but the helpdesk lists it as open; skipped. "
                          "Re-run with --reset if the practice tickets were reset.", file=sys.stderr)
                    counts["skipped"] = counts.get("skipped", 0) + 1
                    continue
                if rec.get("status") == "pending":  # crashed between decide and post: reuse the decision
                    action, body, decision = rec["action"], rec["body"], rec["decision"]
                    gates = ["resumed_after_crash"]
                else:
                    decision, gates = decide(t, llm, faq_entries)
                    action, body = api_payload(decision)
                    ledger.data.pop(tid, None)  # drop any entry left from a different ticket
                    ledger.set(tid, fp=fp, status="pending", action=action, body=body, decision=decision)
                try:
                    hd.act(tid, action, body)
                    status = "posted"
                except AlreadyHandled:
                    status = "already_handled_409"
                ledger.set(tid, status="done", result=status)
                counts[action] = counts.get(action, 0) + 1
                _log(fh, **info, status=status, language=decision["language"],
                     category=decision["category"], priority=decision["priority"], action=action,
                     faq_ids=decision.get("faq_ids"), confidence=decision["confidence"],
                     gates=gates, reason=redact(decision["reason"]),
                     # English gloss of a Dutch draft, so a reviewer can check the reply without reading Dutch
                     gloss=redact(decision.get("reply_english_gloss") or "") or None,
                     retries=getattr(hd, "retries", 0) - retries0,
                     ms=int((time.time() - t0) * 1000))
            except (HelpdeskError, Exception) as e:  # one bad ticket must not stop the run
                _log(fh, **info, status="error", error=redact(str(e))[:200])
                counts["error"] = counts.get("error", 0) + 1
    return {"counts": counts, "log": log_path, "cost_usd": llm.cost_usd()}

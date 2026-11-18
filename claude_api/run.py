#!/usr/bin/env python
"""Run the agent once over all open tickets:  python run.py   (add --reset for a clean practice run)."""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from roosterly.client import AlreadyHandled, Helpdesk, HelpdeskError  # noqa: E402
from roosterly.decide import api_payload, decide  # noqa: E402
from roosterly.llm import LLM  # noqa: E402
from roosterly.policy import load_faq, redact  # noqa: E402

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "state" / "ledger.json"


class Ledger:
    """Crash-safe record of what was decided/sent. Written atomically before and after each post."""

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else {}

    def set(self, tid, **fields):
        self.data[tid] = {**self.data.get(tid, {}), **fields}
        self.path.parent.mkdir(exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        os.replace(tmp, self.path)

    def clear(self):
        self.data = {}
        self.path.unlink(missing_ok=True)


def log_line(fh, **kw):
    fh.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), **kw}, ensure_ascii=False) + "\n")
    fh.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="POST /practice/reset first and clear local state")
    args = ap.parse_args()

    hd = Helpdesk()
    ledger = Ledger(LEDGER)
    if args.reset:
        hd.reset()
        ledger.clear()
        print("practice tickets re-opened, local state cleared")

    faq_text, faq_entries = load_faq()
    llm = LLM(faq_text)
    (ROOT / "logs").mkdir(exist_ok=True)
    log_path = ROOT / "logs" / f"run-{datetime.now():%Y%m%d-%H%M%S}.log"
    counts = {}

    with open(log_path, "a", encoding="utf-8") as fh:
        for t in hd.open_tickets():
            tid = t["id"]
            t0 = time.time()
            rec = ledger.data.get(tid, {})
            info = {"ticket": tid}
            try:
                if rec.get("status") == "done":
                    # Server still lists it as open: local state is stale (practice reset
                    # done outside run.py). Do not guess; skip and say so.
                    log_line(fh, **info, status="skipped_stale_ledger")
                    counts["skipped"] = counts.get("skipped", 0) + 1
                    continue
                if rec.get("status") == "pending":  # crashed between decide and post: reuse decision
                    action, body = rec["action"], rec["body"]
                    decision = rec["decision"]
                    gates = ["resumed_after_crash"]
                else:
                    decision, gates = decide(t, llm, faq_entries)
                    action, body = api_payload(decision)
                    ledger.set(tid, status="pending", action=action, body=body, decision=decision)
                try:
                    hd.act(tid, action, body)
                    status = "posted"
                except AlreadyHandled:
                    status = "already_handled_409"
                ledger.set(tid, status="done", result=status)
                counts[action] = counts.get(action, 0) + 1
                log_line(fh, **info, status=status, language=decision["language"],
                         category=decision["category"], priority=decision["priority"], action=action,
                         faq_ids=decision.get("faq_ids"), confidence=decision["confidence"],
                         gates=gates, reason=redact(decision["reason"]),
                         ms=int((time.time() - t0) * 1000))
            except (HelpdeskError, Exception) as e:  # one bad ticket must not stop the run
                log_line(fh, **info, status="error", error=redact(str(e))[:200])
                counts["error"] = counts.get("error", 0) + 1
    print(f"done: {counts}  log: {log_path.relative_to(ROOT)}  model cost: ${llm.cost_usd():.4f}")


if __name__ == "__main__":
    main()

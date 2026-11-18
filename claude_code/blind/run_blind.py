#!/usr/bin/env python
"""Run the Claude Code triage (Haiku 5.5, current skills) on unlabelled tickets. No scoring.

Writes every decision and gate result to blind/results/<tag>.json so a person can check them
against the client's rules without seeing any expected answer.

  python blind/run_blind.py --tickets blind/g15_tickets.json --tag haiku_g15
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # triage.py
sys.path.insert(0, str(HERE.parent.parent / "claude_api"))  # roosterly/

from roosterly.decide import decide  # noqa: E402
from roosterly.policy import load_faq  # noqa: E402
from triage import MODEL, ClaudeCodeLLM  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickets", default=str(HERE / "g15_tickets.json"))
    ap.add_argument("--tag", default="blind")
    args = ap.parse_args()

    tickets = json.loads(Path(args.tickets).read_text(encoding="utf-8"))
    _, faq_entries = load_faq()
    llm = ClaudeCodeLLM()

    rows = []
    for t in tickets:
        try:
            dec, gates = decide(t, llm, faq_entries)
        except Exception as e:  # one bad call must not stop the run
            dec, gates = {"action": "handoff", "reason": f"error {type(e).__name__}"}, [f"error:{e}"]
        rows.append({"ticket": t, "decision": dec, "gates": gates})
        print(f"{t['id']}: {dec.get('action')} | {dec.get('category')} | {dec.get('priority')} | "
              f"{dec.get('language')} | gates={gates}", flush=True)

    out = {"tag": args.tag, "model": MODEL, "when": datetime.now().isoformat(timespec="seconds"),
           "cost_usd": round(llm.cost_usd(), 4), "tokens_in": llm.tokens_in, "tokens_out": llm.tokens_out,
           "rows": rows}
    path = HERE / "results" / f"{args.tag}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"saved {path}  cost_usd={out['cost_usd']}")


if __name__ == "__main__":
    main()

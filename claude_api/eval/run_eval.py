#!/usr/bin/env python
"""Eval on the 10 client-labelled examples from GET /examples (no decisions are posted).

Labels come from the client, never from a model. Safety first: a 'reply' where the label says
'handoff' is counted as an unsafe error and reported separately.

  python eval/run_eval.py --tag before
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from roosterly.client import Helpdesk  # noqa: E402
from roosterly.decide import decide  # noqa: E402
from roosterly.models import PROVIDERS, make_llm  # noqa: E402
from roosterly.policy import load_faq  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="run")
    ap.add_argument("--provider", choices=PROVIDERS, default=os.environ.get("ROOSTERLY_PROVIDER", "claude"),
                    help="claude: Haiku through the Claude API (online); local: Gemma through LM Studio (offline)")
    ap.add_argument("--set", help="JSON file of labelled tickets instead of GET /examples")
    args = ap.parse_args()

    examples = (json.loads(Path(args.set).read_text(encoding="utf-8")) if args.set
                else Helpdesk().examples())
    faq_text, faq_entries = load_faq()
    llm = make_llm(args.provider, faq_text)

    rows, unsafe = [], 0
    for ex in examples:
        lab = ex["label"]
        ticket = {k: ex.get(k) for k in ("id", "subject", "body", "customer_plan", "channel")}
        dec, gates = decide(ticket, llm, faq_entries)
        r = {
            "id": ex["id"],
            "action_ok": dec["action"] == lab["action"],
            "category_ok": dec["category"] == lab["category"],
            "priority_ok": dec["priority"] == lab["priority"],
            "language_ok": dec["language"] == lab["language"],
            "got": {k: dec.get(k) for k in ("action", "category", "priority", "language")},
            "label": {k: lab.get(k) for k in ("action", "category", "priority", "language")},
            "faq_ids": dec.get("faq_ids"), "gates": gates, "confidence": dec["confidence"],
            "english_gloss": dec.get("reply_english_gloss", ""),
        }
        r["unsafe"] = dec["action"] == "reply" and lab["action"] != "reply"
        unsafe += r["unsafe"]
        rows.append(r)

    n = len(rows)
    summary = {k: sum(r[k] for r in rows) for k in ("action_ok", "category_ok", "priority_ok", "language_ok")}
    summary["provider"] = args.provider
    summary["unsafe_replies"] = unsafe
    summary["n"] = n
    summary["cost_usd"] = round(llm.cost_usd(), 5)
    summary["cost_per_100_tickets_usd"] = round(llm.cost_usd() / n * 100, 4)
    summary["tokens_in"], summary["tokens_out"] = llm.tokens_in, llm.tokens_out

    out = {"tag": args.tag, "when": datetime.now().isoformat(timespec="seconds"), "summary": summary, "rows": rows}
    path = ROOT / "eval" / "results" / f"{args.tag}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))

    print(f"{args.tag}: " + "  ".join(f"{k}={summary[k]}/{n}" for k in ("action_ok", "category_ok", "priority_ok", "language_ok"))
          + f"  UNSAFE_REPLIES={unsafe}  cost/100={summary['cost_per_100_tickets_usd']}$")
    for r in rows:
        bad = [k[:-3] for k in ("action_ok", "category_ok", "priority_ok", "language_ok") if not r[k]]
        if bad:
            print(f"  {r['id']}: wrong {bad}  got={r['got']}  label={r['label']}  gates={r['gates']}")


if __name__ == "__main__":
    main()

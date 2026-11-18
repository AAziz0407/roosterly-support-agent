#!/usr/bin/env python
"""Eval of the Claude Code version (Haiku 5.5 via CLAUDE.md, skills and commands).

Same scoring as eval/run_eval.py in the API version, so the two are comparable.

  python eval.py --tag cc_labelled                       # the 10 labelled examples (GET /examples)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "claude_api"))

from roosterly.decide import decide  # noqa: E402
from roosterly.policy import load_faq  # noqa: E402
from triage import MODEL, ClaudeCodeLLM  # noqa: E402


def load_examples(path: str | None):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    from roosterly.client import Helpdesk  # needs HELPDESK_* env vars
    return Helpdesk().examples()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="cc_run")
    ap.add_argument("--set", help="JSON file of labelled tickets instead of GET /examples")
    ap.add_argument("--desc-only", action="store_true",
                    help="send the model only id, subject and body (no plan or channel)")
    args = ap.parse_args()
    fields = ("id", "subject", "body") if args.desc_only else ("id", "subject", "body", "customer_plan", "channel")

    examples = load_examples(args.set)
    _, faq_entries = load_faq()
    llm = ClaudeCodeLLM()

    rows, unsafe = [], 0
    for ex in examples:
        lab = ex["label"]
        ticket = {k: ex.get(k) for k in fields}
        try:
            dec, gates = decide(ticket, llm, faq_entries)
        except Exception as e:  # one bad call must not stop the eval
            dec, gates = {"action": "handoff", "category": "other", "priority": "P3", "language": "nl",
                          "confidence": 0.0, "reason": f"error {type(e).__name__}"}, [f"error:{e}"]
        r = {
            "id": ex["id"],
            "action_ok": dec["action"] == lab["action"],
            "category_ok": dec["category"] == lab["category"],
            "priority_ok": dec["priority"] == lab["priority"],
            "language_ok": dec["language"] == lab["language"],
            "got": {k: dec.get(k) for k in ("action", "category", "priority", "language")},
            "label": {k: lab.get(k) for k in ("action", "category", "priority", "language")},
            "gates": gates, "confidence": dec.get("confidence"),
        }
        r["unsafe"] = dec["action"] == "reply" and lab["action"] != "reply"
        unsafe += r["unsafe"]
        rows.append(r)
        print(f"  {ex['id']} done: {r['got']}", flush=True)

    n = len(rows)
    summary = {k: sum(r[k] for r in rows) for k in ("action_ok", "category_ok", "priority_ok", "language_ok")}
    summary.update(unsafe_replies=unsafe, n=n, cost_usd=round(llm.cost_usd, 4),
                   tokens_in=llm.tokens_in, tokens_out=llm.tokens_out, model=MODEL)
    out = {"tag": args.tag, "when": datetime.now().isoformat(timespec="seconds"), "summary": summary, "rows": rows}
    path = HERE / "results" / f"{args.tag}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))

    print(f"{args.tag}: " + "  ".join(f"{k}={summary[k]}/{n}" for k in ("action_ok", "category_ok", "priority_ok", "language_ok"))
          + f"  UNSAFE_REPLIES={unsafe}  cost_usd={summary['cost_usd']}")
    for r in rows:
        bad = [k[:-3] for k in ("action_ok", "category_ok", "priority_ok", "language_ok") if not r[k]]
        if bad:
            print(f"  {r['id']}: wrong {bad}  got={r['got']}  label={r['label']}  gates={r['gates']}")


if __name__ == "__main__":
    main()

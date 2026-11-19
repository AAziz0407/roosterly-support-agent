#!/usr/bin/env python
"""Run the agent once over all open tickets:  python run.py   (add --reset for a clean practice run)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from roosterly.models import PROVIDERS, make_llm  # noqa: E402
from roosterly.policy import load_faq  # noqa: E402
from roosterly.runner import run  # noqa: E402

ROOT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=PROVIDERS, default=os.environ.get("ROOSTERLY_PROVIDER", "claude"),
                    help="claude: Haiku through the Claude API (online); local: Gemma through LM Studio (offline)")
    ap.add_argument("--reset", action="store_true", help="POST /practice/reset first and clear local state")
    args = ap.parse_args()

    llm = make_llm(args.provider, load_faq()[0])
    res = run(llm, state_dir=ROOT / "state", logs_dir=ROOT / "logs", reset=args.reset)
    if args.reset:
        print("practice tickets re-opened, local state cleared")
    print(f"done: {res['counts']}  log: {res['log'].relative_to(ROOT)}  model cost: ${res['cost_usd']:.4f}")
    if res["stopped"]:
        sys.exit("STOPPED: the model failed on 3 tickets in a row. The rest are still open. "
                 "Fix the backend (key, server, network) and run again; finished tickets are skipped.")


if __name__ == "__main__":
    main()

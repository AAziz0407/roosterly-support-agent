#!/usr/bin/env python
"""Run the Claude Code agent once over all open tickets:  python run.py   (add --reset for a clean practice run).

Same loop, ledger and logs as claude_api/run.py. Only the model layer differs: triage.py calls
Haiku 5.5 through the Claude Agent SDK. Needs HELPDESK_KEY and HELPDESK_EMAIL in the environment.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # triage.py
sys.path.insert(0, str(HERE.parent / "claude_api"))  # roosterly/

from roosterly.runner import run  # noqa: E402
from triage import ClaudeCodeLLM  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="POST /practice/reset first and clear local state")
    args = ap.parse_args()

    llm = ClaudeCodeLLM()
    res = run(llm, state_dir=HERE / "state", logs_dir=HERE / "logs", reset=args.reset)
    if args.reset:
        print("practice tickets re-opened, local state cleared")
    print(f"done: {res['counts']}  log: {res['log'].relative_to(HERE)}  model cost: ${res['cost_usd']:.4f}")


if __name__ == "__main__":
    main()

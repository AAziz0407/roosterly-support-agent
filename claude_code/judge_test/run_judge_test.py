#!/usr/bin/env python
"""Test the judge alone on drafts with known right and wrong answers (no tickets, no decisions).

  python judge_test/run_judge_test.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # triage.py
sys.path.insert(0, str(HERE.parent.parent / "claude_api"))  # roosterly/

from roosterly.policy import load_faq  # noqa: E402
from triage import ClaudeCodeLLM  # noqa: E402


def main():
    _, faq = load_faq()
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    llm = ClaudeCodeLLM()
    agree = 0
    for c in cases:
        excerpt = "\n\n".join(faq[i] for i in c["faq"])
        j = llm.judge(c["ticket"], excerpt, c["draft"])
        ok = (j["supported"] == c["expect_supported"]) and (j["answers_question"] == c["expect_answers"])
        agree += ok
        print(f"{c['id']}: supported={j['supported']} (expect {c['expect_supported']}) "
              f"answers={j['answers_question']} (expect {c['expect_answers']}) {'OK' if ok else 'MISMATCH'}")
        if not ok:
            print(f"    issues: {j['issues']}")
    print(f"agreement {agree}/{len(cases)}  cost_usd={round(llm.cost_usd(), 4)}")


if __name__ == "__main__":
    main()

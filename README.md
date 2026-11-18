# Roosterly support agent

Triages Roosterly support tickets (mostly Dutch) into one decision each: language, category, priority with a reason, and one action: `reply` (a draft in the customer's language), `handoff` (an English note), or `close`.

Two versions are in this repo. The **Claude Code version** (`claude_code/`, Haiku 5.5 through the Claude Agent SDK) is the one under evaluation. It has **no live runner**, so it does not post to the helpdesk. The **API version** (`claude_api/`, Gemma through LM Studio) runs live with a crash-safe ledger and is the fallback. Both use the same safety layer, `claude_api/roosterly/`.

## How to run

Safety tests (no network, no model):

```bash
cd claude_api && python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && pytest -q tests
```

Claude Code version (Python 3.10+; it uses the Claude Code login on this machine, not a key in the repo):

```bash
cd claude_code && python3 -m venv .venv && . .venv/bin/activate && pip install claude-agent-sdk
set -a && . ../.env && set +a          # HELPDESK_KEY, HELPDESK_EMAIL
CC_MODEL=claude-haiku-5-5 python eval.py --tag my_run          # the 10 client examples, scored
CC_MODEL=claude-haiku-5-5 python blind/run_blind.py --tag my_g15   # unlabelled batch, not scored
```

API version (LM Studio on `localhost:1234`):

```bash
cd claude_api
ROOSTERLY_BASE_URL=http://localhost:1234/v1 ROOSTERLY_MODEL=google/gemma-4-e4b python run.py --reset
```

Keys come from the environment or `.env` (see `.env.example`). `.env` is git-ignored, and keys never reach logs. Results go to `claude_code/results/`, `claude_code/blind/results/` and `claude_api/logs/`.

## Decisions

1. **A system prompt and three skills, not hard-coded rules.** `claude_code/system.md` holds the role, the output contract and the always-human list. The help centre (`claude_api/data/faq.md`, the only FAQ file) is appended to it. The skills `priority-triage`, `reply-style` and `handoff-note` hold the rules and examples. The examples are invented, not taken from the client's tickets. The `reason` names the deciding fact (the trigger, the FAQ entry, or the number of blocked users), not the checks the model ran.
2. **Code can only make a decision safer.** The model proposes; `roosterly/policy.py` decides. Refund, cancellation, personal-data, security and legal wording in NL, EN or DE forces a handoff at a minimum priority (P2 for money or contract, P1 for security or legal). A reply is sent only if it cites a valid FAQ entry, the FAQ fully covers the question, confidence is at least 0.80, no number or domain is missing from the FAQ or the ticket, the language check passes, no payment details appear, and a second model call judges the draft supported and answering the question. Close needs 0.90. Any failure becomes a handoff. I chose these thresholds myself: an unnecessary handoff costs a minute, a wrong reply reaches a customer.
3. **Dutch and the ticket.** The model gets the ticket as the helpdesk returns it, marked as data, and the code detects the language and passes it on. Replies are in the customer's language, and handoff notes are always English. Without the code hint, the model drifted to Dutch on English and German tickets.

## Reliability

These apply to the **API version**, which posts live:

- **503:** retried with exponential backoff and jitter, up to 8 attempts. **429:** waits `Retry-After`, and requests are paced at 4 per second. **409:** never retried; the ticket counts as handled.
- **Crash safety:** each decision is written atomically to `state/ledger.json` as `pending` before the POST, and as `done` after it. A restart skips `done` tickets and re-posts `pending` ones without a model call. A crash between the POST and `done` replays one POST, which the server rejects with 409.
- **One bad ticket** is logged and the run continues.

The Claude Code version has none of this, because it has no live runner.

## Eval and fix

Only the client's 10 labelled examples (`GET /examples`) count as labels. I wrote the rules after looking at them, so these scores are regression checks, not accuracy. Sets I labelled myself were discarded.

Claude Code version, client 10, Haiku 5.5:

| Run | Prompt | Action | Category | Priority | Language | Unsafe replies | Cost |
|---|---|---|---|---|---|---|---|
| Before (`v1_client10_regression.json`) | CLAUDE.md and three skills, no system prompt | 9/10 | 10/10 | 10/10 | 10/10 | 0 | $0.075 |
| After (`client10_system_v2_allfields.json`) | system prompt and new skill examples, FAQ in CLAUDE.md | 10/10 | 10/10 | 10/10 | 10/10 | 0 | $0.076 |
| After, FAQ moved to system prompt (`client10_single_faq_allfields.json`) | the current version | 9/10 | 10/10 | 10/10 | 10/10 | 0 | $0.072 |

In the current run, E07 (a billing question, labelled reply) was blocked by the judge and handed off. The judge gave the other run a reply. One ticket moved between runs, so I can't yet tell how much of that is the change and how much is run-to-run variance.

Judge check (8 hand-written cases, `claude_code/judge_test/`): "supported" matched my expectation in 8/8. "Answers the question" differed in 3 cases, where my expectations were too narrow. The reason rule was fixed by reading the outputs, not by a score.

API version, client 10 (earlier prompt, Gemma): action 8/10, category 8/10, priority 8/10, language 10/10, no unsafe replies.

**Cost:** about $0.0075 per ticket on Haiku 5.5, including the judge call, so about **$0.75 per 100 tickets**. The API version has no model charges, since it runs locally.

## What I would improve

- **Label the blind batch, then score it once.** `fair15` has no labels yet, so there is no accuracy number.
- **Build a live runner for the Claude Code version**, with the same ledger and retry rules, and run both versions on the same 30 practice tickets.
- **Run the client-10 eval several times** and report the spread, since one judge decision moved between runs. Test the judge on wrong drafts too.
- **Narrow "customer threatens to leave"** to an explicit cancellation request. Most such messages are complaints, and the current rule sends them to a human.

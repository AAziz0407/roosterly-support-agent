# Roosterly support agent

Triages Roosterly support tickets (mostly Dutch) into one decision each: language, category, priority with a reason, and one action: `reply` (a draft in the customer's language), `handoff` (an English note for the support team), or `close`.

Two versions share one runner and one safety layer (`claude_api/roosterly/`). The **Claude Code version** (`claude_code/`, Haiku 5.5 through the Claude Agent SDK) is the one I submit and it has been run live. The **API version** (`claude_api/`, Gemma through LM Studio) has not been run against the helpdesk yet. A Claude API version needs an Anthropic API key, which I do not have yet.

## How to run

From a fresh clone:

```bash
cp .env.example .env                 # add HELPDESK_KEY (from the email) and HELPDESK_EMAIL
set -a && . ./.env && set +a         # load them into the shell
cd claude_code && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python run.py --reset                # POST /practice/reset, then one run over all open tickets
python eval.py --tag my_run          # the 10 labelled examples, scored
```

The Claude Code version uses the Claude Code login on the machine, so `claude` must be logged in. No model key is stored in the repo. Each run writes one JSON line per ticket to `claude_code/logs/`.

Safety tests (no network, no model): `cd claude_api && pip install -r requirements.txt && pytest -q tests` (13 tests).

## Decisions

1. **The model proposes; code decides.** `roosterly/policy.py` can only make a decision safer. A reply is sent only if it cites a FAQ entry that fully covers the question, confidence is at least 0.80, every number and domain in the draft is in the FAQ or the ticket, the draft passes a language check, no payment details appear, and a second model call (a judge) finds the draft supported and answering the question. Anything else becomes a handoff. Refund, cancellation, personal-data, security and legal wording in NL, EN or DE forces a handoff at P2 or P1. I chose these thresholds myself: a wrong reply reaches a customer, an unnecessary handoff costs a minute.
2. **Dutch.** The model reads the Dutch ticket directly. The language detected by code is passed as a hint, because without it the model drifted to Dutch on English and German tickets. Every reply comes with an English gloss and the FAQ ids it used, and both are in the log. I cannot read Dutch, so I check a reply through the gloss, the FAQ ids, the judge verdict and the deterministic checks. The gloss is the model's own translation, and no Dutch speaker has checked it.
3. **Where the brief was open.** "Unsure" means confidence below 0.80 (handoff); a close needs 0.90. A customer who threatens to leave goes to a human, following the client's rule. That rule may over-escalate (see below).

**AI tools.** I built this with Claude Code. Most of the code and prompts were written with it. I read each change, ran the tests and the live pass myself, and wrote the eval and this README. The labels are the client's; the model under test never wrote labels.

## Reliability

- **503:** retried up to 8 times with exponential backoff and jitter. **429:** waits `Retry-After`; requests are paced at 4 per second. **409:** never retried; recorded as `already_handled_409`.
- **Crash safety:** each decision is written atomically to `state/ledger.json` as `pending` before the POST, and as `done` after it. On restart, `done` tickets are skipped and `pending` tickets post their saved decision with no model call. A crash between the POST and `done` replays one POST, which the server rejects with 409. If the server still lists a ticket as open but the ledger says `done`, the run skips it and logs `skipped_stale_ledger`.
- **One bad ticket** is logged as an error and the run continues.
- **Security:** keys come only from environment variables, and `.env` is git-ignored. Ticket text is data inside `<ticket>` tags. The Claude Code agent has one tool, Skill, so it has no shell or file access. Payment details are redacted from model input, logs and reasons, and a draft that contains them is blocked.
- **Not covered by tests:** the 503 and 429 retry paths and the retry count. Retries are not logged, so I cannot say how many occurred in the final run.

## Eval and fix

Eval: the 10 labelled examples from `GET /examples`, scored by `claude_code/eval.py`. These labels are the only ones used. I wrote the rules after reading them, so the scores are regression checks, not accuracy.

| Version (saved result) | Prompt | Action | Category | Priority | Language | Unsafe | Cost |
|---|---|---|---|---|---|---|---|
| v1 (`v1_client10_regression.json`) | CLAUDE.md and three skills, no system prompt | 10/10 | 10/10 | 10/10 | 10/10 | 0 | $0.075 |
| v2 (`client10_system_v2_allfields.json`) | system prompt and skill examples, FAQ in CLAUDE.md | 10/10 | 10/10 | 10/10 | 10/10 | 0 | $0.076 |
| before the fix (`client10_single_faq_allfields.json`) | FAQ moved into the system prompt | 9/10 | 10/10 | 10/10 | 10/10 | 0 | $0.072 |
| after the fix (`client10_e07_fix_full.json`) | reply-style skill states a count as a condition | 10/10 | 10/10 | 10/10 | 10/10 | 0 | $0.072 |

**What was wrong:** E07, "Wat kost Plus voor 25 medewerkers?" (labelled as a reply). The draft said "25 actieve medewerkers", but the ticket does not say the 25 are active, and F02 bills only active employees. The judge rejected the draft. Before the fix, E07 got a reply in 1 of 5 decisions.

**The fix:** the reply-style skill now states a total for a count that the FAQ bills differently as a condition ("Als alle 25 medewerkers actief zijn, is dat €150 …") and includes that case as an example. No threshold or gate changed. After the fix, E07 got a reply in 5 of 5 decisions, and the 10-example eval scores 10/10 on action.

**Caveats:** the 10-example eval was run once after the fix. The 30-ticket practice pass moved from 10 replies to 7: T001, T029 and T030 became handoffs, and T011 changed from close to handoff. T029 is a how-to that the judge rejected this time but accepted before. I have not measured whether the skill change caused the drop or whether it is judge variance.

**Cost per 100 tickets** (cost ÷ tickets × 100, judge call included): the final 30-ticket run cost $0.1347, so $0.45 per 100. The 10-ticket eval after the fix cost $0.0716, so $0.72 per 100.

**Final run:** reset, then one run over all 30 practice tickets: 7 replies, 22 handoffs, 1 close, 30 posted, 0 errors. Log: `claude_code/logs/run-20261119-011732.log`. The helpdesk shows 30 handled.

## What I would improve

- **A client rule I would change:** "a customer threatening to leave always goes to a human." A complaint is not a cancellation, and the brief itself says that escalating everything saves nobody time. I would narrow it to an explicit cancellation request.
- **Claude API version:** with an Anthropic key, add the Claude API as a third model path in `claude_api/`. It shares the runner, so only the model layer changes. I cannot test it without a key.
- **Dutch check:** a second, independent check on Dutch replies, such as back-translation by a different model, plus a Dutch speaker reviewing a sample.

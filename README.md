# Roosterly support agent

Triages Roosterly support tickets (mostly Dutch) into one decision each: language, category, priority with a reason, and one action: `reply` (a draft in the customer's language), `handoff` (an English note for the team), or `close`.

The **Claude Code version** (`claude_code/`, Haiku 5.5 through the Claude Agent SDK) is the one I submit, and it has been run live. The **API version** (`claude_api/`, Gemma through LM Studio) shares its runner and safety layer, but has not been run against the helpdesk. A Claude API version needs an Anthropic API key, which I do not have yet.

## How to run

Needs Python 3.10 or newer and a logged-in Claude Code install (`claude`). From a fresh clone:

```bash
cp .env.example .env                 # add HELPDESK_KEY (from the email) and HELPDESK_EMAIL
set -a && . ./.env && set +a         # load them into the shell
cd claude_code && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python run.py --reset                # reset the practice tickets, then one run over all 30
python eval.py --tag my_run          # the 10 labelled examples, scored
```

Each run writes one JSON line per ticket to `claude_code/logs/`. No model key is stored in the repo. Safety tests, no network or model: `cd claude_api && pip install -r requirements.txt && pytest -q tests` (13 tests).

## Decisions

1. **The model proposes; code decides.** `roosterly/policy.py` can only make a decision safer. A reply is sent only if it cites a FAQ entry that fully covers the question, confidence is at least 0.80, every number and domain in the draft is in the FAQ or the ticket, the language check passes, no payment details appear, and a second model call (a judge) finds the draft supported. Anything else becomes a handoff. A wrong reply reaches a customer; an unnecessary handoff costs a minute.
2. **Dutch.** The model reads the Dutch ticket directly, with the language detected by code passed as a hint. Without the hint, the model drifted to Dutch on English and German tickets. Every reply carries an English gloss and its FAQ ids in the log. I cannot read Dutch, and no Dutch speaker has checked the glosses.
3. **Assumptions where the brief was open.** "Unsure" means confidence below 0.80; a close needs 0.90. A reply is in the customer's language. A plan or price question gets a reply. A feature wish gets a thank-you and the roadmap pointer. A customer who threatens to leave goes to a human, following the client's rule.

**AI tools.** I researched the approach and settled the architecture myself, and used Claude Code to help build it. I read each change, ran the tests and the live pass myself, and wrote the eval and this README. The labels are the client's; the model under test never wrote them.

## Reliability

- **503:** retried up to 8 times with backoff and jitter. **429:** waits `Retry-After`; requests are paced at 4 per second. **409:** never retried; recorded as `already_handled_409`.
- **Crash safety:** each decision is written to `state/ledger.json` as `pending` before the POST and as `done` after it. On restart, `done` tickets are skipped and `pending` tickets post their saved decision with no model call. A crash between the POST and `done` replays one POST, which the server rejects with 409.
- **One bad ticket** is logged as an error and the run continues.
- **Security:** the key and your email are read only from environment variables, and `.env` and `docs/` are git-ignored. Ticket text is data inside `<ticket>` tags. The Claude Code agent's only tool is Skill, so it has no shell or file access. Payment details are redacted before the model, the logs and any reply.
- **Not tested:** the 503 and 429 retry paths. Retries are not logged, so I cannot count them in the final run.

## Eval and fix

Eval: the 10 labelled examples from `GET /examples`, scored by `claude_code/eval.py`. These are the only labels used. I wrote the rules after reading them, so the scores are regression checks, not accuracy.

| Version (saved result) | Prompt | Action | Category | Priority | Language | Unsafe | Cost |
|---|---|---|---|---|---|---|---|
| before the fix (`client10_single_faq_allfields.json`) | FAQ moved into the system prompt | 9/10 | 10/10 | 10/10 | 10/10 | 0 | $0.072 |
| after the fix (`client10_e07_fix_full.json`) | reply-style skill states a count as a condition | 10/10 | 10/10 | 10/10 | 10/10 | 0 | $0.072 |

**What was wrong:** E07, "Wat kost Plus voor 25 medewerkers?", labelled as a reply. The draft said "25 actieve medewerkers", which the ticket does not say. F02 bills only active employees, so the judge rejected the draft. Before the fix, E07 got a reply in 1 of 5 decisions.

**The fix:** the reply-style skill now states a total for a count that the FAQ bills differently as a condition ("Als alle 25 medewerkers actief zijn, is dat €150 …"). No threshold or gate changed. After the fix, E07 got a reply in 5 of 5 decisions, and the eval scores 10/10 on action.

**Caveats:** the eval was run once after the fix. Judge decisions vary between runs, so one eval run is weak evidence, and the 30-ticket results move by a few tickets between runs.

**Cost per 100 tickets** (cost ÷ tickets × 100, judge included): $0.45 on the 30-ticket final run ($0.1347 ÷ 30 × 100); $0.72 on the 10-ticket eval ($0.0716 ÷ 10 × 100).

**Final run:** reset, then one run over all 30 practice tickets: 7 replies, 22 handoffs, 1 close, 30 posted, 0 errors. Log: `claude_code/logs/run-20261119-011732.log`.

## What I would improve

- **A client rule I would change:** "a customer threatening to leave always goes to a human." A complaint is not a cancellation, and the brief says escalating everything saves nobody time. I would narrow it to an explicit cancellation request.
- **Claude API version:** with an Anthropic key, add the Claude API as a third model path in `claude_api/`. It shares the runner, so only the model layer changes. Until then it has not been run live.
- **Dutch check:** a second, independent check on Dutch replies, such as back-translation by a different model, plus a Dutch speaker reviewing a sample.
- **Typed validation with Pydantic:** the model's JSON is checked against a JSON schema and then by hand in `policy.py`. A Pydantic model for triage and judge output would reject malformed fields in one place, and it would make the helpdesk payload type-checked before it is sent.
- **Tracing and observability:** each ticket is one run of several calls (triage, judge, helpdesk), and the log only shows the outcome. OpenTelemetry spans per ticket would show which call and which gate decided each action, with latency, tokens and cost, so a bad decision can be debugged from its trace.

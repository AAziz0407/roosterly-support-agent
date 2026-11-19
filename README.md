# Roosterly support agent

Triages Roosterly tickets (mostly Dutch) into one decision each: language, category, priority with a reason, and `reply`, `handoff` (English note) or `close`. There are two versions with one runner and one safety layer (`claude_api/roosterly/`). The **Claude Code version** (`claude_code/`, Haiku 5.5 via the Claude Agent SDK) is the one I submit; the final run and the eval below come from it. The **API version** (`claude_api/`) has one model switch: `--provider claude` is Haiku 5.5 through the Claude API (online, needs `ANTHROPIC_API_KEY`), `--provider local` is Gemma through LM Studio (offline). Both use the same prompts, schemas and checks, and a backend that is not reachable stops the run before any ticket is touched.

## How to run

Needs Python 3.10+ and a logged-in Claude Code (`claude`).

```bash
cp .env.example .env                 # add HELPDESK_KEY and HELPDESK_EMAIL
set -a && . ./.env && set +a
cd claude_code && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python run.py --reset                # reset the practice tickets, then one run over all 30
python eval.py --tag my_run          # the 10 labelled examples, scored
```

API version: `cd claude_api && pip install -r requirements.txt && python run.py --provider claude` (or `--provider local`); the eval is `python eval/run_eval.py --provider ...`.

Logs: one JSON line per ticket in `claude_code/logs/`. Tests (no network, no model): `cd claude_api && pip install -r requirements.txt && pytest -q tests`.

## Decisions

1. **The model proposes; code decides.** `roosterly/policy.py` can only make a decision safer. A reply is sent only if it cites a FAQ entry that fully covers the question, confidence is at least 0.80, every number, domain and menu name is in the FAQ or the ticket, the language check passes, no payment details appear, and a second model call (a judge) finds it supported. Otherwise: handoff. A wrong reply reaches a customer; an unnecessary handoff costs a minute.
2. **Dutch.** The model reads Dutch directly, with a code-detected language hint (without it, it drifted to Dutch on English and German tickets). I cannot read Dutch, so checks are string-based: numbers, domains and menu names must appear in the FAQ (this caught "Instellungen" for "Instellingen"), and each reply is logged with an English gloss and FAQ ids. No Dutch speaker has reviewed the glosses.
3. **Assumptions.** "Unsure" is confidence below 0.80; a close needs 0.85. Plan and price questions get a reply; a feature wish gets a thank-you and the roadmap link; a customer threatening to leave goes to a human, per the client's rule.

**AI tools.** I chose the architecture and built it with Claude Code. I read each change, ran the tests and live runs, and wrote the eval and this README. The labels are the client's; the model under test wrote none.

## Reliability

- **503:** up to 8 retries with backoff and jitter. **429:** waits `Retry-After`; calls paced at 4 per second. **409:** never retried. Each log line has a `retries` count (final run: 1). Tested with a fake session, not a forced failure live.
- **Crash safety:** each decision is saved to `state/ledger.json` as `pending` before the POST and `done` after. After a crash, `done` is skipped and `pending` posts its saved decision with no model call. Entries carry a hash of the ticket text, so a reused id never inherits an old decision. A replayed POST gets a 409.
- **Security:** keys come from environment variables; `.env` and `docs/` are git-ignored. Ticket text is data inside `<ticket>` tags, the agent's only tool is Skill (no shell, no files), and payment details are redacted before the model, logs and replies.

## Eval and fix

The 10 labelled examples from `GET /examples` (`claude_code/eval.py`). Reply examples are also checked for the FAQ entry named in the client's label and the reply language.

| Version (saved result) | Action | Category | Priority | Language | Reply FAQ / lang | Unsafe | Cost |
|---|---|---|---|---|---|---|---|
| before (`client10_single_faq_allfields.json`) | 9/10 | 10/10 | 10/10 | 10/10 | not measured | 0 | $0.072 |
| after (`final_eval.json`) | 10/10 | 10/10 | 10/10 | 10/10 | 6/6, 6/6 | 0 | $0.051 |

- **Wrong:** E07, "Wat kost Plus voor 25 medewerkers?" The draft said "25 actieve medewerkers"; the ticket does not say active, and F02 bills only active employees, so the judge rejected it.
- **Fix:** the reply-style skill now states such a total as a condition ("Als alle 25 medewerkers actief zijn, is dat €150 …"). No threshold changed. My first version put the E07 ticket itself in the skill, which is teaching to the test; I replaced it with another ticket and re-ran.
- **Caveat:** after that, action scored 10/10 in 3 of 4 runs and 8/10 in one (judge variance). It is a regression check, not accuracy.
- **Cost per 100 tickets** (cost ÷ tickets × 100): $0.60 on the final run ($0.1806 ÷ 30 × 100), judge included.
- **Final run:** reset, then 30 tickets: 9 replies, 19 handoffs, 2 closes, 0 errors. Log: `claude_code/logs/run-20261119-181536.log`.

## What I would improve

- **Next step:** an independent check on Dutch replies (back-translation by a different model) and a Dutch speaker reviewing a sample. The judge and the gloss come from the same model family as the author.
- **Tracing:** each ticket is several calls (triage, judge, helpdesk) and the log only shows the outcome. OpenTelemetry spans per ticket would show which call and which gate decided each action, with latency, tokens and cost, so a bad decision can be debugged from its trace.
- **A client rule I would change:** "a customer threatening to leave always goes to a human." A complaint is not a cancellation, and escalating everything saves nobody time. I would narrow it to an explicit cancellation request.

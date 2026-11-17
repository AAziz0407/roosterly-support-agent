# Roosterly support agent

Triages Roosterly support tickets (almost all Dutch) into one decision per ticket: language, category, priority with a reason, and one action (`reply` with a draft in the customer's language, `handoff` with an English note, or `close`).

**Status, honestly:** two versions exist in this repo.

- **Claude Code version** (`claude_code_version/`): Haiku 5.5 through the Claude Agent SDK, with `CLAUDE.md`, three skills and two commands. It reuses the same safety layer as the API version. It has been run on the client's 10 labelled examples and on unlabelled test batches. **It has no live runner yet**, so it does not post to the helpdesk.
- **API version** (`roosterly/`, `run.py`): a local `google/gemma-4-e4b` through LM Studio, because I have no Anthropic API key. It runs live with a crash-safe ledger. Its prompt does not yet use the Claude Code skills.

The Claude Code version is the one under evaluation. The API version is the fallback that does post.

## How to run

**Safety-layer tests** (no network, no model):

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest -q tests                                  # 10 tests
```

**Claude Code version** (needs Python 3.10+ for the SDK; it uses the Claude Code login on this machine, not a key in the repo):

```bash
cd claude_code_version
python3 -m venv .venv && . .venv/bin/activate
pip install claude-agent-sdk
CC_MODEL=claude-haiku-5-5 python eval.py --tag my_run                 # the 10 client examples
CC_MODEL=claude-haiku-5-5 python blind/run_blind.py --tickets blind/g15_tickets.json --tag my_g15
```

Results go to `results/` and `blind/results/`. `run_blind.py` prints decisions and saves them without scoring; `eval.py` scores against labels.

**API version** (LM Studio running a chat model on `http://localhost:1234`; keys in `.env`, see `.env.example`):

```bash
ROOSTERLY_BASE_URL=http://localhost:1234/v1 ROOSTERLY_MODEL=google/gemma-4-e4b python eval/run_eval.py --tag before
ROOSTERLY_BASE_URL=http://localhost:1234/v1 ROOSTERLY_MODEL=google/gemma-4-e4b python run.py --reset
```

`run.py` without `--reset` processes only tickets still open. Each run writes one JSON line per ticket to `logs/`. Keys come from the environment or `.env` and are never written to logs.

## Decisions

1. **Skills, not hard-coded rules, in the Claude Code version.** The model gets three skills: `priority-triage` (language, category, priority, action, with three examples per priority and three close examples), `reply-style` (facts, calculations, feature wishes, bugs with a stated fix or limit), and `handoff-note` (the three-part English note). Each is about 100 to 150 lines and written in the helpdesk's own ticket and decision format. The examples are invented, not copied from the client's labelled tickets.
2. **Code can only make a decision safer.** The model proposes; `roosterly/policy.py` decides what is sent. Refund, cancellation, personal-data, security and legal wording in NL/EN/DE forces a handoff with a minimum priority (P2 for money or contract, P1 for security or legal). A reply is sent only if a valid FAQ id is cited, the model says the FAQ fully covers the question, confidence is at least 0.80, no number or domain is ungrounded in the FAQ entry or the ticket, the language check passes, no payment details appear, and a second model call judges the draft supported and answering the question. Close needs confidence 0.90. Any failure defaults to handoff. I chose these thresholds myself: escalating an unsure ticket is cheap, and a wrong reply reaches a customer.
3. **The model sees the ticket as the helpdesk returns it.** `id`, `received_at`, `channel`, `customer_plan`, `subject`, `body`. The ticket is marked as data, not instructions, and payment details are redacted before anything is logged. The language is detected by code and given to the model, because the model otherwise drifted to Dutch on English and German tickets.
4. **Reason is one sentence that names the deciding fact** (the trigger, the FAQ entry used, or the number of users blocked), not a description of the checks the model ran.

**Assumptions where the brief is open:** a 0.80 reply threshold and a 0.90 close threshold; "fully covered" means the FAQ states the answer; handoff is preferred over a guess on any error.

**How AI tools were used:** I worked with an AI as assistant. I described my architecture, then improved it step by step, and arrived at one plan, which this README describes.

## Reliability

These apply to the **API version**, which posts live:

- **503:** retried with exponential backoff and jitter, up to 8 attempts.
- **429:** waits the `Retry-After` value, then retries. Requests are paced at 4 per second.
- **409:** never retried. The ticket is marked already handled and the run continues.
- **Crash safety:** before each POST the decision is written atomically to `state/ledger.json` as `pending`. After a successful POST or a 409 it becomes `done`. On restart, `done` tickets are skipped and `pending` tickets re-post the saved decision without a new model call. A crash between the POST and the `done` write causes one replayed POST, which the server rejects with 409.
- **One bad ticket** is logged as an error and the run continues.
- **Security:** keys from environment variables only; `.env` is git-ignored; logs exclude ticket text and payment details.

The **Claude Code version has none of this yet**, because it has no live runner.

## Eval and fix

Only the 10 client-labelled examples (`GET /examples`) count as labels. I wrote the rules after looking at them, so those scores are not a fair test. I discarded the sets I labelled myself.

**Claude Code version, client 10 (v1 skills, Haiku 5.5):** action 10/10, category 10/10, priority 10/10, language 10/10, unsafe replies 0, cost $0.075. Tuned on these same tickets, so this is a regression check, not an accuracy number.

**Judge check** (8 hand-written cases, `judge_test/`): the judge's "supported" verdict matched my expectation in 8/8 cases. Its "answers the question" verdict differed from mine in 3 cases, where I found my expectations too narrow.

**Unlabelled batches:** `blind/fair15_tickets.json` (F01–F15, labels to be filled in) and `blind/g15_tickets.json` (G01–G15, unlabelled). Both have been run with Haiku 5.5 and saved in `blind/results/`. There is no score yet, because the labels are not in.

**The fix so far:** the `reason` rule. The first blind run gave reasons that described the model's checks ("no always-a-human topic is involved"). I changed the rule in `CLAUDE.md` and the three skills to name the deciding fact. I checked this by reading the outputs, not by a labelled score. The g15 run shows reasons such as "F05 gives €4 per active employee per month, and the 25 employees from the ticket make €100 per month, excl. VAT."

**API version, client 10 (earlier prompt, Gemma):** action 8/10, category 8/10, priority 8/10, language 10/10, unsafe replies 0. The priority fix took this from 5/10 to 8/10 on the same 10 tickets; that is also tuned-on.

**Cost:** Claude Code version about $0.005 to $0.01 per ticket on Haiku 5.5, measured on the batch runs. API version $0.00 in model charges, since the model runs locally.

## What I would improve

- **Label the batches blind, then score.** Until a set is labelled before any change, no accuracy number is fair. The next step is the fair15 labels and then one scored run.
- **Build the live runner for the Claude Code version**, with the same ledger and retry rules as the API version. Then the two versions can be compared on the same 30 practice tickets.
- **Test the judge on wrong drafts**, not only right ones, and fix its answers-question rule where my expectations were too narrow.
- **Clarify one client rule.** "Customers threatening to leave" always go to a human. Many such messages are only complaints. A clearer trigger, such as an explicit cancellation request, would send fewer tickets to handoff without adding risk.

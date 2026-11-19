"""One ticket in, one final decision out (no network writes). Shared by run.py and the eval."""
from __future__ import annotations

from . import policy


TICKET_FIELDS = ("id", "received_at", "channel", "customer_plan", "subject", "body")


def model_input(ticket: dict) -> dict:
    """The ticket as the helpdesk returns it (docs/api_reference.md, 'A ticket')."""
    return {k: ticket.get(k) for k in TICKET_FIELDS}


def decide(ticket: dict, llm, faq_entries: dict):
    """Return (decision, gates). Any model failure degrades to a safe handoff."""
    ticket = model_input(ticket)
    model_failed = False
    try:
        proposal = llm.triage(ticket)
    except Exception as e:  # network, refusal, bad JSON ...
        model_failed = True
        proposal = {"action": "handoff", "confidence": 0.0, "category": "other", "priority": "P3",
                    "language": "nl", "reason": f"Model call failed ({type(e).__name__}).",
                    "handoff_note": "Automatic triage failed; please read the ticket."}
    judge = None
    pre_hits, _ = policy.keyword_gate(ticket.get("subject", ""), ticket.get("body", ""))
    if proposal.get("action") == "reply" and not pre_hits and not proposal.get("critical_topic"):
        ids = [i for i in proposal.get("faq_ids") or [] if i in faq_entries]
        if ids and proposal.get("draft_reply"):
            try:
                judge = llm.judge(ticket, "\n\n".join(faq_entries[i] for i in ids), proposal["draft_reply"])
            except Exception:
                judge = None  # no judge verdict -> reply is blocked by policy.finalize
    decision, gates = policy.finalize(proposal, ticket, faq_entries, judge)
    if model_failed:
        gates.append("model_call_failed")  # the runner counts these to stop a run when the model is down
    decision["faq_ids"] = [i for i in proposal.get("faq_ids") or [] if i in faq_entries]
    decision["reply_english_gloss"] = proposal.get("reply_english_gloss", "") if decision["action"] == "reply" else ""
    return decision, gates


def api_payload(decision: dict):
    """Build the (endpoint, body) for the helpdesk. Only documented fields are sent."""
    body = {k: decision[k] for k in ("language", "category", "priority", "reason")}
    body["confidence"] = round(decision["confidence"], 2)
    action = decision["action"]
    if action == "reply":
        body["draft_reply"] = decision["draft_reply"]
    elif action == "handoff":
        body["handoff_note"] = decision["handoff_note"]
    return action, body

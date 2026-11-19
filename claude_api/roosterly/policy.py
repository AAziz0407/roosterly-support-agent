"""Deterministic safety layer. The LLM proposes; this code can only make a decision safer.

Everything here is checkable without reading Dutch: regexes, id lookups, set comparisons.
"""
from __future__ import annotations

import re
from pathlib import Path

CATEGORIES = {"bug", "billing", "feature_request", "question", "other"}
LANGS = {"nl", "en", "de"}
PRIORITIES = ["P1", "P2", "P3", "P4"]

# Below these the decision is sent to a human. Chosen to be conservative: a wrong reply
# reaches a customer, an unnecessary handoff costs one minute of a human's time.
MIN_CONF_REPLY = 0.80
MIN_CONF_CLOSE = 0.85

# --- FAQ ---------------------------------------------------------------------------
FAQ_PATH = Path(__file__).resolve().parent.parent / "data" / "faq.md"


def load_faq(path: Path = FAQ_PATH):
    """Return (full_text, {F01: entry_text}). The FAQ file is the only knowledge source."""
    text = path.read_text(encoding="utf-8")
    entries = {}
    for m in re.finditer(r"^## (F\d+) · .*?(?=^## |^---$)", text, re.S | re.M):
        entries[m.group(1)] = m.group(0).strip()
    return text, entries


# --- Payment details ---------------------------------------------------------------
IBAN_RE = re.compile(r"\b[A-Za-z]{2}\d{2}(?:[ ]?[A-Za-z0-9]{4}){2,7}(?:[ ]?[A-Za-z0-9]{1,4})?\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def redact(text: str) -> str:
    text = IBAN_RE.sub("[IBAN-REDACTED]", text or "")
    return CARD_RE.sub("[CARD-REDACTED]", text)


def has_payment_details(text: str) -> bool:
    return bool(IBAN_RE.search(text or "") or CARD_RE.search(text or ""))


# --- Topics that always go to a human (client rule), in NL/EN/DE ------------------
# (regex, minimum priority). Security/legal = P1 per the brief; money/contract = P2.
TRIGGERS = [
    (r"terugbetal|restitutie|geld terug|terugkrijgen|terugstorten|refund|rückerstattung|erstattung", "P2"),
    (r"betwist|onterecht|dubbel afgeschreven|afgeschreven|incasso|stornier|chargeback|te veel betaald|dispute", "P2"),
    (r"opzeg|opzegging|beëindig|beeindig|stoppen met (het |ons |mijn |de )?(abonnement|roosterly|jullie|dienst)|annulering van (het |ons |mijn )?(abonnement|contract)|cancell?ation|cancel (my|our|the) (subscription|account|contract)|kündig|contractwijziging|(wijzig|aanpass|verander|beëindig|ontbind|verleng)\w*\W+(\w+\W+){0,3}contract\b|\bcontract\W+(wijzig|aanpass|beëindig|ontbind|verleng)|(change|amend|terminate|end)\W+(\w+\W+){0,3}contract\b|\bovereenkomst\b.{0,20}(opzeg|beëindig|ontbind)", "P2"),
    (r"overstappen|stap over|andere leverancier|weg bij jullie|niet meer gebruiken|switch to|leave you|anbieter wechseln|anderen anbieter", "P2"),
    (r"\bavg\b|gdpr|dsgvo|persoonsgegevens|vergeten worden|gegevens verwijder|verwijder mijn|personal data|inzage", "P2"),
    (r"datalek|data breach|data leak", "P1"),
    (r"gehackt|\bhack(ed|er|ers|ing)?\b|inbreuk|ongeautoriseerd|onbevoegd|phishing|verdachte? (inlog|login|activiteit|e-?mail|mail|aanmelding)|verdenk|verdächtig|suspicious|beveiligingsincident|security incident|unauthori[sz]ed", "P1"),
    (r"advocaat|juridisch|rechtszaak|rechter|aansprakelijk|aangifte|sommatie|ingebrekestelling|dagvaard|autoriteit persoonsgegevens|lawyer|legal action|sue |klacht indienen|anwalt|klage", "P1"),
]
_TRIGGERS = [(re.compile(p, re.I), prio) for p, prio in TRIGGERS]


def keyword_gate(subject: str, body: str):
    """Return (matched_patterns, minimum_priority) or ([], None)."""
    text = f"{subject}\n{body}"
    hits, best = [], None
    for rx, prio in _TRIGGERS:
        m = rx.search(text)
        if m:
            hits.append(m.group(0).strip().lower())
            if best is None or PRIORITIES.index(prio) < PRIORITIES.index(best):
                best = prio
    return hits, best


# --- Reply checks that need no Dutch -----------------------------------------------
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
_DOMAIN_RE = re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:nl|com|io|org)\b", re.I)

_STOP = {
    "nl": {"de", "het", "een", "en", "u", "je", "uw", "jouw", "te", "van", "voor", "met", "op", "kunt", "kun", "naar", "of", "is", "dat", "bij"},
    "en": {"the", "and", "you", "your", "to", "of", "for", "with", "is", "can", "on", "in", "a", "this", "that"},
    "de": {"der", "die", "das", "und", "sie", "ihr", "ihre", "zu", "von", "für", "mit", "ist", "können", "auf", "den", "ein"},
}


def guess_language(text: str):
    """nl/en/de from stopword counts, or None when the text is too short to tell."""
    words = re.findall(r"[a-zäöüß]+", text.lower())
    score = {k: sum(w in v for w in words) for k, v in _STOP.items()}
    best = max(score, key=score.get)
    return best if score[best] >= 2 and sum(s == score[best] for s in score.values()) == 1 else None


def language_looks_right(draft: str, lang: str) -> bool:
    words = re.findall(r"[a-zäöüß]+", draft.lower())
    if not words:
        return False
    score = {k: sum(w in v for w in words) for k, v in _STOP.items()}
    return score[lang] >= 3 and score[lang] >= max(score.values())


# --- Menu names: checkable without Dutch -------------------------------------------
_CHAIN_RE = re.compile(r"(\S+)((?:\s*→\s*[^→\n()\[\].,;:]+)+)")
_QUOTE_RE = re.compile(r"[\"“„]([^\"“”„]{2,60})[\"”“]")


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _menu_terms(text: str) -> list:
    """Menu names written as 'Team → Medewerker toevoegen': the word before the first arrow and each segment after."""
    terms = []
    for m in _CHAIN_RE.finditer(text):
        terms.append(_norm(m.group(1).strip(".,;:()\"“”'")))
        terms += [_norm(seg) for seg in m.group(2).split("→") if seg.strip()]
    return terms


def unknown_menu_names(draft: str, faq_entries: list):
    """Menu paths and quoted button names in the draft that the cited FAQ entries do not contain.

    A mistyped Dutch menu name (for example 'Instellungen' for 'Instellingen') is caught by string comparison.
    The last segment of a path may run on into prose, so a segment counts as known when it starts with a FAQ one.
    """
    source = "\n".join(faq_entries)
    known = set(_menu_terms(source))
    flat = _norm(source)
    bad = [t for t in _menu_terms(draft) if not any(t == k or t.startswith(k + " ") for k in known)]
    bad += [q for q in _QUOTE_RE.findall(draft) if _norm(q) not in flat]
    return bad


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def ungrounded_tokens(draft: str, faq_entries: list, ticket_text: str = ""):
    """Numbers / domains in the draft that are not in the FAQ entries or the ticket.

    A number is also allowed when it is the product of two numbers that are in the FAQ or the ticket
    (for example 25 employees x €6 = 150), so a calculation the customer can check is not blocked.
    """
    source = "\n".join(faq_entries)
    allowed_nums = set(_NUM_RE.findall(source)) | set(_NUM_RE.findall(ticket_text))
    base = {_num(n) for n in allowed_nums}
    products = {round(a * b, 4) for a in base for b in base}
    allowed_dom = {d.lower() for d in _DOMAIN_RE.findall(source)}
    bad = [n for n in _NUM_RE.findall(draft)
           if n not in allowed_nums and round(_num(n), 4) not in products]
    bad += [d for d in _DOMAIN_RE.findall(draft) if d.lower() not in allowed_dom]
    return bad


# --- Final gatekeeper --------------------------------------------------------------
def _at_least(prio: str, floor: str) -> str:
    return prio if PRIORITIES.index(prio) <= PRIORITIES.index(floor) else floor


def finalize(d: dict, ticket: dict, faq_entries: dict, judge: dict | None):
    """Validate/override the LLM proposal. Returns (decision, gates_fired)."""
    gates = []
    out = dict(d)
    out["category"] = out.get("category") if out.get("category") in CATEGORIES else "other"
    out["priority"] = out.get("priority") if out.get("priority") in PRIORITIES else "P3"
    out["language"] = out.get("language") if out.get("language") in LANGS else "nl"
    conf = float(out.get("confidence") or 0)
    out["confidence"] = max(0.0, min(1.0, conf))

    hits, floor = keyword_gate(ticket.get("subject", ""), ticket.get("body", ""))
    if hits:
        gates.append("keyword:" + "|".join(hits))
        out["action"] = "handoff"
        out["priority"] = _at_least(out["priority"], floor)
    if out.get("critical_topic"):
        gates.append("llm_critical")
        out["action"] = "handoff"
        out["priority"] = _at_least(out["priority"], "P2")

    action = out.get("action")
    if action == "reply":
        ids = [i for i in out.get("faq_ids") or [] if i in faq_entries]
        draft = (out.get("draft_reply") or "").strip()
        problems = []
        if not ids:
            problems.append("no_valid_faq_id")
        if not out.get("fully_answered_by_faq"):
            problems.append("not_fully_covered")
        if not draft:
            problems.append("empty_draft")
        if out["confidence"] < MIN_CONF_REPLY:
            problems.append("low_confidence")
        if draft and has_payment_details(draft):
            problems.append("payment_details_in_draft")
        if draft and not language_looks_right(draft, out["language"]):
            problems.append("language_mismatch")
        if draft and ids:
            bad = ungrounded_tokens(draft, [faq_entries[i] for i in ids], ticket.get("body", ""))
            if bad:
                problems.append("ungrounded:" + ",".join(bad[:5]))
        if draft and ids:
            bad_menu = unknown_menu_names(draft, [faq_entries[i] for i in ids])
            if bad_menu:
                problems.append("unknown_menu:" + ",".join(bad_menu[:3]))
        if judge is None or not (judge.get("supported") and judge.get("answers_question")):
            issues = " ".join(((judge or {}).get("issues") or "").split())[:120]
            problems.append("judge_rejected" + (f" ({issues})" if issues else ""))
        if problems:
            gates.append("reply_blocked:" + ";".join(problems))
            out["action"] = "handoff"
    elif action == "close":
        if out["confidence"] < MIN_CONF_CLOSE:
            gates.append("close_blocked:low_confidence")
            out["action"] = "handoff"
    elif action != "handoff":
        gates.append("invalid_action")
        out["action"] = "handoff"

    if out["action"] == "handoff":
        note = redact((out.get("handoff_note") or "").strip())
        if not note:  # a blocked reply has no note from the model: say what it was about and why it stopped
            why = out.get("reason") or "the ticket"
            note = (f"Customer wants: {why} Key facts: an automatic reply was blocked by a check. "
                    "Next step: read the ticket and answer it or confirm the help-centre fact first.")
        if gates:
            note += "  [Agent flags: " + " / ".join(gates) + "]"
        out["handoff_note"] = note
        out.pop("draft_reply", None)
    elif out["action"] == "reply":
        out["draft_reply"] = out["draft_reply"].strip()
    out["reason"] = redact((out.get("reason") or "").strip()) or "No reason given."
    return out, gates

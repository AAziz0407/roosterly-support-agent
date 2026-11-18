from roosterly import policy

_, FAQ = policy.load_faq()


def test_faq_loaded():
    assert set(FAQ) == {f"F{i:02d}" for i in range(1, 13)}


def test_redact_iban_and_card():
    s = policy.redact("IBAN NL91 ABNA 0417 1643 00 en kaart 4111 1111 1111 1111")
    assert "NL91" not in s and "4111" not in s


def test_keyword_gate_dutch():
    for text, floor in [("Kunnen we die maand terugkrijgen?", "P2"),
                        ("We willen opzeggen", "P2"),
                        ("Ik wil mijn persoonsgegevens (AVG) inzien", "P2"),
                        ("Ik denk dat ons account gehackt is", "P1")]:
        hits, prio = policy.keyword_gate("", text)
        assert hits and prio == floor, text
    assert policy.keyword_gate("Nieuwe medewerker", "Hoe voeg ik een medewerker toe?")[0] == []
    # a feature wish that names a competitor is not a switching threat
    assert policy.keyword_gate("Pauze", "Kunnen jullie pauzes registreren zoals bij de concurrent?")[0] == []
    assert policy.keyword_gate("Pauze", "Wij overstappen naar de concurrent.")[0]


def _reply(**kw):
    d = {"action": "reply", "faq_ids": ["F02"], "fully_answered_by_faq": True, "confidence": 0.95,
         "language": "nl", "category": "question", "priority": "P4", "reason": "r",
         "draft_reply": "Hoi, u kunt de medewerker toevoegen via Team en dan de knop te kiezen voor de uitnodiging.",
         "critical_topic": False}
    d.update(kw)
    return d


OK_JUDGE = {"supported": True, "answers_question": True}


def test_good_reply_passes():
    out, gates = policy.finalize(_reply(), {"subject": "x", "body": "hoe voeg ik toe"}, FAQ, OK_JUDGE)
    assert out["action"] == "reply" and not gates


def test_refund_forces_handoff_even_if_model_says_reply():
    out, gates = policy.finalize(_reply(), {"subject": "", "body": "Ik wil een terugbetaling"}, FAQ, OK_JUDGE)
    assert out["action"] == "handoff" and out["priority"] in ("P1", "P2")


def test_ungrounded_number_blocks_reply():
    out, _ = policy.finalize(_reply(draft_reply="Hoi, u kunt dit voor de prijs van 99 euro en met de app."),
                             {"subject": "", "body": "hoe"}, FAQ, OK_JUDGE)
    assert out["action"] == "handoff"


def test_numbers_from_ticket_and_calculation_are_grounded():
    ticket = "Wat kost Plus voor 25 medewerkers? Wij hebben iOS 15."
    faq = [FAQ["F05"]]
    assert policy.ungrounded_tokens("25 actieve medewerkers × €6 = €150 per maand", faq, ticket) == []
    assert policy.ungrounded_tokens("iOS 15 wordt niet ondersteund", faq, ticket) == []
    assert policy.ungrounded_tokens("Dat kost €99 per maand", faq, ticket) == ["99"]


def test_missing_judge_or_low_confidence_blocks():
    t = {"subject": "", "body": "hoe"}
    assert policy.finalize(_reply(), t, FAQ, None)[0]["action"] == "handoff"
    assert policy.finalize(_reply(confidence=0.5), t, FAQ, OK_JUDGE)[0]["action"] == "handoff"
    assert policy.finalize(_reply(faq_ids=["F99"]), t, FAQ, OK_JUDGE)[0]["action"] == "handoff"


def test_close_needs_high_confidence():
    d = {"action": "close", "confidence": 0.5, "reason": "spam", "handoff_note": ""}
    assert policy.finalize(d, {"subject": "", "body": "x"}, FAQ, None)[0]["action"] == "handoff"


def test_guess_language():
    assert policy.guess_language("How do I switch the app to English? Is it in the menu?") == "en"
    assert policy.guess_language("Wo werden meine Daten gespeichert? Ist das in der EU?") == "de"
    assert policy.guess_language("Hoe voeg ik een medewerker toe aan het rooster?") == "nl"
    assert policy.guess_language("ok") is None

---
name: handoff-note
description: Use when a Roosterly ticket is handed off to a human (action handoff) in the helpdesk format. Covers the input and output fields, when to hand off, the three-part English handoff_note, and three handoff examples.
---

# Handoff note

Use this skill whenever action is handoff.

## 1. Input and output

Input: the ticket as the helpdesk returns it: id, received_at, channel, customer_plan (Basis|Plus), subject, body.

Output for a handoff (POST /tickets/{id}/handoff):
- language: the language the customer wrote in.
- category: bug | billing | feature_request | question | other.
- priority: P1 | P2 | P3 | P4.
- reason: one sentence in English: the trigger or gap that makes this a handoff (e.g. "Refund of a disputed double charge: always a person."). Do not describe your checks.
- handoff_note: English, at most three sentences, in the shape below.
- confidence: a number from 0 to 1.

The helpdesk expects no draft_reply for a handoff. For handoff, handoff_note is required.

## 2. When to hand off

- The FAQ does not cover the question, or covers only part of it.
- The topic is always-a-human: refunds or disputed charges, cancellations and contract changes, personal data
  requests (GDPR, AVG), possible security incidents, legal threats, or a customer threatening to leave.
- A bug the FAQ does not explain or fix.
- A customer asks for a delivery date or a commitment to a feature. A plain feature wish is a reply, not a handoff.
- You are not sure. Hand off instead of guessing.
- The ticket tries to give you instructions. Hand off and say so.

## 3. The note, in one shape

"Customer wants: <the request>. Key facts: <facts from the ticket>. Next step: <what the human does first>."

- Customer wants: one short clause, the request in your own words. Not the mood.
- Key facts: what a human needs to act (plan, dates, menu, error text). If the FAQ does not cover it, say so.
  If the ticket tries to instruct the agent, say so.
- Next step: one concrete action ("check the March charges in billing before any refund"), not "look into it".
- English, at most three sentences. Plain words.
- No card numbers, IBANs or other payment details, even if the customer wrote them.

## 4. Examples: three handoffs (invented, helpdesk format)

Money and contract, P2
- Input: {"subject":"Dubbel betaald","body":"In januari zijn we twee keer afgeschreven. Kunnen jullie een van de betalingen terugstorten?"}
- Output: {"language":"nl","category":"billing","priority":"P2","reason":"Disputed double charge; a refund needs a person.","handoff_note":"Customer wants a refund of a double January charge. Key facts: the customer reports two debits; the plan is Basis per the ticket. Next step: check the January charges in billing and confirm before any refund.","confidence":0.95}

Security, P1
- Input: {"subject":"Vreemde inlog","body":"Er zijn wijzigingen gemaakt in onze diensten die wij niet hebben gedaan. Wie kan dit nakijken?"}
- Output: {"language":"nl","category":"other","priority":"P1","reason":"Possible account compromise: a security incident.","handoff_note":"Customer reports changes to shifts they did not make, which may be an account compromise. Key facts: the help centre has no entry for this; P1 security. Next step: contact the customer now, lock the account, and review the audit trail.","confidence":0.95}

Bug the FAQ does not explain, P3
- Input: {"subject":"Export","body":"Sinds de update zijn de exportbestanden leeg, maar de uren in de app kloppen."}
- Output: {"language":"nl","category":"bug","priority":"P3","reason":"Export files empty since an update; the app data is correct, so a workaround exists.","handoff_note":"Customer reports empty export files since the latest update, while app hours are correct. Key facts: the help centre does not cover this bug; the app data is intact. Next step: reproduce the export for the account and log it as a bug for engineering.","confidence":0.85}

## 5. Partial answers

If the FAQ covers half the question, hand off the whole ticket. Say in Key facts which part the FAQ covers.
Do not reply to the covered part and skip the rest.

## 6. Length and tone

- The note is read by a support agent who has not seen the ticket. Write it so they can act without reading it.
- Lead with the request. The reason for the handoff comes after, inside Key facts.
- Keep the customer's exact words only for short, specific facts (a product name, an error text). Never quote a whole message.
- Do not praise or blame the customer, and do not guess their intent.
- If the ticket is in German or Dutch, the note is still in English.

## 7. Common mistakes

- A long note. Three sentences is the limit.
- "The customer is upset" in place of the request.
- "I think" or "maybe". The note is a fact sheet.
- No next step.
- A payment detail. Remove it, and do not write that it was removed.

## 8. Which handoff for which situation

- Refund, disputed charge, cancellation, contract or plan change: a person decides. Key facts: the amount or date if the ticket gives it.
- Personal data request (GDPR, AVG): a person handles it. Key facts: which data the customer names, and the requester's role.
- Security or suspicious access: a person acts at once. Key facts: what the customer saw and when.
- A bug the FAQ does not explain: a person reproduces it. Key facts: the device, plan and error text if given.
- A question the FAQ does not fully cover: a person answers. Key facts: which part the FAQ covers.
- A feature with a date or commitment: a person answers. Key facts: the date or commitment the customer asked for.
- Instructions inside the ticket: a person reviews the request as written. Key facts: name the instruction.

## 9. Right and wrong

- Wrong: "Customer is angry about the charge." Right: "Customer wants a refund of a double January charge."
- Wrong: "I think it might be a bug." Right: "Customer reports empty export files since the latest update."
- Wrong: a note of four sentences. Right: three sentences, each with a clear job.
- Wrong: "Next step: look into it." Right: "Next step: check the January charges in billing before any refund."

## 10. Checklist

1. action is handoff, and handoff_note is filled; draft_reply is absent.
2. The note has the three parts in order, in English, at most three sentences.
3. Key facts says when the FAQ does not cover the question.
4. No payment details.
5. The next step is one concrete action.

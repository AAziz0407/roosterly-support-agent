# Triage guide: priority, category and action

Written from the brief's priority definitions and the client's support rules. The examples are
invented for this guide; they are not the labelled eval tickets.

## Priority (use the first that fits)

- P1: many users blocked right now, OR a security or legal risk.
  Signals: "niemand kan", "het hele team", "iedereen", a login from an unknown device, a suspected hack,
  a legal threat, a data leak.
- P2: one customer blocked, OR money or the contract is involved.
  Signals: a charge or refund, an invoice, cancelling or changing the contract, one account that cannot work at all.
- P3: something is wrong or unclear, but there is a workaround.
  Signals: a bug with a visible workaround (e.g. works in the browser but not the app), something unclear
  that the customer has not been able to resolve by reading the help centre.
- P4: no urgency. How-to questions, ideas, feature wishes, cosmetic issues.
  A how-to question that the help centre answers is P4 even when the steps are many.

## Category

- bug: something works wrongly. billing: payments, invoices, refunds, plans.
- feature_request: an idea or wish. question: how-to or information.
- other: none of the above, including spam and empty tickets.

## Action

- reply: the help centre fully answers the question and nothing critical is involved.
- handoff: anything the help centre does not fully cover, anything critical (see the client's rules),
  or any doubt. Feature requests are handed off, because the help centre cannot promise them.
- close: spam, or an empty or meaningless ticket with no request. Only with high confidence.

## Reply examples (invented, one per language)

The examples use the outage entry (F11), which no held-out ticket uses.

- Dutch ticket: "Is er nu een storing?" -> "Hoi, de actuele storingen en geplande onderhoudsmomenten vindt u op status.roosterly.nl. Team Roosterly"
  (gloss: "Hi, current outages and planned maintenance are on status.roosterly.nl. Team Roosterly")
- English ticket: "Is there an outage right now?" -> "Hi, you can find current outages and planned maintenance at status.roosterly.nl. Team Roosterly"
- German ticket: "Gibt es gerade eine Störung?" -> "Hallo, aktuelle Störungen und geplante Wartungen finden Sie auf status.roosterly.nl. Team Roosterly"

A reply is always in the ticket's language, never in Dutch by default.

## Examples (invented)

1. "Niemand in ons team kan vanochtend inloggen, we staan stil." -> bug, P1, handoff.
2. "Er staat een inlog in ons account van een apparaat dat wij niet kennen." -> other, P1, handoff (security).
3. "Mijn betaling is vandaag twee keer afgeschreven." -> billing, P2, handoff (money).
4. "Wij willen het contract per volgende maand opzeggen." -> billing, P2, handoff (cancellation).
5. "De app toont het rooster niet op mijn telefoon, in de browser werkt het wel." -> bug, P3, handoff (workaround exists).
6. "Hoe voeg ik een nieuwe medewerker toe?" with a help-centre answer -> question, P4, reply.
7. "Zouden jullie een donkere modus kunnen toevoegen?" -> feature_request, P4, handoff.
8. "asdf" with no request -> other, P4, close.

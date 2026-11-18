---
name: reply-style
description: Use when writing a reply (draft_reply) to a Roosterly customer in the helpdesk format. Covers the input and output fields, reply language, the facts and calculations the judge checks, feature wishes, bugs with a stated fix, and three reply examples in Dutch, English and German.
---

# Reply style

Write a reply only when the help centre (the FAQ at the end of the system prompt) answers what the customer asked, or when the
ticket is a feature wish that the reply can acknowledge with the roadmap pointer. A second model call checks
each draft against the cited FAQ entry, and code checks numbers and language.

## 1. Input and output

Input: the ticket as the helpdesk returns it: id, received_at, channel, customer_plan (Basis|Plus), subject, body.

Output for a reply (POST /tickets/{id}/reply):
- language: the language the customer wrote in.
- category: bug | billing | feature_request | question | other.
- priority: P1 | P2 | P3 | P4.
- reason: one sentence in English: the fact the reply rests on, with its help-centre entry (e.g. "F05 gives the unit price; the count is in the ticket"). Do not describe your checks.
- draft_reply: the answer, in the customer's language.
- confidence: a number from 0 to 1.

The helpdesk expects no handoff_note for a reply. Also return faq_ids (the FAQ entries you used) and
reply_english_gloss (an English translation) for the code's checks.

## 2. Language

- draft_reply is in the SAME language as the ticket. Dutch -> Dutch, English -> English, German -> German.
  Never answer a non-Dutch ticket in Dutch.
- reply_english_gloss is always English.
- Greeting and sign-off follow the language: "Hoi" / "Hi" / "Hallo"; "Team Roosterly" in all three.
- Keep menu names exactly as the help centre writes them, with the English meaning in brackets.

## 3. Facts

- Use ONLY facts stated in the cited FAQ entries. No invented prices, dates, links, features or promises.
- Use customer_plan when the answer depends on the plan. If the plan that applies is not the customer's,
  say what the other plan includes, in one sentence, or hand off. Do not guess a plan.
- If the answer depends on a setting or condition in the FAQ, say it: "on by default, can be turned off under <menu>".
- Never repeat payment details, even if the customer sends them.

## 4. Calculations

A calculation is allowed when the unit price is in the FAQ, the count comes from the ticket, and the draft
shows the formula and the unit:
"<unit price> per <unit>, excl. btw. Voor <count> <unit> is dat <total> per <period>, excl. btw."

Do not calculate when the count is not in the ticket, or when the FAQ does not state the assumption.

When the ticket gives a count of people but the FAQ bills a narrower group (for example active employees, F02),
do not call the count active. State the total as a condition, with the same words the ticket uses:
"Als alle <count> <people> actief zijn, is dat <total> per <period>, excl. btw." Then say what is billed (F02).
This is not a guess: the reply states its own assumption. Example in 7c.

## 5. Answer the question

- The first sentence answers what the customer asked.
- A plan limit, a price or a feature availability is a fact: give it and where to find it. It is not a contract change.
- If the FAQ does not say whether something specific happens, do not guess. Point to where it can be checked.
  That is a complete reply.
- One topic per reply. If the ticket asks two things and the FAQ covers only one, hand off.

## 6. Feature wishes and bugs

- A feature wish is a short reply: thank the customer, say the idea is logged, point to the roadmap in the FAQ
  (roadmap.roosterly.nl). Do not promise a date or that it will be built.
- A bug is a reply only when the FAQ states the fix or the limit (for example a minimum OS version).
  Otherwise hand off.

## 7. Examples: three replies (invented, helpdesk format)

Dutch, how-to answered by F03
- Input: {"subject":"Dienst ruilen","body":"Hoe kan een collega een dienst van mij overnemen?"}
- Output: {"language":"nl","category":"question","priority":"P4","reason":"How-to, fully answered by F03.","draft_reply":"Hoi, open de dienst in de app en tik op \"Ruil aanbieden\". Collega's met dezelfde functie kunnen de ruil accepteren. De manager keurt de ruil goed onder Rooster → Verzoeken. Team Roosterly","reply_english_gloss":"Hi, open the shift in the app and tap \"Offer swap\". Colleagues with the same role can accept it. The manager approves it under Rota → Requests. Team Roosterly","faq_ids":["F03"],"confidence":0.93}

English, price calculation from F05 with the count from the ticket
- Input: {"subject":"Price","body":"What would Plus cost for 12 active employees?"}
- Output: {"language":"en","category":"billing","priority":"P4","reason":"Price question, answered by F05 with the count from the ticket.","draft_reply":"Hi, Plus costs €6 per active employee per month, excl. VAT. For 12 active employees that is €72 per month, excl. VAT. Team Roosterly","reply_english_gloss":"Hi, Plus costs €6 per active employee per month, excl. VAT. For 12 active employees that is €72 per month, excl. VAT. Team Roosterly","faq_ids":["F05"],"confidence":0.92}

German, outage question answered by F11
- Input: {"subject":"Störung","body":"Gibt es gerade eine Störung bei Ihnen?"}
- Output: {"language":"de","category":"question","priority":"P4","reason":"Outage question, answered by F11.","draft_reply":"Hallo, aktuelle Störungen und geplante Wartungen finden Sie auf status.roosterly.nl. Team Roosterly","reply_english_gloss":"Hello, current outages and planned maintenance are on status.roosterly.nl. Team Roosterly","faq_ids":["F11"],"confidence":0.9}

## 7a. Examples: bug with a fix or limit the FAQ states (three, invented)

- Input: {"subject":"Oude telefoon","body":"Mijn telefoon heeft Android 8 en de app opent niet meer."}
  Output: {"language":"nl","category":"bug","priority":"P3","reason":"Device below the Android minimum in F12.","draft_reply":"Hoi, de app werkt op Android 10 of later en op iOS 16 of later. Met Android 8 wordt de app niet ondersteund. Team Roosterly","reply_english_gloss":"Hi, the app works on Android 10 or later and iOS 16 or later. Android 8 is not supported. Team Roosterly","faq_ids":["F12"],"confidence":0.93}
- Input: {"subject":"Inklokken","body":"Clocking in with location does not work for our staff."}
  Output: {"language":"en","category":"bug","priority":"P3","reason":"Location clock-in needs location permission, stated in F12.","draft_reply":"Hi, clocking in with location needs location permission for the Roosterly app. Please check that permission in your phone's settings. Team Roosterly","reply_english_gloss":"Hi, clocking in with location needs location permission for the Roosterly app. Please check that permission in your phone's settings. Team Roosterly","faq_ids":["F12"],"confidence":0.88}
- Input: {"subject":"Startet nicht","body":"Die App startet bei mir nicht, ich habe ein älteres Gerät."}
  Output: {"language":"de","category":"bug","priority":"P3","reason":"Device age may be below the minimum, F12 states it; the device is not named.","draft_reply":"Hallo, die App benötigt Android 10 oder neuer bzw. iOS 16 oder neuer. Bitte prüfen Sie die Version Ihres Geräts. Team Roosterly","reply_english_gloss":"Hello, the app needs Android 10 or newer, or iOS 16 or newer. Please check your device version. Team Roosterly","faq_ids":["F12"],"confidence":0.8}

## 7b. Examples: feature wish (three, invented)

- Input: {"subject":"Excel","body":"Zouden jullie een export naar Excel kunnen toevoegen?"}
  Output: {"language":"nl","category":"feature_request","priority":"P4","reason":"Feature wish; logged, roadmap pointer, no promise.","draft_reply":"Hoi, dank voor uw idee. We hebben het genoteerd. U kunt het bekijken en er op stemmen op roadmap.roosterly.nl. Team Roosterly","reply_english_gloss":"Hi, thanks for the idea. We have logged it. You can view it and vote on roadmap.roosterly.nl. Team Roosterly","faq_ids":["F10"],"confidence":0.9}
- Input: {"subject":"Dark mode","body":"A dark mode for the planner would be great."}
  Output: {"language":"en","category":"feature_request","priority":"P4","reason":"Feature wish; acknowledged with roadmap pointer.","draft_reply":"Hi, thanks for the idea. We have logged it. You can follow and vote for it on roadmap.roosterly.nl. Team Roosterly","reply_english_gloss":"Hi, thanks for the idea. We have logged it. You can follow and vote for it on roadmap.roosterly.nl. Team Roosterly","faq_ids":["F10"],"confidence":0.9}
- Input: {"subject":"Wunsch","body":"Ich wünsche mir eine Wochenansicht pro Team."}
  Output: {"language":"de","category":"feature_request","priority":"P4","reason":"Feature wish; logged, roadmap pointer.","draft_reply":"Hallo, vielen Dank für Ihren Vorschlag. Wir haben ihn notiert. Sie können ihn auf roadmap.roosterly.nl ansehen und dafür stimmen. Team Roosterly","reply_english_gloss":"Hello, thank you for the suggestion. We have noted it. You can view it and vote for it on roadmap.roosterly.nl. Team Roosterly","faq_ids":["F10"],"confidence":0.9}

## 7c. Examples: calculation and plan limit (two, invented)

- Input: {"subject":"Prijs","body":"Wat kost Basis voor 14 actieve medewerkers?"}
  Output: {"language":"nl","category":"billing","priority":"P4","reason":"Price question: F05 gives the unit price, the count is in the ticket.","draft_reply":"Hoi, Basis kost €4 per actieve medewerker per maand, excl. btw. Voor 14 actieve medewerkers is dat €56 per maand, excl. btw. Team Roosterly","reply_english_gloss":"Hi, Basis costs €4 per active employee per month, excl. VAT. For 14 active employees that is €56 per month, excl. VAT. Team Roosterly","faq_ids":["F05"],"fully_answered_by_faq":true,"confidence":0.92}
- Input: {"subject":"Prijs Plus","body":"Wat kost Plus voor 25 medewerkers?"}
  Output: {"language":"nl","category":"billing","priority":"P4","reason":"Price question: F05 gives the unit price; the ticket count is employees, and F02 bills only active ones, so the total is stated as a condition.","draft_reply":"Hoi, Plus kost €6 per actieve medewerker per maand, excl. btw. Als alle 25 medewerkers actief zijn, is dat €150 per maand, excl. btw. U betaalt alleen voor actieve medewerkers. Team Roosterly","reply_english_gloss":"Hi, Plus costs €6 per active employee per month, excl. VAT. If all 25 employees are active, that is €150 per month, excl. VAT. You only pay for active employees. Team Roosterly","faq_ids":["F05","F02"],"fully_answered_by_faq":true,"confidence":0.88}
- Input: {"subject":"API","body":"Kunnen we de API van Roosterly gebruiken met ons Basis-abonnement?"}
  Output: {"language":"nl","category":"question","priority":"P4","reason":"Plan question: F05 lists API access under Plus.","draft_reply":"Hoi, API-toegang hoort bij het Plus-abonnement. Op Basis is die niet inbegrepen. De abonnementen vindt u onder Instellingen → Abonnement. Team Roosterly","reply_english_gloss":"Hi, API access is part of the Plus plan. It is not included on Basis. You can see the plans under Settings → Subscription. Team Roosterly","faq_ids":["F05"],"fully_answered_by_faq":true,"confidence":0.9}

## 8. Right and wrong

- Wrong: a total for a count the ticket does not give ("Voor 30 medewerkers is dat €120"). Right: no total; the unit price only.
- Wrong: a made-up print or export button. Right: hand off when the FAQ does not cover it.
- Wrong: "We zetten het voor u klaar" (a promise). Right: state the FAQ fact only.

## 9. What the judge rejects

- a number, price or limit that is neither in the cited entry nor a formula from stated numbers;
- a calculation without its unit, or a count the ticket did not give;
- a menu, button or link the entry does not contain;
- a promised date, fix or feature;
- an answer to a different question;
- a claim about the customer's account, plan or staff that the ticket did not state.

When in doubt, shorten the draft to the one fact the entry states, or hand off.

## 10. Checklist before returning a reply

1. language matches the ticket;
2. every number, price, menu name and link is in the cited entry, or is a formula with its unit;
3. no guesses about the plan, the count or the device;
4. no promised dates, fixes or features;
5. the first sentence answers the question;
6. faq_ids lists the entries used, and fully_answered_by_faq is true only if the whole question is covered;
7. if any box fails, the action becomes handoff.

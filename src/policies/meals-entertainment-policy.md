# Meals & Entertainment Expense Policy

**Applies to:** meals, team lunches and dinners, coffee runs, catering, and client
or business entertainment.

_Owner: Finance Operations. Routine meals are easy to auto-approve, but client
entertainment carries extra scrutiny (business purpose, attendees), so it always
gets a human look._

Work the rules in order, **top to bottom; the first rule that matches decides the
outcome**. Every request is routed to exactly one queue.

## 1. Completeness

If you cannot determine an amount, or the request is too vague to price, it cannot
be auto-processed.

- **Decision:** `flag` → `expense-flagged` (needs clarification).

## 2. Client & business entertainment

Any client entertainment, hosted event, or meal with external guests requires review
so the business purpose and attendee list can be attached — regardless of amount.

- **Decision:** `route` → `expense-review`.

## 3. Currency

Evaluate amounts in **US dollars (USD)**. If the amount is in any other currency, do
**not** guess an exchange rate.

- **Decision:** `route` → `expense-review` for FX verification.

## 4. Amount thresholds (USD)

For routine internal meals (no external guests) with a clear USD amount:

| Amount (USD)             | Decision  | Queue              |
| ------------------------ | --------- | ------------------ |
| $150 or less             | `approve` | `expense-approved` |
| Over $150, up to $1,000  | `route`   | `expense-review`   |
| Over $1,000              | `flag`    | `expense-flagged`  |

Boundary values follow the table exactly: **$150 is `approve`**, **$1,000 is
`route`**.

## Notes for the reviewer

- Rules 1–3 are the judgment layer and may override the amount thresholds, but only
  for the reasons stated above.
- The `reason` on each decision should name the amount or setting (routine vs.
  client entertainment) and the rule from **this meals policy** that applied.

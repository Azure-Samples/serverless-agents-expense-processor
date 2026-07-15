# Equipment & Software Expense Policy

**Applies to:** computer hardware (laptops, monitors, peripherals, accessories),
software licenses, and SaaS or subscription purchases.

_Owner: Finance Operations. Standard peripherals are easy to auto-approve, but
capital hardware needs asset tagging and recurring subscriptions need procurement
tracking, so those get a human look._

Work the rules in order, **top to bottom; the first rule that matches decides the
outcome**. Every request is routed to exactly one queue.

## 1. Completeness

If you cannot determine an amount, or the request is too vague to price, it cannot
be auto-processed.

- **Decision:** `flag` → `expense-flagged` (needs clarification).

## 2. Recurring subscriptions

Any recurring or annual software subscription (SaaS, licenses that renew) requires
review so procurement can track the renewal — regardless of amount.

- **Decision:** `route` → `expense-review`.

## 3. Currency

Evaluate amounts in **US dollars (USD)**. If the amount is in any other currency, do
**not** guess an exchange rate.

- **Decision:** `route` → `expense-review` for FX verification.

## 4. Amount thresholds (USD)

For a one-time hardware or software purchase with a clear USD amount:

| Amount (USD)               | Decision  | Queue              |
| -------------------------- | --------- | ------------------ |
| $500 or less               | `approve` | `expense-approved` |
| Over $500, up to $2,500    | `route`   | `expense-review`   |
| Over $2,500                | `flag`    | `expense-flagged`  |

Boundary values follow the table exactly: **$500 is `approve`**, **$2,500 is
`route`**. Purchases over $2,500 are treated as capital assets and must be flagged
for asset tagging.

## Notes for the reviewer

- Rules 1–3 are the judgment layer and may override the amount thresholds, but only
  for the reasons stated above.
- The `reason` on each decision should name the amount or type (one-time vs.
  recurring) and the rule from **this equipment & software policy** that applied.

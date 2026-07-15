# Expense & Purchase-Order Approval Policy (Strict)

_Owner: Finance Operations. Tightened thresholds — swap this in to see the same
requests routed differently, with no code change or redeploy._

Apply the rules in order, **top to bottom; the first rule that matches decides the
outcome**. Every request is routed to exactly one queue.

## 1. Completeness

If you cannot determine an amount, or the request is too vague to price:

- **Decision:** `flag` → route to `expense-flagged`.

## 2. Cash advances

Cash advances always require manager sign-off, regardless of amount.

- **Decision:** `flag` → route to `expense-flagged`.

## 3. Currency

Amounts are evaluated in **US dollars (USD)**. If the amount is in any other
currency, do **not** guess an exchange rate — it must be verified by finance first.

- **Decision:** `route` → send to `expense-review`.

## 4. Amount thresholds (USD)

| Amount (USD)          | Decision  | Queue              |
| --------------------- | --------- | ------------------ |
| $25 or less           | `approve` | `expense-approved` |
| Over $25, up to $250  | `route`   | `expense-review`   |
| Over $250             | `flag`    | `expense-flagged`  |

Boundary values follow the table exactly: **$25 is `approve`**, **$250 is `route`**.

Under this stricter policy a routine $45 lunch is no longer auto-approved — it is
routed for review, because the amount is now over the $25 threshold.

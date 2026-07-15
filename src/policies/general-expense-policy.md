# General Expense & Purchase-Order Policy

**Applies to:** any expense that no more specific policy covers — miscellaneous
purchases, office supplies, professional services, memberships, and anything the
category-specific policies (travel, meals & entertainment, equipment & software)
do not clearly own.

_Owner: Finance Operations. This is the default, catch-all policy. Update it to
change how uncategorized requests are routed — no code change or redeploy is
required._

Work the rules in order, **top to bottom; the first rule that matches decides the
outcome**. Every request is routed to exactly one queue.

## 1. Completeness

If you cannot determine an amount from the request, or it is too vague to price, it
cannot be auto-processed.

- **Decision:** `flag` → `expense-flagged` (needs clarification).

## 2. Cash advances

Cash advances always require manager sign-off, regardless of amount.

- **Decision:** `flag` → `expense-flagged`.

## 3. Currency

Amounts are evaluated in **US dollars (USD)**. If the amount is in any other
currency, do **not** guess an exchange rate — it must be verified by finance first.

- **Decision:** `route` → `expense-review` for FX verification.

## 4. Amount thresholds (USD)

For an ordinary USD request with a clear amount, the dollar amount alone decides:

| Amount (USD)             | Decision  | Queue              |
| ------------------------ | --------- | ------------------ |
| $100 or less             | `approve` | `expense-approved` |
| Over $100, up to $1,000  | `route`   | `expense-review`   |
| Over $1,000              | `flag`    | `expense-flagged`  |

Boundary values follow the table exactly: **$100 is `approve`**, **$1,000 is
`route`**.

## Notes for the reviewer

- Rules 1–3 are the judgment layer and may override the amount thresholds, but only
  for the reasons stated above. Do not invent other reasons to change an outcome.
- The `reason` on each decision should name the amount or category **and** the rule
  from this policy that applied.

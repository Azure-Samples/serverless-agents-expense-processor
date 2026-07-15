# Travel & Transportation Expense Policy (Strict)

**Applies to:** air travel, rail, lodging and hotels, ground transportation,
ride-share and taxis, car rental, and mileage reimbursement.

_Owner: Finance Operations. Tightened travel policy for a cost-control period —
drop this in over `travel-policy.md` to see the same trip route differently while
every other category is unaffected._

Work the rules in order, **top to bottom; the first rule that matches decides the
outcome**. Every request is routed to exactly one queue.

## 1. Completeness

If you cannot determine an amount, or the request is too vague to price, it cannot
be auto-processed.

- **Decision:** `flag` → `expense-flagged` (needs clarification).

## 2. Cash advances

Travel cash advances require manager sign-off, regardless of amount.

- **Decision:** `flag` → `expense-flagged`.

## 3. Premium travel

First-class or business-class airfare, suites, and other premium upgrades always
need review, regardless of amount.

- **Decision:** `route` → `expense-review`.

## 4. Currency

Evaluate amounts in **US dollars (USD)**; if the amount is in any other currency, do
**not** guess an exchange rate.

- **Decision:** `route` → `expense-review` for FX verification.

## 5. Amount thresholds (USD)

During the cost-control period the auto-approve ceiling is lowered sharply:

| Amount (USD)             | Decision  | Queue              |
| ------------------------ | --------- | ------------------ |
| $250 or less             | `approve` | `expense-approved` |
| Over $250, up to $2,500  | `route`   | `expense-review`   |
| Over $2,500              | `flag`    | `expense-flagged`  |

Boundary values follow the table exactly: **$250 is `approve`**, **$2,500 is
`route`**.

## Notes for the reviewer

- Rules 1–4 are the judgment layer and may override the amount thresholds, but only
  for the reasons stated above.
- The `reason` on each decision should name the amount and the rule from **this
  travel policy** that applied.

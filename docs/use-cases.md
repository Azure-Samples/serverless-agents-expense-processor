# Use cases

Two things prove the agent is genuinely reasoning rather than matching a fixed schema: the **same
amount** decided differently by category, and **swapping one policy document** rerouting only that
category with no code change and no redeploy.

## The same $450, three different policies

Because every policy sets its **own** thresholds, the category the agent picks changes the outcome.
Here's the **same $450 request** run through each category:

| $450 request | Category → policy | Auto-approve ≤ | Decision |
|---|---|---|---|
| Round-trip flight to Denver | travel → `travel-policy.md` | $1,000 | **`approve`** |
| 4K monitor from Dell | equipment → `equipment-software-policy.md` | $500 | **`approve`** |
| Client dinner at Nobu | meals → `meals-entertainment-policy.md` | $150 (client entertainment always reviews) | **`review`** |
| Uncategorized purchase | fallback → `general-expense-policy.md` | $100 | **`review`** |

Same dollar amount, four documents, different outcomes. They are driven by *which policy the agent selects*,
not by logic compiled into the prompt. These three arrive automatically after `azd up` (the
[demo-send hook](deploy.md#auto-seeding-and-the-demo-send)); locally, send them yourself:

```bash
uv run scripts/send_expense.py --file samples/travel.txt          # $450 flight  -> approve  (travel)
uv run scripts/send_expense.py --file samples/equipment.txt       # $450 monitor -> approve  (equipment)
uv run scripts/send_expense.py --file samples/client-dinner.txt   # $450 dinner  -> review   (meals)
uv run scripts/read_decision.py --queue all --peek                # read all three decisions
```

## A worked example

Send this raw text to the input queue:

> Booked a $450 round-trip flight to Denver for the customer onsite next week. (Priya)

The agent extracts the details, selects the travel policy, applies it, and produces:

```json
{ "expenseId": "EXP-3F8A1C", "vendor": "United Airlines", "category": "travel", "amount": 450.0, "currency": "USD", "policyApplied": "travel-policy.md", "decision": "approve", "routedTo": "expense-approved", "reason": "Travel expense of 450 USD is at or below the travel policy's 1,000 auto-approve threshold." }
```

…and puts it on the `expense-approved` queue. Each decision carries a `policyApplied` field naming
the document the agent selected.

## Any format in, the right decision out

The agent extracts the details whatever the shape of the message: free text, an email snippet,
`key: value` lines, or JSON. It then applies the matching policy's judgment rules on top of the amount:

```bash
uv run scripts/send_expense.py "lunch with the team ran about $45"          # -> approve (meals)
uv run scripts/send_expense.py --file samples/cash-advance.txt              # -> flag    (cash advance)
uv run scripts/send_expense.py --file samples/foreign-currency.txt          # -> route   (480 EUR, FX review)
uv run scripts/send_expense.py --file samples/missing-amount.txt            # -> flag    (no clear amount)
uv run scripts/send_expense.py --amount 45                                  # quick way to prove the amount drives it
```

A `$50 cash advance` is **flagged**, `480 EUR` is **routed** for FX review (the agent won't guess a
rate), and a message with no number is **flagged** for clarification. All come from the same agent,
driven by what it selects and reads.

## Swap one policy, reroute one category

The most telling part of the demo: replace a **single** category's policy document and only that
category reroutes. The bundled [`samples/strict-travel-policy.md`](../samples/strict-travel-policy.md)
drops travel auto-approve from $1,000 to **$250**, so the **$450 flight flips from `approve` to
`review`**, while the $450 monitor and the $450 client dinner are **completely unaffected**. The
rules live in the documents, and the agent applies whichever one it selects.

→ Step-by-step commands for the swap are in [customize.md](customize.md#swap-a-single-policy).

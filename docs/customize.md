# Customize

The rules live in the policy documents in [`src/policies/`](../src/policies/), not in code. Because
the agent fetches the chosen policy on **every** run, replacing a document changes how the matching
requests are routed with **no code change and no redeploy**. Swapping a single category's policy
reroutes only that category.

The [`scripts/set_policy.py`](../scripts/set_policy.py) helper lists, shows, seeds, and replaces the
documents. It targets local Azurite by default; add `--cloud` to target the deployed storage account
over Entra ID (your identity needs **Storage Blob Data Contributor**, which `azd` grants the deployer).

## See what's in effect

```bash
uv run scripts/set_policy.py --list --cloud            # names + what each policy covers
uv run scripts/set_policy.py --show travel-policy.md --cloud   # print one policy's full text
```

## Edit a policy in place

Edit any file under `src/policies/`, then push just that document:

```bash
uv run scripts/set_policy.py --file src/policies/travel-policy.md --cloud
```

Send a **new** request afterward. Policies are read per request, so messages already processed keep
their original decision.

## Swap a single policy

Replace one category's document with a different one and watch only that category reroute. The bundled
`samples/strict-travel-policy.md` drops travel auto-approve to $250:

```bash
# Baseline: the $450 flight auto-approves under the shipped travel policy
uv run scripts/send_expense.py --file samples/travel.txt --cloud
uv run scripts/read_decision.py --queue expense-approved --peek --cloud

# Tighten ONLY travel: swap the travel document, leave meals/equipment/general alone
uv run scripts/set_policy.py --file samples/strict-travel-policy.md --name travel-policy.md --cloud

# Same $450 flight is now routed for review; the $450 monitor still auto-approves
uv run scripts/send_expense.py --file samples/travel.txt    --cloud
uv run scripts/send_expense.py --file samples/equipment.txt --cloud
uv run scripts/read_decision.py --queue all --peek --cloud

# Restore the shipped travel policy (or re-seed the whole library) when you're done
uv run scripts/set_policy.py --file src/policies/travel-policy.md --cloud
uv run scripts/set_policy.py --seed --cloud
```

## Add a new policy category

1. Create `src/policies/<your-category>-policy.md`. Start it with an `**Applies to:**` line. That's
   what the `list_expense_policies` tool surfaces as the policy's scope, and how the agent knows when
   to pick it. Use the bundled documents as a template for the threshold table.
2. Upload it: `uv run scripts/set_policy.py --file src/policies/<your-category>-policy.md --cloud`.
3. Send a request in that category. The agent lists the policies, sees the new scope, selects it, and
   applies it. No prompt edit, no redeploy.

The agent picks by scope, so a well-written `**Applies to:**` line is all it needs to route a brand-new
category correctly.

## Tune the agent itself

The agent's instructions are the markdown body of
[`src/agents/expense_processor.agent.md`](../src/agents/expense_processor.agent.md); the model and reasoning effort
are set in [`src/local.settings.json.sample`](../src/local.settings.json.sample) (local) and the
Function App settings (cloud). Redeploy with `azd deploy` after changing the agent definition.

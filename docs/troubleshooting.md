# Troubleshooting

## Output queues stay empty

Check the function logs / Application Insights for the agent run and any `route_expense_decision`
error. Confirm the app deployed and that the managed identity has **Storage Queue Data Contributor**
on the storage account (RBAC can take a few minutes to propagate after deploy). Tail the live trace
with `azd monitor --logs`.

## `403` from the scripts against the account

Your identity is missing **Storage Queue Data Contributor** (send/read) or **Storage Blob Data
Contributor** (policies) on the account. `azd` grants both to the deployer, but role propagation can
take a few minutes. Wait and retry.

## Policy changes don't seem to take effect

Confirm what's in effect with `uv run scripts/set_policy.py --list --cloud`, then send a **new**
request. Policies are read per request, so messages already processed keep their original decision.
Remember the agent selects by category: swapping `travel-policy.md` only affects travel requests.

## `DeploymentNotFound` / model errors

The Foundry model deployment isn't ready or the app settings don't point at it. Check the `azd`
outputs and the Function App configuration.

## The demo send didn't run

The `postup` hook only sends when the output queues are empty (so re-runs don't duplicate). If you've
already seen decisions, it skips by design. Send manually with
`uv run scripts/send_expense.py --file samples/travel.txt --cloud`. The hook is also best-effort: a
cold start or RBAC lag right after deploy can skip it without failing the deploy.

## Local run: the agent can't reach a model

Local Azurite covers the queues and policy blobs, but the agent still calls an Azure OpenAI / Foundry
model. Copy [`src/local.settings.json.sample`](../src/local.settings.json.sample) to
`src/local.settings.json` and set `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_DEPLOYMENT` (leave the API
key empty to use `DefaultAzureCredential`). Running `azd provision` once creates a Foundry deployment
and establishes an `azd` credential you can use locally.

## `uv run func start` fails to import the runtime

Make sure you're running from the `src/` directory (where `pyproject.toml` lives) so uv resolves the
function app's environment. `uv sync` in `src/` rebuilds `.venv` from `uv.lock`.

## Windows local dev

On Windows, `uv run func start` can fail with
`ModuleNotFoundError: No module named 'azure_functions_agents'` even after a clean `uv sync`. The
cause is the **Microsoft Store `python.exe` alias**: it sits ahead of the uv-managed venv on your
`PATH`, so the Functions host launches the wrong interpreter. Turn it off in **Settings → Apps →
Advanced app settings → App execution aliases** (disable the `python.exe` and `python3.exe` Microsoft
Store entries), open a new terminal, and run `uv run func start` from `src/` again. Installing the
interpreter with uv (`uv python install 3.13`) keeps the venv Python authoritative.

# Deploy to Azure

`azd up` provisions everything in [`infra/`](../infra/), deploys the app, seeds the policy documents,
and drops three sample requests on the queue so you see decisions immediately.

## Prerequisites

- An **Azure subscription** with permission to create Functions, Storage, and Microsoft Foundry
  resources.
- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd).
- [uv](https://docs.astral.sh/uv/): the `prepackage` hook runs `uv export` to generate
  `requirements.txt`, and the deployment hooks and helper scripts run with `uv run`.

## Provision and deploy

```bash
azd up
```

`azd up` prompts for an environment name, subscription, and region on first run, then:

1. **Provisions** the resources below.
2. **Seeds** the bundled policy documents into the `policies` blob container (post-provision hook).
3. **Packages** the app: the `prepackage` hook regenerates `src/requirements.txt` from
   `src/pyproject.toml` + `src/uv.lock` via `uv export`, so the Functions remote build has one.
4. **Deploys** the function app.
5. **Sends** the three `$450` sample requests to the input queue (post-up hook) so decisions land on
   the output queues within a minute.

Read the decisions:

```bash
uv run scripts/read_decision.py --queue all --peek --cloud
```

The default view groups decisions by outcome and shows the selected policy and reason. Add `--raw`
to print the original queue JSON.

## What gets deployed

- **Function App:** Flex Consumption, Python 3.13, running the agent.
- **Microsoft Foundry** account + project + a `gpt-5.4` model deployment.
- **Storage account:** the `expense-requests` input queue, the `expense-approved` /
  `expense-review` / `expense-flagged` output queues, and a `policies` blob container that holds the
  approval policy documents. Shared-key access is **disabled**.
- **User-assigned managed identity** + RBAC:

  | Identity | Role | Why |
  |---|---|---|
  | Function app MI | Storage Queue Data Contributor | trigger reads the input queue; `route_expense_decision` writes the output queues |
  | Function app MI | Storage Blob Data | the policy tools list and read the policy blobs |
  | Function app MI | Cognitive Services OpenAI User | the agent calls the Foundry model |
  | Deploying user | Storage Queue Data Contributor + Storage Blob Data Contributor | so the demo scripts and hooks can send requests, read decisions, and change policies out of the box |

Key values are printed as `azd` outputs and saved to `.azure/<env>/.env` (for example
`OUTPUT_STORAGE_ACCOUNT`, `AZURE_FUNCTION_NAME`, and `INPUT_QUEUE_NAME`).

## Auto-seeding and the demo send

Two hooks in [`azure.yaml`](../azure.yaml) call
[`scripts/setup_demo.py`](../scripts/setup_demo.py) so a fresh deploy works without a manual setup
step. The helper uses `DefaultAzureCredential`, including the identity established by `azd`, and both
hooks are best-effort (`continueOnError`) because the runtime is a guaranteed fallback:

- **`postprovision`: seed policies.** Uploads [`src/policies/*.md`](../src/policies/) into the
  `policies` container. It seeds **only when the container is empty**, so re-provisioning never
  overwrites a policy you've edited. (The agent also re-seeds lazily on its first run if the container
  is ever empty.)
- **`postup`: demo send.** Drops the three `$450` samples (travel, equipment, client dinner) on the
  input queue so you see the multi-policy behavior immediately. It sends **only when the output queues
  are empty**, so re-running `azd up` won't pile on duplicates.

## Send and read against the cloud yourself

The helper scripts talk to the deployed account over **Entra ID** (no keys). `azd` already granted
your identity the roles above, so you can send, read, and change policies right away. `--cloud`
auto-resolves the account from your `azd` env:

```bash
uv run scripts/send_expense.py --file samples/travel.txt --cloud
uv run scripts/read_decision.py --queue all --peek --cloud
```

## Clean up

```bash
azd down --purge
```

---

Change a policy without redeploying: [customize.md](customize.md). Hitting an error:
[troubleshooting.md](troubleshooting.md).

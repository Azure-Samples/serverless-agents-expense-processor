#!/usr/bin/env python3
"""Show or replace the expense-approval policy document the agent reads at decision time.

The policy lives as a blob (`policies/expense-policy.md`) in the same storage account as the
queues. Because the agent fetches it on every run, replacing the blob changes how requests are
routed with **no code change and no redeploy** — send the same expense before and after and
watch the decision follow the policy.

By default this targets local Azurite (AzureWebJobsStorage=UseDevelopmentStorage=true). Use
``--cloud`` to target the deployed storage account over Entra ID (needs the "Storage Blob Data
Contributor" role, which azd grants the deployer).

Examples
--------
    # Show the policy currently in effect
    python scripts/set_policy.py --show
    python scripts/set_policy.py --show --cloud

    # Swap in the stricter policy, then re-send a $45 lunch and watch it flip approve -> review
    python scripts/set_policy.py --file samples/strict-policy.md --cloud
    python scripts/send_expense.py --file samples/approve.txt --cloud
    python scripts/read_decision.py --queue all --peek --cloud

    # Restore the default policy
    python scripts/set_policy.py --file src/policies/expense-policy.md --cloud
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from azure.storage.blob import BlobClient

from _cloud import resolve_blob_account_url

DEV_CONNECTION_STRING = "UseDevelopmentStorage=true"


def build_blob_client(args: argparse.Namespace) -> BlobClient:
    """Create a BlobClient from either an account URL (Entra ID) or a connection string."""
    if args.account_url:
        from azure.identity import DefaultAzureCredential

        return BlobClient(
            account_url=args.account_url,
            container_name=args.container,
            blob_name=args.blob,
            credential=DefaultAzureCredential(),
        )
    return BlobClient.from_connection_string(
        args.connection_string, container_name=args.container, blob_name=args.blob
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--show", action="store_true", help="Print the current policy and exit.")
    parser.add_argument("--file", "-f", help="Path to a policy document (.md/.txt) to upload.")
    parser.add_argument("--container", default=os.environ.get("POLICY_CONTAINER", "policies"), help="Blob container.")
    parser.add_argument("--blob", default=os.environ.get("POLICY_BLOB", "expense-policy.md"), help="Blob name.")
    parser.add_argument(
        "--connection-string",
        default=os.environ.get("AzureWebJobsStorage", DEV_CONNECTION_STRING),
        help="Storage connection string (defaults to Azurite dev storage).",
    )
    parser.add_argument(
        "--account-url",
        default=os.environ.get("OUTPUT_STORAGE_ACCOUNT_BLOB_URL"),
        help="Blob endpoint, e.g. https://<acct>.blob.core.windows.net. When set, authenticates "
        "with Entra ID (DefaultAzureCredential) instead of a connection string.",
    )
    parser.add_argument(
        "--cloud",
        action="store_true",
        help="Target the DEPLOYED storage account (Entra ID). Auto-resolves the blob endpoint "
        "from OUTPUT_STORAGE_ACCOUNT_BLOB_URL / OUTPUT_STORAGE_ACCOUNT or `azd env get-values`.",
    )
    args = parser.parse_args()

    if args.cloud and not args.account_url:
        args.account_url = resolve_blob_account_url()
        if not args.account_url:
            raise SystemExit(
                "--cloud could not resolve the deployed storage account. Run this from the "
                "project root after `azd up` (needs OUTPUT_STORAGE_ACCOUNT in the azd env), "
                "or pass --account-url https://<acct>.blob.core.windows.net explicitly."
            )

    if not args.show and not args.file:
        raise SystemExit("Nothing to do: pass --show to read, or --file PATH to upload a policy.")

    client = build_blob_client(args)
    target = args.account_url or "Azurite"

    if args.file:
        text = open(args.file, "r", encoding="utf-8").read()
        # Locally the container may not exist yet; create it. In the cloud it is provisioned by
        # azd, and the upload will find it.
        if not args.account_url:
            from azure.storage.blob import ContainerClient

            try:
                ContainerClient.from_connection_string(
                    args.connection_string, args.container
                ).create_container()
            except Exception:
                pass  # already exists
        client.upload_blob(text.encode("utf-8"), overwrite=True)
        print(f"Uploaded '{args.file}' -> {args.container}/{args.blob} ({target}, {len(text)} bytes)")

    if args.show:
        text = client.download_blob().readall().decode("utf-8")
        print(f"--- {args.container}/{args.blob} ({target}) ---")
        print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())

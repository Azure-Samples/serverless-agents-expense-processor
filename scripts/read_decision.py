#!/usr/bin/env python3
"""Read and print messages from a decision output queue.

Useful for verifying routing after deployment (use --cloud, or point --account-url at
the deployed storage account) or for local experiments against Azurite.

Examples
--------
    python scripts/read_decision.py --queue expense-approved
    python scripts/read_decision.py --queue expense-review
    python scripts/read_decision.py --queue expense-flagged

    # Peek ALL three decision queues at once (handy right after sending a batch):
    python scripts/read_decision.py --queue all --peek

    # Against the DEPLOYED account (Entra ID) — auto-resolves the queue endpoint from your
    # azd env (OUTPUT_STORAGE_ACCOUNT). Requires `az login`; the signed-in user needs the
    # "Storage Queue Data Reader" (peek) or "Message Processor" (receive+delete) role.
    python scripts/read_decision.py --queue all --peek --cloud

    # Or point at a specific account explicitly:
    python scripts/read_decision.py --queue expense-approved \
        --account-url https://<storageaccount>.queue.core.windows.net
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from azure.storage.queue import QueueClient

from _cloud import resolve_queue_account_url

DEV_CONNECTION_STRING = "UseDevelopmentStorage=true"

# The three decision queues the agent routes to, in amount order.
DECISION_QUEUES = ["expense-approved", "expense-review", "expense-flagged"]


def build_queue_client(args: argparse.Namespace, queue_name: str) -> QueueClient:
    """Create a QueueClient from either an account URL (Entra ID) or a connection string."""
    if args.account_url:
        from azure.identity import DefaultAzureCredential

        return QueueClient(
            account_url=args.account_url,
            queue_name=queue_name,
            credential=DefaultAzureCredential(),
        )
    return QueueClient.from_connection_string(args.connection_string, queue_name)


def decode(text: str) -> str:
    """Best-effort: return decoded JSON whether the message is base64 or raw text."""
    try:
        candidate = base64.b64decode(text).decode("utf-8")
        json.loads(candidate)
        return candidate
    except Exception:
        return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue", "-q", required=True, help="Queue name to read (e.g. expense-approved).")
    parser.add_argument("--max", "-n", type=int, default=32, help="Max messages to read.")
    parser.add_argument("--peek", action="store_true", help="Peek without dequeuing.")
    parser.add_argument(
        "--connection-string",
        default=os.environ.get("AzureWebJobsStorage", DEV_CONNECTION_STRING),
        help="Storage connection string (defaults to Azurite dev storage).",
    )
    parser.add_argument(
        "--account-url",
        default=os.environ.get("OUTPUT_STORAGE_ACCOUNT_URL"),
        help="Queue endpoint, e.g. https://<acct>.queue.core.windows.net. When set, "
        "authenticates with Entra ID (DefaultAzureCredential) instead of a connection string.",
    )
    parser.add_argument(
        "--cloud",
        action="store_true",
        help="Read from the DEPLOYED Azure storage account (Entra ID). Auto-resolves the queue "
        "endpoint from OUTPUT_STORAGE_ACCOUNT_URL / OUTPUT_STORAGE_ACCOUNT or `azd env get-values`.",
    )
    args = parser.parse_args()

    if args.cloud and not args.account_url:
        args.account_url = resolve_queue_account_url()
        if not args.account_url:
            raise SystemExit(
                "--cloud could not resolve the deployed storage account. Run this from the "
                "project root after `azd up` (needs OUTPUT_STORAGE_ACCOUNT in the azd env), "
                "or pass --account-url https://<acct>.queue.core.windows.net explicitly."
            )

    queues = DECISION_QUEUES if args.queue == "all" else [args.queue]
    total = 0
    for queue_name in queues:
        client = build_queue_client(args, queue_name)
        count = 0
        if args.peek:
            for msg in client.peek_messages(max_messages=min(args.max, 32)):
                print(f"[{queue_name}] {decode(msg.content)}")
                count += 1
        else:
            for msg in client.receive_messages(max_messages=args.max):
                print(f"[{queue_name}] {decode(msg.content)}")
                client.delete_message(msg)
                count += 1
        if args.queue == "all":
            print(f"  ({count} in '{queue_name}')", file=sys.stderr)
        total += count
    print(f"\n({total} message(s) total)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

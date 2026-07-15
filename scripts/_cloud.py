"""Shared helper for the demo scripts: resolve the deployed storage account's queue and
blob endpoints so ``--cloud`` targets the deployed resources (Entra ID) without pasting a URL.

Resolution order (first hit wins):
  1. an explicit value (e.g. ``--account-url``)
  2. ``OUTPUT_STORAGE_ACCOUNT_URL``  — a full queue endpoint URL
  3. ``OUTPUT_STORAGE_ACCOUNT``      — the account *name*; we build the URL
  4. ``azd env get-values``          — reads ``OUTPUT_STORAGE_ACCOUNT`` from the azd env

Returns ``None`` when nothing resolves.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _account_name_from_azd() -> str | None:
    """Read OUTPUT_STORAGE_ACCOUNT from `azd env get-values` (run in the project root)."""
    azd = shutil.which("azd")
    if not azd:
        return None
    try:
        result = subprocess.run(
            [azd, "env", "get-values"],
            cwd=_project_root(),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("OUTPUT_STORAGE_ACCOUNT="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def resolve_queue_account_url(explicit: str | None = None) -> str | None:
    """Return the queue endpoint URL for the deployed storage account, or None."""
    if explicit:
        return explicit
    url = os.environ.get("OUTPUT_STORAGE_ACCOUNT_URL")
    if url:
        return url
    name = os.environ.get("OUTPUT_STORAGE_ACCOUNT") or _account_name_from_azd()
    if name:
        return f"https://{name}.queue.core.windows.net"
    return None


def resolve_blob_account_url(explicit: str | None = None) -> str | None:
    """Return the blob endpoint URL for the deployed storage account, or None.

    Mirrors :func:`resolve_queue_account_url` for the policy document, which lives in
    Blob Storage on the same account as the queues.
    """
    if explicit:
        return explicit
    url = os.environ.get("OUTPUT_STORAGE_ACCOUNT_BLOB_URL")
    if url:
        return url
    name = os.environ.get("OUTPUT_STORAGE_ACCOUNT") or _account_name_from_azd()
    if name:
        return f"https://{name}.blob.core.windows.net"
    return None

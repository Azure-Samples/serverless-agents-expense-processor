"""Shared helpers for the policy tools.

This module is prefixed with ``_`` so the runtime's tool discovery skips it when
scanning ``src/tools/*.py`` (discovery ignores underscore-prefixed files and only
registers the first ``@tool`` it finds per file). The two thin tool wrappers
(``get_policy.py`` and ``list_policies.py``) import the functions defined here so
they can share the blob-storage client, seeding, and parsing logic.
"""

import json
import os
import re
from pathlib import Path

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

# Where the policy documents live. Overridable via app settings (set by infra/main.bicep);
# defaults keep local Azurite runs zero-config.
_POLICY_CONTAINER = os.environ.get("POLICY_CONTAINER", "policies")

# The fallback policy used when a request matches no category-specific policy, or when a
# requested document can't be found. Overridable via the POLICY_BLOB app setting.
_DEFAULT_POLICY = os.environ.get("POLICY_BLOB", "general-expense-policy.md")

# The bundled policy documents that ship with the sample. On first use (empty container)
# every one of these is uploaded to blob storage, so a fresh deploy — or a clean local
# Azurite — has a working policy set without any manual seeding. Replace or add blobs to
# change routing behavior (see scripts/set_policy.py) — no code change or redeploy required.
_POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"

# Substrings that mark AzureWebJobsStorage as a classic connection string
# (Azurite / shared-key) rather than an identity-based connection.
_CONNECTION_STRING_MARKERS = (
    "UseDevelopmentStorage=true",
    "AccountKey=",
    "DefaultEndpointsProtocol=",
)

_APPLIES_TO_RE = re.compile(r"^\*\*Applies to:\*\*\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _is_connection_string(value: str) -> bool:
    return any(marker in value for marker in _CONNECTION_STRING_MARKERS)


def _blob_service_client() -> BlobServiceClient:
    """Build a :class:`BlobServiceClient` for the policy store.

    Uses the local Azurite connection string when one is present, otherwise
    authenticates to the cloud storage account with managed identity.
    """
    connection = os.environ.get("AzureWebJobsStorage", "")
    if _is_connection_string(connection):
        return BlobServiceClient.from_connection_string(connection)

    endpoint = os.environ.get("AzureWebJobsStorage__blobServiceUri")
    if not endpoint:
        account = os.environ.get("OUTPUT_STORAGE_ACCOUNT")
        if not account:
            raise RuntimeError(
                "No blob endpoint available. Set AzureWebJobsStorage to a "
                "connection string (local) or provide "
                "AzureWebJobsStorage__blobServiceUri / OUTPUT_STORAGE_ACCOUNT (cloud)."
            )
        endpoint = f"https://{account}.blob.core.windows.net"

    # Imported lazily so local (connection-string) runs don't require azure-identity.
    from azure.identity import DefaultAzureCredential

    # DefaultAzureCredential picks up the user-assigned identity via AZURE_CLIENT_ID.
    return BlobServiceClient(
        account_url=endpoint.rstrip("/"),
        credential=DefaultAzureCredential(),
    )


def _bundled_policies() -> list[Path]:
    """The policy documents shipped with the app (src/policies/*.md)."""
    return sorted(_POLICIES_DIR.glob("*.md"))


def _ensure_seeded(service: BlobServiceClient) -> None:
    """Upload the bundled policy documents if the container has none yet.

    In the cloud the container is provisioned empty by infra/main.bicep; locally it
    may not exist at all. Either way, the first policy call seeds every bundled
    document so the sample works without manual setup. Idempotent: once any policy
    exists the seed is skipped, so operator edits are never overwritten.
    """
    container = service.get_container_client(_POLICY_CONTAINER)
    try:
        existing = any(container.list_blobs())
    except ResourceNotFoundError:
        # Container missing (clean local Azurite). Create it, then seed.
        try:
            container.create_container()
        except ResourceExistsError:
            pass
        existing = False

    if existing:
        return

    for path in _bundled_policies():
        container.upload_blob(
            name=path.name,
            data=path.read_text(encoding="utf-8").encode("utf-8"),
            overwrite=True,
        )


def _scope_of(text: str) -> str:
    """A one-line summary of what a policy covers (its **Applies to:** line)."""
    match = _APPLIES_TO_RE.search(text)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    heading = _HEADING_RE.search(text)
    return heading.group(1).strip() if heading else ""


def list_policies() -> str:
    """Return the catalog of policy documents as a JSON array string.

    Seeds the bundled documents on first use, then lists whatever is in the policy
    container so operator-added policies show up too. Each entry is
    ``{"name": <blob>, "appliesTo": <scope>}``.
    """
    service = _blob_service_client()
    _ensure_seeded(service)
    container = service.get_container_client(_POLICY_CONTAINER)

    catalog = []
    for blob in container.list_blobs():
        text = container.download_blob(blob.name).readall().decode("utf-8")
        catalog.append({"name": blob.name, "appliesTo": _scope_of(text)})
    catalog.sort(key=lambda item: item["name"])
    return json.dumps(catalog)


def get_policy(policy_name: str = "") -> str:
    """Return the text of the requested policy from blob storage.

    Falls back to the default (general) policy when ``policy_name`` is blank or the
    named document doesn't exist, so a mismatched name never fails the request.
    """
    service = _blob_service_client()
    _ensure_seeded(service)
    container = service.get_container_client(_POLICY_CONTAINER)

    name = policy_name.strip() or _DEFAULT_POLICY
    try:
        return container.download_blob(name).readall().decode("utf-8")
    except ResourceNotFoundError:
        if name == _DEFAULT_POLICY:
            raise
        text = container.download_blob(_DEFAULT_POLICY).readall().decode("utf-8")
        return f"> Requested policy '{name}' was not found; applying the general policy instead.\n\n{text}"

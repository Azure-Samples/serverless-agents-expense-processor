import os
from pathlib import Path

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient
from azure_functions_agents import tool

# Where the policy document lives. Overridable via app settings (set by infra/main.bicep);
# defaults keep local Azurite runs zero-config.
_POLICY_CONTAINER = os.environ.get("POLICY_CONTAINER", "policies")
_POLICY_BLOB = os.environ.get("POLICY_BLOB", "expense-policy.md")

# The policy document that ships with the sample. It is uploaded to blob storage on first
# use if the blob doesn't exist yet, so a fresh deploy (or a clean local Azurite) has a
# working policy without any manual seeding. Replace the blob to change routing behavior
# (see scripts/set_policy.py) — no code change or redeploy required.
_SEED_POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / _POLICY_BLOB

# Substrings that mark AzureWebJobsStorage as a classic connection string
# (Azurite / shared-key) rather than an identity-based connection.
_CONNECTION_STRING_MARKERS = (
    "UseDevelopmentStorage=true",
    "AccountKey=",
    "DefaultEndpointsProtocol=",
)


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


def _seed_policy_text() -> str:
    """The bundled policy document shipped with the app."""
    return _SEED_POLICY_PATH.read_text(encoding="utf-8")


@tool(
    name="get_expense_policy",
    description=(
        "Fetch the current expense-approval policy. Call this first, before deciding, "
        "and apply the returned policy exactly to the request you are processing. The "
        "policy is a document owned by Finance, so it can change between runs — always "
        "read it fresh rather than relying on remembered rules."
    ),
)
def get_expense_policy() -> str:
    """Return the current expense policy text from blob storage.

    On first use (blob or container missing) the bundled policy document is uploaded
    and returned, so the sample works without any manual seeding in either environment.
    The app's identity can read and create blobs in both: Storage Blob Data
    Contributor/Owner in the cloud, the Azurite connection string locally.
    """
    service = _blob_service_client()
    blob = service.get_blob_client(_POLICY_CONTAINER, _POLICY_BLOB)
    try:
        return blob.download_blob().readall().decode("utf-8")
    except ResourceNotFoundError:
        # No policy has been uploaded yet. Seed the bundled document and return it. In
        # the cloud infra/main.bicep provisions the container; locally it may not exist
        # yet, so create it first (ignoring a concurrent create) and then upload.
        text = _seed_policy_text()
        try:
            service.create_container(_POLICY_CONTAINER)
        except ResourceExistsError:
            pass
        blob.upload_blob(text.encode("utf-8"), overwrite=True)
        return text

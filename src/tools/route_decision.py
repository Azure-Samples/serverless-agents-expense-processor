import os
from typing import Annotated

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.queue import QueueClient
from azure_functions_agents import tool

# The three destination queues provisioned by infra/app/storage-queues.bicep.
_ALLOWED_QUEUES = ("expense-approved", "expense-review", "expense-flagged")

# Substrings that mark AzureWebJobsStorage as a classic connection string
# (Azurite / shared-key) rather than an identity-based connection.
_CONNECTION_STRING_MARKERS = (
    "UseDevelopmentStorage=true",
    "AccountKey=",
    "DefaultEndpointsProtocol=",
)


def _is_connection_string(value: str) -> bool:
    return any(marker in value for marker in _CONNECTION_STRING_MARKERS)


def _queue_client(queue_name: str) -> QueueClient:
    """Build a :class:`QueueClient` for ``queue_name``.

    Uses the local Azurite connection string when one is present, otherwise
    authenticates to the cloud storage account with managed identity.
    """
    connection = os.environ.get("AzureWebJobsStorage", "")
    if _is_connection_string(connection):
        return QueueClient.from_connection_string(connection, queue_name)

    endpoint = os.environ.get("AzureWebJobsStorage__queueServiceUri")
    if not endpoint:
        account = os.environ.get("OUTPUT_STORAGE_ACCOUNT")
        if not account:
            raise RuntimeError(
                "No queue endpoint available. Set AzureWebJobsStorage to a "
                "connection string (local) or provide "
                "AzureWebJobsStorage__queueServiceUri / OUTPUT_STORAGE_ACCOUNT (cloud)."
            )
        endpoint = f"https://{account}.queue.core.windows.net"

    # Imported lazily so local (connection-string) runs don't require azure-identity.
    from azure.identity import DefaultAzureCredential

    # DefaultAzureCredential picks up the user-assigned identity via AZURE_CLIENT_ID.
    return QueueClient(
        account_url=endpoint.rstrip("/"),
        queue_name=queue_name,
        credential=DefaultAzureCredential(),
    )


@tool(
    name="route_expense_decision",
    description=(
        "Send the final expense decision to its destination Storage queue. Call "
        "this exactly once, after you have decided, with the chosen queue "
        "(expense-approved, expense-review, or expense-flagged) and the decision JSON."
    ),
)
def route_expense_decision(
    queue_name: Annotated[
        str,
        "Destination queue: one of 'expense-approved', 'expense-review', 'expense-flagged'.",
    ],
    message: Annotated[
        str,
        "The compact decision JSON to enqueue as the message body.",
    ],
) -> str:
    """Enqueue ``message`` on ``queue_name`` using the app's managed identity."""
    if queue_name not in _ALLOWED_QUEUES:
        raise ValueError(
            f"queue_name must be one of {list(_ALLOWED_QUEUES)}, got {queue_name!r}."
        )

    client = _queue_client(queue_name)
    try:
        client.send_message(message)
    except ResourceNotFoundError:
        # The destination queue doesn't exist yet. In the cloud the three queues are
        # provisioned by infra/app/storage-queues.bicep, but a fresh local Azurite has
        # only whatever has been created so far. Create it and retry once. The app's
        # identity (Storage Queue Data Contributor locally via the connection string,
        # managed identity in the cloud) is allowed to create queues in both.
        try:
            client.create_queue()
        except ResourceExistsError:
            pass  # created concurrently by another invocation
        client.send_message(message)
    return f"Routed decision to '{queue_name}'."

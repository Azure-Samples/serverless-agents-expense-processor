from typing import Annotated

from azure_functions_agents import tool

# Shared logic lives in _policy_store (underscore-prefixed so tool discovery skips it).
# Discovery registers only the first @tool per file, so each policy tool needs its own file.
from _policy_store import get_policy as _get_policy


@tool(
    name="get_expense_policy",
    description=(
        "Fetch the full text of one expense-approval policy by its exact document name "
        "(as returned by list_expense_policies). Apply the returned policy exactly to the "
        "request you are processing. If the request matches no specific policy, request the "
        "general policy. Policies are owned by Finance and can change between runs — always "
        "read fresh rather than relying on remembered rules."
    ),
)
def get_expense_policy(
    policy_name: Annotated[
        str,
        "Exact policy document name from list_expense_policies, e.g. 'travel-policy.md'. "
        "Use the general policy when nothing else fits.",
    ] = "",
) -> str:
    """Return the text of the requested expense-approval policy from blob storage."""
    return _get_policy(policy_name)

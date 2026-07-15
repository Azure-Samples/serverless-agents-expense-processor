from azure_functions_agents import tool

# Shared logic lives in _policy_store (underscore-prefixed so tool discovery skips it).
# Discovery registers only the first @tool per file, so each policy tool needs its own file.
from _policy_store import list_policies as _list_policies


@tool(
    name="list_expense_policies",
    description=(
        "List the available expense-approval policy documents and what each one covers. "
        "Call this after you have extracted the request so you can choose the policy whose "
        "scope matches the expense category (travel, meals, equipment, etc.), then fetch "
        "that policy with get_expense_policy. Returns a JSON array of {name, appliesTo} "
        "objects; pass a name back to get_expense_policy verbatim."
    ),
)
def list_expense_policies() -> str:
    """Return the catalog of expense-approval policies (name + scope) as JSON."""
    return _list_policies()

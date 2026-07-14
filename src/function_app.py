"""Function app entry point for the queue-triggered Expense Processor agent.

The agent itself is defined declaratively in ``expense_processor.agent.md``;
``create_function_app()`` discovers every ``*.agent.md`` file and registers its
trigger. We only add one small compatibility shim below.

Compatibility shim (Azure Functions serverless agents runtime 0.1.0b6)
---------------------------------------------------------------------
For non-HTTP triggers the runtime turns the trigger payload into the agent
prompt via ``registration._handlers.serialize_trigger_data``. That helper knows
how to serialize a ``dict``/``str`` (what its unit tests feed it) but the real
Azure Functions Python worker delivers a binding object instead - e.g. a
``azure.functions.QueueMessage`` for a queue trigger. The stock helper has no
branch for those objects, so it falls through to ``str(obj)`` and the agent
receives ``"<azure.QueueMessage id=... >"`` instead of the JSON message body.

We patch the helper to first pull the decoded body out of any binding object
that exposes ``get_body()`` (QueueMessage, ServiceBusMessage, EventHubEvent,
...). This is exactly the raw message the sender enqueued, so the agent sees the
real JSON and the amount-based decision works. Everything else falls back to the
runtime's original behavior.
"""

from azure_functions_agents import create_function_app
from azure_functions_agents.registration import _handlers

_original_serialize_trigger_data = _handlers.serialize_trigger_data


def _serialize_trigger_data(trigger_data):
    """Decode message-binding objects to their raw body before serializing."""
    get_body = getattr(trigger_data, "get_body", None)
    if callable(get_body):
        body = get_body()
        if isinstance(body, (bytes, bytearray)):
            return bytes(body).decode("utf-8", errors="replace")
        if isinstance(body, str):
            return body
    return _original_serialize_trigger_data(trigger_data)


_handlers.serialize_trigger_data = _serialize_trigger_data

app = create_function_app()

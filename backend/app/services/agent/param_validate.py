"""Host-side validation of model-provided tool arguments (BE-08, AI-02).

The model's ``arguments`` are validated against the tool's advertised
``inputSchema`` *before* any outbound request. Invalid arguments are rejected
by the host (status ``rejected``) and the server is never called.
"""

import jsonschema


def validate_tool_args(input_schema: dict | None, arguments) -> tuple[bool, str]:
    """Return ``(ok, reason)``. ``reason`` is empty when ok."""
    if not isinstance(arguments, dict):
        return False, "arguments must be a JSON object"
    schema = input_schema if isinstance(input_schema, dict) and input_schema else {"type": "object"}
    try:
        jsonschema.validate(instance=arguments, schema=schema)
        return True, ""
    except jsonschema.ValidationError as exc:
        return False, exc.message
    except jsonschema.SchemaError:
        # Tool advertised a broken schema; reject rather than guess.
        return False, "tool input schema is invalid"

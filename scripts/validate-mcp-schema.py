#!/usr/bin/env python3
"""Validate MCP tool definitions against MCP schema 2025-06-18.

This script validates that all tool definitions in mcp_server.py conform to
the MCP specification schema.

Usage:
    python scripts/validate-mcp-schema.py
"""

import json
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import jsonschema
from jsonschema import validate

# MCP Schema URL
MCP_SCHEMA_URL = "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/refs/heads/main/schema/2025-06-18/schema.json"

# Local schema cache path
SCHEMA_CACHE = Path(__file__).parent.parent / ".cache" / "mcp-schema.json"


def fetch_schema() -> dict[str, Any]:
    """Fetch MCP schema from remote or cache."""
    # Try cache first
    if SCHEMA_CACHE.exists():
        try:
            with open(SCHEMA_CACHE) as f:
                return json.load(f)
        except Exception:
            pass

    # Fetch from remote
    try:
        print(f"Fetching MCP schema from {MCP_SCHEMA_URL}...", file=sys.stderr)
        with urlopen(MCP_SCHEMA_URL, timeout=10) as response:
            schema = json.loads(response.read())

        # Cache schema
        SCHEMA_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(SCHEMA_CACHE, "w") as f:
            json.dump(schema, f, indent=2)

        return schema
    except Exception as e:
        print(f"Error fetching schema: {e}", file=sys.stderr)
        print("Continuing with basic validation...", file=sys.stderr)
        return {}


def validate_tool(
    tool: dict[str, Any], schema: dict[str, Any], tool_name: str
) -> list[str]:
    """Validate a single tool against MCP schema.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Check required fields
    if "name" not in tool:
        errors.append(f"Tool '{tool_name}': Missing required field 'name'")
    if "description" not in tool:
        errors.append(f"Tool '{tool_name}': Missing required field 'description'")
    if "inputSchema" not in tool:
        errors.append(f"Tool '{tool_name}': Missing required field 'inputSchema'")

    # Validate against schema if available
    if schema and "definitions" in schema and "Tool" in schema["definitions"]:
        tool_schema = schema["definitions"]["Tool"]
        try:
            validate(instance=tool, schema=tool_schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Tool '{tool_name}': Schema validation error: {e.message}")

    # Basic validation even without schema
    if "inputSchema" in tool:
        input_schema = tool["inputSchema"]
        if not isinstance(input_schema, dict):
            errors.append(f"Tool '{tool_name}': inputSchema must be a dict")
        elif "type" not in input_schema:
            errors.append(f"Tool '{tool_name}': inputSchema must have 'type' field")
        elif input_schema["type"] != "object":
            errors.append(f"Tool '{tool_name}': inputSchema.type must be 'object'")

    return errors


def extract_tools_from_server() -> dict[str, dict[str, Any]]:
    """Extract tool definitions from mcp_server.py.

    This is a simplified extractor - in practice, tools are defined using
    the @mcp.tool() decorator. For validation, we'd need to actually import
    and inspect the module, but that requires the full environment.

    Returns:
        Dict mapping tool names to tool definitions
    """
    # For now, return empty dict - full implementation would require
    # importing mcp_server and inspecting the tools
    # This is a placeholder for future enhancement
    return {}


def main() -> int:
    """Main validation function."""
    print(
        "Validating MCP tool definitions against schema 2025-06-18...", file=sys.stderr
    )

    schema = fetch_schema()
    if not schema:
        print(
            "Warning: Could not fetch schema, performing basic validation only",
            file=sys.stderr,
        )

    # Extract tools (placeholder - would need full module import)
    tools = extract_tools_from_server()

    if not tools:
        print(
            "Note: Tool extraction not fully implemented - skipping detailed validation",
            file=sys.stderr,
        )
        print(
            "This script is a placeholder for future MCP schema validation",
            file=sys.stderr,
        )
        return 0

    # Validate each tool
    all_errors = []
    for tool_name, tool_def in tools.items():
        errors = validate_tool(tool_def, schema, tool_name)
        all_errors.extend(errors)

    # Report results
    if all_errors:
        print("\nValidation errors found:", file=sys.stderr)
        for error in all_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("All tools validated successfully!", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

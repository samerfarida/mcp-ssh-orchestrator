#!/usr/bin/env python3
"""Validate MCP tool definitions against MCP schema 2025-06-18.

This script validates that all tool definitions in mcp_server.py conform to
the MCP specification schema.

Usage:
    python scripts/validate-mcp-schema.py
"""

import ast
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import validate

# MCP Schema URL
MCP_SCHEMA_URL = "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/refs/heads/main/schema/2025-06-18/schema.json"

# Local schema cache path
SCHEMA_CACHE = Path(__file__).parent.parent / ".cache" / "mcp-schema.json"

# Path to mcp_server.py
MCP_SERVER_PATH = Path(__file__).parent.parent / "src" / "mcp_ssh" / "mcp_server.py"


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
        from urllib.request import urlopen

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


def extract_tools_from_ast() -> dict[str, dict[str, Any]]:
    """Extract tool definitions from mcp_server.py using AST parsing.

    Returns:
        Dict mapping tool names to tool definitions
    """
    tools = {}

    try:
        with open(MCP_SERVER_PATH) as f:
            tree = ast.parse(f.read(), filename=str(MCP_SERVER_PATH))

        for node in ast.walk(tree):
            # Look for functions decorated with @mcp.tool() (both sync and async)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Check for @mcp.tool() decorator
                has_tool_decorator = False
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if (
                            isinstance(decorator.func, ast.Attribute)
                            and isinstance(decorator.func.value, ast.Name)
                            and decorator.func.value.id == "mcp"
                            and decorator.func.attr == "tool"
                        ):
                            has_tool_decorator = True
                            break

                if has_tool_decorator:
                    # Extract function name (tool name)
                    tool_name = node.name

                    # Extract docstring (description)
                    description = ast.get_docstring(node) or ""

                    # Extract parameters (for inputSchema)
                    properties = {}
                    required = []
                    for arg in node.args.args:
                        if arg.arg == "self" or arg.arg == "ctx":
                            continue
                        param_name = arg.arg
                        # Check if parameter has default value
                        has_default = len(node.args.defaults) > 0 and (
                            len(node.args.args) - len(node.args.defaults)
                            <= node.args.args.index(arg)
                        )
                        if not has_default:
                            required.append(param_name)

                        # Infer type from annotation if available
                        param_type = "string"  # Default
                        if arg.annotation:
                            if isinstance(arg.annotation, ast.Constant):
                                if arg.annotation.value == "int":
                                    param_type = "integer"
                            elif isinstance(arg.annotation, ast.Name):
                                if arg.annotation.id == "int":
                                    param_type = "integer"

                        properties[param_name] = {"type": param_type}

                    # Build tool definition
                    tool_def = {
                        "name": tool_name,
                        "description": description.strip(),
                        "inputSchema": {
                            "type": "object",
                            "properties": properties,
                            "required": required if required else None,
                        },
                    }

                    # Remove required if empty (MCP spec allows this)
                    if not tool_def["inputSchema"]["required"]:
                        del tool_def["inputSchema"]["required"]

                    tools[tool_name] = tool_def

    except Exception as e:
        print(f"Error parsing mcp_server.py: {e}", file=sys.stderr)
        return {}

    return tools


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
            errors.append(
                f"Tool '{tool_name}': Schema validation error: {e.message} (path: {'.'.join(str(p) for p in e.path)})"
            )

    # Basic validation even without schema
    if "inputSchema" in tool:
        input_schema = tool["inputSchema"]
        if not isinstance(input_schema, dict):
            errors.append(f"Tool '{tool_name}': inputSchema must be a dict")
        elif "type" not in input_schema:
            errors.append(f"Tool '{tool_name}': inputSchema must have 'type' field")
        elif input_schema["type"] != "object":
            errors.append(
                f"Tool '{tool_name}': inputSchema.type must be 'object', got '{input_schema['type']}'"
            )

        # Validate properties structure
        if "properties" in input_schema:
            if not isinstance(input_schema["properties"], dict):
                errors.append(
                    f"Tool '{tool_name}': inputSchema.properties must be a dict"
                )

    return errors


def check_mcp_compliance() -> list[str]:
    """Check MCP specification compliance beyond schema validation.

    Returns:
        List of compliance warnings/errors
    """
    issues = []

    # Check that we're using stdio transport (MCP requirement)
    try:
        with open(MCP_SERVER_PATH) as f:
            content = f.read()
            if 'mcp.run(transport="stdio")' not in content:
                issues.append(
                    "WARNING: MCP server should use stdio transport for security"
                )
    except Exception:
        pass

    # Check for input validation (MCP security requirement)
    validation_functions = [
        "_validate_alias",
        "_validate_command",
        "_validate_tag",
        "_validate_task_id",
    ]
    try:
        with open(MCP_SERVER_PATH) as f:
            content = f.read()
            for func in validation_functions:
                if func not in content:
                    issues.append(f"WARNING: Missing input validation function: {func}")
    except Exception:
        pass

    return issues


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

    # Extract tools from AST
    tools = extract_tools_from_ast()

    if not tools:
        print(
            "ERROR: Could not extract any tools from mcp_server.py",
            file=sys.stderr,
        )
        return 1

    print(f"Found {len(tools)} tools to validate...", file=sys.stderr)

    # Validate each tool
    all_errors = []
    for tool_name, tool_def in tools.items():
        errors = validate_tool(tool_def, schema, tool_name)
        all_errors.extend(errors)

    # Check MCP compliance
    compliance_issues = check_mcp_compliance()
    if compliance_issues:
        print("\nMCP Compliance Issues:", file=sys.stderr)
        for issue in compliance_issues:
            print(f"  - {issue}", file=sys.stderr)

    # Report results
    if all_errors:
        print("\nValidation errors found:", file=sys.stderr)
        for error in all_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"\n✓ All {len(tools)} tools validated successfully!", file=sys.stderr)
    if compliance_issues:
        print(
            "  (Some compliance warnings above, but schema validation passed)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

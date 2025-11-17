"""Tests for MCP specification compliance."""

import json
from unittest.mock import patch

from mcp_ssh import mcp_server
from mcp_ssh.tools.utilities import sanitize_error


def test_tool_error_response_format():
    """Verify tools return proper error format per MCP spec."""
    # Tools should return str for errors (FastMCP pattern)
    # Success responses return dict

    # Test error response (should be string)
    result = mcp_server.ssh_describe_host(alias="")  # Invalid alias
    assert isinstance(result, str)
    assert "Error:" in result or "error" in result.lower()

    # Test success response (should be dict)
    # This requires a valid config, so we'll test with a mock
    with patch.object(mcp_server.config, "get_host") as mock_get_host:
        mock_get_host.return_value = {
            "alias": "test1",
            "host": "10.0.0.1",
            "port": 22,
        }
        result = mcp_server.ssh_describe_host(alias="test1")
        assert isinstance(result, dict)
        assert "alias" in result


def test_error_sanitization_mcp_compliance():
    """Verify errors don't leak sensitive info per MCP security requirements."""
    # Test that sanitize_error removes sensitive information
    error_with_ip = "Connection failed to 192.168.1.100:22"
    sanitized = sanitize_error(error_with_ip)
    assert "192.168.1.100" not in sanitized
    assert "22" not in sanitized or "port" in sanitized.lower()

    error_with_path = "File not found: /app/keys/id_rsa"
    sanitized = sanitize_error(error_with_path)
    assert "/app/keys/id_rsa" not in sanitized
    assert "/" not in sanitized or sanitized.count("/") < error_with_path.count("/")

    error_with_hostname = "Cannot connect to web1.example.com"
    sanitized = sanitize_error(error_with_hostname)
    assert "web1.example.com" not in sanitized


def test_structured_logging_mcp_compliance():
    """Verify logging follows MCP patterns (structured JSON to stderr)."""
    import io
    import sys

    from mcp_ssh.tools.utilities import log_json

    # Capture stderr
    stderr_capture = io.StringIO()
    original_stderr = sys.stderr
    sys.stderr = stderr_capture

    try:
        # Log a test message
        log_json({"level": "info", "msg": "test_message", "test": True})

        # Get output
        output = stderr_capture.getvalue()

        # Should be valid JSON
        lines = output.strip().split("\n")
        for line in lines:
            if line.strip():
                parsed = json.loads(line)
                assert isinstance(parsed, dict)
                assert "msg" in parsed or "level" in parsed
    finally:
        sys.stderr = original_stderr


def test_fastmcp_error_handling():
    """Verify FastMCP error handling patterns."""
    # FastMCP tools should handle exceptions gracefully
    # and return string errors (not raise exceptions to MCP layer)

    # Test that invalid input returns error string, not exception
    result = mcp_server.ssh_run(alias="", command="")
    assert isinstance(result, str)
    assert "Error:" in result or "error" in result.lower()

    # Test that missing alias returns error string
    result = mcp_server.ssh_describe_host(alias="nonexistent")
    assert isinstance(result, str)
    assert "Error:" in result or "error" in result.lower()


def test_tool_return_types():
    """Verify all tools return proper types per MCP spec."""
    # Success: dict
    # Error: str

    # Test ping (always succeeds)
    result = mcp_server.ssh_ping()
    assert isinstance(result, dict)
    assert result == {"status": "pong"}

    # Test list_hosts (may succeed or fail)
    with patch.object(mcp_server.config, "list_hosts") as mock_list:
        mock_list.return_value = ["host1", "host2"]
        result = mcp_server.ssh_list_hosts()
        assert isinstance(result, dict)
        assert "hosts" in result

    # Test error case
    with patch.object(mcp_server.config, "list_hosts") as mock_list:
        mock_list.side_effect = Exception("Config error")
        result = mcp_server.ssh_list_hosts()
        assert isinstance(result, str)
        assert "Error:" in result or "error" in result.lower()


def test_error_messages_user_friendly():
    """Verify error messages are user-friendly and actionable."""
    # Error messages should be clear and actionable
    result = mcp_server.ssh_run(alias="", command="")
    assert isinstance(result, str)
    # Should contain helpful information
    assert "required" in result.lower() or "invalid" in result.lower()

    # Should not contain technical stack traces
    assert "Traceback" not in result
    assert 'File "' not in result
    assert ".py" not in result or "line" not in result


def test_no_sensitive_info_in_errors():
    """Verify no sensitive information in error messages."""
    # Test various error scenarios
    test_cases = [
        mcp_server.ssh_run(alias="", command=""),
        mcp_server.ssh_describe_host(alias=""),
        mcp_server.ssh_plan(alias="", command=""),
    ]

    sensitive_patterns = [
        "/app/",
        "/etc/",
        "/home/",
        "192.168.",
        "10.0.0.",
        "password",
        "secret",
        "key",
    ]

    for result in test_cases:
        if isinstance(result, str):
            result_lower = result.lower()
            # Check that sensitive patterns are not in error messages
            # (some may appear in sanitized form, which is acceptable)
            for pattern in sensitive_patterns:
                # If pattern appears, it should be in a sanitized context
                if pattern in result_lower:
                    # Should not be a full path or IP
                    assert not (
                        result_lower.count("/") > 2
                        or (pattern.startswith("192") and "." in result)
                    )

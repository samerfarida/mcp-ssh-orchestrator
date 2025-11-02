"""Tests for input validation in MCP server tools."""

from mcp_ssh import mcp_server


def test_validate_alias_valid():
    """Test that valid aliases pass validation."""
    # Valid aliases
    valid, msg = mcp_server._validate_alias("web1")
    assert valid is True
    assert msg == ""

    valid, msg = mcp_server._validate_alias("prod-web-1")
    assert valid is True

    valid, msg = mcp_server._validate_alias("db_server")
    assert valid is True

    valid, msg = mcp_server._validate_alias("server.example.com")
    assert valid is True


def test_validate_alias_empty():
    """Test that empty aliases are rejected."""
    valid, msg = mcp_server._validate_alias("")
    assert valid is False
    assert "required" in msg.lower()

    valid, msg = mcp_server._validate_alias("   ")
    assert valid is False
    assert "required" in msg.lower()


def test_validate_alias_too_long():
    """Test that aliases exceeding length limit are rejected."""
    long_alias = "a" * (mcp_server.MAX_ALIAS_LENGTH + 1)
    valid, msg = mcp_server._validate_alias(long_alias)
    assert valid is False
    assert "too long" in msg.lower()
    assert str(mcp_server.MAX_ALIAS_LENGTH) in msg


def test_validate_alias_invalid_characters():
    """Test that aliases with invalid characters are rejected."""
    # Special characters not allowed
    invalid_aliases = [
        "web@1",
        "web#1",
        "web$1",
        "web/1",
        "web\\1",
        "web 1",
        "web(1)",
        "web[1]",
        "web{1}",
        "web|1",
        "web&1",
    ]

    for alias in invalid_aliases:
        valid, msg = mcp_server._validate_alias(alias)
        assert valid is False, f"Alias '{alias}' should be rejected"
        assert "invalid characters" in msg.lower()


def test_validate_alias_at_limit():
    """Test that aliases at exactly the length limit are accepted."""
    alias_at_limit = "a" * mcp_server.MAX_ALIAS_LENGTH
    valid, msg = mcp_server._validate_alias(alias_at_limit)
    assert valid is True


def test_validate_command_valid():
    """Test that valid commands pass validation."""
    valid, msg = mcp_server._validate_command("uptime")
    assert valid is True
    assert msg == ""

    valid, msg = mcp_server._validate_command("df -h")
    assert valid is True

    valid, msg = mcp_server._validate_command("echo 'hello world'")
    assert valid is True

    # Commands with newlines (legitimate use case)
    valid, msg = mcp_server._validate_command("echo 'line1'\necho 'line2'")
    assert valid is True

    # Commands with tabs (legitimate use case)
    valid, msg = mcp_server._validate_command("echo 'line1'\techo 'line2'")
    assert valid is True


def test_validate_command_empty():
    """Test that empty commands are rejected."""
    valid, msg = mcp_server._validate_command("")
    assert valid is False
    assert "required" in msg.lower()

    valid, msg = mcp_server._validate_command("   ")
    assert valid is False
    assert "required" in msg.lower()


def test_validate_command_too_long():
    """Test that commands exceeding length limit are rejected."""
    long_command = "a" * (mcp_server.MAX_COMMAND_LENGTH + 1)
    valid, msg = mcp_server._validate_command(long_command)
    assert valid is False
    assert "too long" in msg.lower()
    assert str(mcp_server.MAX_COMMAND_LENGTH) in msg


def test_validate_command_at_limit():
    """Test that commands at exactly the length limit are accepted."""
    command_at_limit = "a" * mcp_server.MAX_COMMAND_LENGTH
    valid, msg = mcp_server._validate_command(command_at_limit)
    assert valid is True


def test_validate_command_null_bytes():
    """Test that commands with null bytes are rejected."""
    command_with_null = "echo\x00hello"
    valid, msg = mcp_server._validate_command(command_with_null)
    assert valid is False
    assert "null bytes" in msg.lower()


def test_validate_command_control_characters():
    """Test that commands with control characters are rejected."""
    # Control characters except newline, tab, carriage return
    invalid_commands = [
        "echo\x01hello",  # SOH
        "echo\x02hello",  # STX
        "echo\x03hello",  # ETX
        "echo\x04hello",  # EOT
        "echo\x05hello",  # ENQ
        "echo\x1bhello",  # ESC
    ]

    for cmd in invalid_commands:
        valid, msg = mcp_server._validate_command(cmd)
        assert (
            valid is False
        ), f"Command with control char should be rejected: {repr(cmd)}"
        assert "control characters" in msg.lower()


def test_validate_command_allowed_control_characters():
    """Test that newline, tab, and carriage return are allowed."""
    # These should be allowed for legitimate use
    valid, msg = mcp_server._validate_command("echo 'line1'\necho 'line2'")
    assert valid is True

    valid, msg = mcp_server._validate_command("echo 'line1'\techo 'line2'")
    assert valid is True

    valid, msg = mcp_server._validate_command("echo 'line1'\recho 'line2'")
    assert valid is True


def test_validate_tag_valid():
    """Test that valid tags pass validation."""
    valid, msg = mcp_server._validate_tag("web")
    assert valid is True
    assert msg == ""

    valid, msg = mcp_server._validate_tag("prod-web")
    assert valid is True

    valid, msg = mcp_server._validate_tag("db_server")
    assert valid is True

    valid, msg = mcp_server._validate_tag("server.example")
    assert valid is True


def test_validate_tag_empty():
    """Test that empty tags are rejected."""
    valid, msg = mcp_server._validate_tag("")
    assert valid is False
    assert "required" in msg.lower()

    valid, msg = mcp_server._validate_tag("   ")
    assert valid is False
    assert "required" in msg.lower()


def test_validate_tag_too_long():
    """Test that tags exceeding length limit are rejected."""
    long_tag = "a" * (mcp_server.MAX_TAG_LENGTH + 1)
    valid, msg = mcp_server._validate_tag(long_tag)
    assert valid is False
    assert "too long" in msg.lower()
    assert str(mcp_server.MAX_TAG_LENGTH) in msg


def test_validate_tag_invalid_characters():
    """Test that tags with invalid characters are rejected."""
    invalid_tags = ["web@1", "web#1", "web/1", "web 1"]

    for tag in invalid_tags:
        valid, msg = mcp_server._validate_tag(tag)
        assert valid is False, f"Tag '{tag}' should be rejected"
        assert "invalid characters" in msg.lower()


def test_validate_task_id_valid():
    """Test that valid task IDs pass validation."""
    valid, msg = mcp_server._validate_task_id("web1:abc123:1234567890")
    assert valid is True
    assert msg == ""

    valid, msg = mcp_server._validate_task_id("prod-web-1:def456:9876543210")
    assert valid is True


def test_validate_task_id_empty():
    """Test that empty task IDs are rejected."""
    valid, msg = mcp_server._validate_task_id("")
    assert valid is False
    assert "required" in msg.lower()

    valid, msg = mcp_server._validate_task_id("   ")
    assert valid is False
    assert "required" in msg.lower()


def test_validate_task_id_too_long():
    """Test that task IDs exceeding length limit are rejected."""
    long_task_id = "a" * (mcp_server.MAX_TASK_ID_LENGTH + 1)
    valid, msg = mcp_server._validate_task_id(long_task_id)
    assert valid is False
    assert "too long" in msg.lower()
    assert str(mcp_server.MAX_TASK_ID_LENGTH) in msg


def test_validate_task_id_invalid_characters():
    """Test that task IDs with invalid characters are rejected."""
    invalid_task_ids = [
        "web1@abc123:1234567890",
        "web1#abc123:1234567890",
        "web1/abc123:1234567890",
        "web1 abc123:1234567890",
    ]

    for task_id in invalid_task_ids:
        valid, msg = mcp_server._validate_task_id(task_id)
        assert valid is False, f"Task ID '{task_id}' should be rejected"
        assert "invalid characters" in msg.lower()


def test_validate_task_id_allowed_characters():
    """Test that task IDs with allowed characters pass validation."""
    # Colon is allowed (format: alias:hash:timestamp)
    valid, msg = mcp_server._validate_task_id("web1:abc123:1234567890")
    assert valid is True

    # Dash and underscore are allowed
    valid, msg = mcp_server._validate_task_id("prod-web_1:abc123:1234567890")
    assert valid is True

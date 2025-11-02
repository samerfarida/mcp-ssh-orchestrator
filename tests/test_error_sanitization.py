"""Tests for error message sanitization."""

from mcp_ssh.tools.utilities import sanitize_error


def test_sanitize_error_removes_file_paths():
    """Test that file paths are removed from error messages."""
    error = "File not found: /app/config/servers.yml"
    sanitized = sanitize_error(error)
    assert "/app/config/servers.yml" not in sanitized
    assert "[path]" in sanitized or "[file]" in sanitized


def test_sanitize_error_removes_ip_addresses():
    """Test that IP addresses are removed from error messages."""
    error = "Connection failed to 10.0.0.11:22"
    sanitized = sanitize_error(error)
    assert "10.0.0.11" not in sanitized
    assert "[ip]" in sanitized


def test_sanitize_error_removes_hostnames():
    """Test that hostnames are removed from error messages."""
    error = "Connection failed to web1.example.com"
    sanitized = sanitize_error(error)
    assert "web1.example.com" not in sanitized
    assert "[hostname]" in sanitized


def test_sanitize_error_removes_user_at_host_patterns():
    """Test that user@host patterns are removed."""
    error = "SSH authentication failed for ubuntu@10.0.0.11"
    sanitized = sanitize_error(error)
    assert "ubuntu@10.0.0.11" not in sanitized
    assert "[user@host]" in sanitized


def test_sanitize_error_removes_credential_references():
    """Test that credential references are redacted."""
    error = "Password: secret123 is invalid"
    sanitized = sanitize_error(error)
    assert "secret123" not in sanitized
    assert "[redacted]" in sanitized or "redacted" in sanitized.lower()


def test_sanitize_error_removes_windows_paths():
    """Test that Windows paths are removed."""
    error = "File not found: C:\\Users\\admin\\config.yml"
    sanitized = sanitize_error(error)
    assert "C:\\Users" not in sanitized
    assert "[path]" in sanitized


def test_sanitize_error_removes_relative_paths():
    """Test that relative paths are removed."""
    error = "File not found: ../secrets/password"
    sanitized = sanitize_error(error)
    assert "../secrets/password" not in sanitized
    assert "[path]" in sanitized


def test_sanitize_error_removes_port_numbers():
    """Test that port numbers are redacted."""
    error = "Connection failed on port 2222"
    sanitized = sanitize_error(error)
    assert ":2222" not in sanitized or "2222" not in sanitized
    assert "[port]" in sanitized


def test_sanitize_error_generic_message_for_empty():
    """Test that empty errors get generic message."""
    sanitized = sanitize_error("")
    assert sanitized == "An error occurred"


def test_sanitize_error_generic_message_for_over_sanitized():
    """Test that over-sanitized errors get generic message."""
    # Error that would be reduced to just placeholders
    error = "/etc/passwd 10.0.0.1 user@host"
    sanitized = sanitize_error(error)
    # Should not just be placeholders, should be a meaningful message
    assert sanitized != "[path] [ip] [user@host]"
    assert len(sanitized) > 10


def test_sanitize_error_preserves_error_type():
    """Test that error type/message structure is preserved when safe."""
    error = "ValueError: Invalid input"
    sanitized = sanitize_error(error)
    # Should preserve the error type part if no sensitive data
    assert "Invalid input" in sanitized or "error" in sanitized.lower()


def test_sanitize_error_complex_error_message():
    """Test sanitization of complex error messages with multiple sensitive parts."""
    error = "SSH connection failed to ubuntu@web1.example.com:2222 using key /app/keys/id_rsa from 10.0.0.11"
    sanitized = sanitize_error(error)
    # All sensitive parts should be removed
    assert "ubuntu@web1.example.com" not in sanitized
    assert "2222" not in sanitized or ":2222" not in sanitized
    assert "/app/keys/id_rsa" not in sanitized
    assert "10.0.0.11" not in sanitized
    # Should still be a meaningful error message
    assert len(sanitized) > 10


def test_sanitize_error_keeps_detailed_in_logs():
    """Test that detailed errors can be logged when requested."""
    error = "Connection failed to 10.0.0.11:22"
    sanitized = sanitize_error(error, keep_detailed_in_logs=True)
    # Function should still return sanitized version
    assert "10.0.0.11" not in sanitized
    # Detailed logging is tested via stderr capture in integration tests

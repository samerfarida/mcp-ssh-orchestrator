"""Tests for utility functions."""

from mcp_ssh.tools.utilities import hash_command


def test_hash_command_length():
    """Test that hash_command returns 16-character hash."""
    command = "test command"
    hash_value = hash_command(command)

    assert len(hash_value) == 16
    assert isinstance(hash_value, str)
    # Should be hexadecimal
    assert all(c in "0123456789abcdef" for c in hash_value)


def test_hash_command_consistency():
    """Test that same command produces same hash."""
    command = "uptime"
    hash1 = hash_command(command)
    hash2 = hash_command(command)

    assert hash1 == hash2
    assert len(hash1) == 16


def test_hash_command_uniqueness():
    """Test that different commands produce different hashes."""
    command1 = "uptime"
    command2 = "whoami"
    hash1 = hash_command(command1)
    hash2 = hash_command(command2)

    assert hash1 != hash2
    assert len(hash1) == 16
    assert len(hash2) == 16


def test_hash_command_empty():
    """Test that empty command produces valid hash."""
    hash_value = hash_command("")
    assert len(hash_value) == 16
    assert isinstance(hash_value, str)


def test_hash_command_none():
    """Test that None command produces valid hash."""
    hash_value = hash_command(None)  # type: ignore
    assert len(hash_value) == 16
    assert isinstance(hash_value, str)

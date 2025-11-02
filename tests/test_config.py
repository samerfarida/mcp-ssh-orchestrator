"""Tests for configuration loading and credential resolution."""

import os
import tempfile

import pytest
import yaml

from mcp_ssh.config import (
    Config,
    _resolve_key_path,
    _resolve_secret,
    _validate_file_path,
)


@pytest.fixture
def temp_config_dir():
    """Create temporary config directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test servers.yml
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["web", "prod"],
                },
                {
                    "alias": "test2",
                    "host": "10.0.0.2",
                    "port": 2222,
                    "credentials": "cred2",
                    "tags": ["db"],
                },
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        # Create test credentials.yml
        credentials = {
            "entries": [
                {
                    "name": "cred1",
                    "username": "user1",
                    "key_path": "id_ed25519",
                    "password_secret": "",
                    "key_passphrase_secret": "",
                },
                {
                    "name": "cred2",
                    "username": "user2",
                    "key_path": "",
                    "password_secret": "db_password",
                    "key_passphrase_secret": "",
                },
            ]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        # Create test policy.yml
        policy = {
            "limits": {"max_seconds": 60, "max_output_bytes": 1048576},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "commands": ["uptime*"],
                },
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        yield tmpdir


def test_config_load(temp_config_dir):
    """Test loading configuration files."""
    config = Config(config_dir=temp_config_dir)

    hosts = config.list_hosts()
    assert len(hosts) == 2
    assert "test1" in hosts
    assert "test2" in hosts


def test_get_host(temp_config_dir):
    """Test getting host by alias."""
    config = Config(config_dir=temp_config_dir)

    host = config.get_host("test1")
    assert host["host"] == "10.0.0.1"
    assert host["port"] == 22
    assert host["credentials"] == "cred1"


def test_get_host_not_found(temp_config_dir):
    """Test getting non-existent host."""
    config = Config(config_dir=temp_config_dir)

    with pytest.raises(ValueError, match="Host alias not found"):
        config.get_host("nonexistent")


def test_get_host_tags(temp_config_dir):
    """Test getting host tags."""
    config = Config(config_dir=temp_config_dir)

    tags = config.get_host_tags("test1")
    assert tags == ["web", "prod"]

    tags2 = config.get_host_tags("test2")
    assert tags2 == ["db"]


def test_find_hosts_by_tag(temp_config_dir):
    """Test finding hosts by tag."""
    config = Config(config_dir=temp_config_dir)

    web_hosts = config.find_hosts_by_tag("web")
    assert web_hosts == ["test1"]

    prod_hosts = config.find_hosts_by_tag("prod")
    assert prod_hosts == ["test1"]

    db_hosts = config.find_hosts_by_tag("db")
    assert db_hosts == ["test2"]

    no_hosts = config.find_hosts_by_tag("nonexistent")
    assert no_hosts == []


def test_get_credentials(temp_config_dir):
    """Test getting credentials."""
    config = Config(
        config_dir=temp_config_dir, keys_dir="/app/keys", secrets_dir="/app/secrets"
    )

    creds = config.get_credentials("cred1")
    assert creds["username"] == "user1"
    assert creds["key_path"] == "/app/keys/id_ed25519"
    assert creds["password"] == ""


def test_get_credentials_not_found(temp_config_dir):
    """Test getting non-existent credentials."""
    config = Config(config_dir=temp_config_dir)

    creds = config.get_credentials("nonexistent")
    assert creds == {}


def test_get_policy(temp_config_dir):
    """Test getting policy."""
    config = Config(config_dir=temp_config_dir)

    policy = config.get_policy()
    assert policy["limits"]["max_seconds"] == 60
    assert len(policy["rules"]) == 1


def test_reload_config(temp_config_dir):
    """Test reloading configuration."""
    config = Config(config_dir=temp_config_dir)

    # Initial state
    hosts = config.list_hosts()
    assert len(hosts) == 2

    # Modify servers.yml
    servers = {
        "hosts": [
            {
                "alias": "test3",
                "host": "10.0.0.3",
                "port": 22,
                "credentials": "cred1",
                "tags": [],
            },
        ]
    }
    with open(os.path.join(temp_config_dir, "servers.yml"), "w") as f:
        yaml.dump(servers, f)

    # Reload
    config.reload()

    # Verify change
    hosts = config.list_hosts()
    assert len(hosts) == 1
    assert "test3" in hosts


def test_resolve_secret_from_env(monkeypatch):
    """Test resolving secret from environment variable."""
    monkeypatch.setenv("MCP_SSH_SECRET_TEST_PASSWORD", "env-password")

    secret = _resolve_secret("test_password")
    assert secret == "env-password"


def test_resolve_secret_from_file():
    """Test resolving secret from file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        secret_path = os.path.join(tmpdir, "test_secret")
        with open(secret_path, "w") as f:
            f.write("file-secret")

        secret = _resolve_secret("test_secret", secrets_dir=tmpdir)
        assert secret == "file-secret"


def test_resolve_secret_not_found():
    """Test resolving non-existent secret."""
    with tempfile.TemporaryDirectory() as tmpdir:
        secret = _resolve_secret("nonexistent", secrets_dir=tmpdir)
        assert secret == ""


def test_resolve_secret_path_traversal_forward_slash():
    """Test that path traversal with ../ is blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a secret file
        secret_path = os.path.join(tmpdir, "valid_secret")
        with open(secret_path, "w") as f:
            f.write("valid-secret")

        # Create a file outside the secrets directory
        parent_dir = os.path.dirname(tmpdir)
        outside_file = os.path.join(parent_dir, "outside_secret")
        with open(outside_file, "w") as f:
            f.write("outside-secret")

        # Try to access it via path traversal
        result = _resolve_secret("../outside_secret", secrets_dir=tmpdir)
        assert result == ""

        # Clean up
        os.remove(outside_file)


def test_resolve_secret_path_traversal_backslash():
    """Test that path traversal with ..\\ is blocked on Windows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a secret file
        secret_path = os.path.join(tmpdir, "valid_secret")
        with open(secret_path, "w") as f:
            f.write("valid-secret")

        # Try path traversal with backslash (Windows style)
        # Note: os.path.normpath will normalize this on any OS
        result = _resolve_secret("..\\outside_secret", secrets_dir=tmpdir)
        assert result == ""


def test_resolve_secret_absolute_path_rejection():
    """Test that absolute paths are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file at an absolute path
        if os.name == "nt":
            absolute_path = "C:\\Windows\\System32\\secret"
        else:
            absolute_path = "/etc/passwd"

        # Try to use absolute path as secret name
        result = _resolve_secret(absolute_path, secrets_dir=tmpdir)
        assert result == ""


def test_resolve_secret_special_characters_rejection():
    """Test that secret names with special characters are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test various special characters
        invalid_names = [
            "secret/name",
            "secret.name",
            "secret name",
            "secret@name",
            "secret#name",
            "secret$name",
            "secret%name",
            "secret&name",
            "secret*name",
            "secret+name",
            "secret=name",
            "secret?name",
            "secret|name",
            "secret<name",
            "secret>name",
        ]

        for invalid_name in invalid_names:
            result = _resolve_secret(invalid_name, secrets_dir=tmpdir)
            assert result == "", f"Should reject secret name: {invalid_name}"


def test_resolve_secret_valid_characters_allowed():
    """Test that valid characters (alphanumeric, dash, underscore) are allowed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        valid_names = [
            "secret123",
            "secret-name",
            "secret_name",
            "SECRET_NAME",
            "secret123_name-test",
            "a1b2c3",
        ]

        for valid_name in valid_names:
            secret_path = os.path.join(tmpdir, valid_name)
            with open(secret_path, "w") as f:
                f.write(f"content-{valid_name}")

            result = _resolve_secret(valid_name, secrets_dir=tmpdir)
            assert (
                result == f"content-{valid_name}"
            ), f"Should allow secret name: {valid_name}"


def test_resolve_secret_multiple_traversal_attempts():
    """Test multiple levels of path traversal are blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a nested structure
        nested_dir = os.path.join(tmpdir, "nested", "deep")
        os.makedirs(nested_dir, exist_ok=True)

        # Create file in nested dir
        nested_file = os.path.join(nested_dir, "nested_secret")
        with open(nested_file, "w") as f:
            f.write("nested-secret")

        # Try multiple traversal levels
        traversal_attempts = [
            "../../outside",
            "../../../etc/passwd",
            "....//....//etc/passwd",
        ]

        for attempt in traversal_attempts:
            result = _resolve_secret(attempt, secrets_dir=nested_dir)
            assert result == "", f"Should block traversal: {attempt}"


def test_resolve_secret_normal_file_access_still_works():
    """Test that normal file access still works after security fixes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a valid secret file
        secret_path = os.path.join(tmpdir, "valid_secret")
        with open(secret_path, "w") as f:
            f.write("valid-secret-content")

        # Should still work
        result = _resolve_secret("valid_secret", secrets_dir=tmpdir)
        assert result == "valid-secret-content"


def test_resolve_key_path_relative():
    """Test resolving relative key path."""
    path = _resolve_key_path("id_ed25519", keys_dir="/app/keys")
    assert path == "/app/keys/id_ed25519"


def test_resolve_key_path_absolute_within_keys_dir():
    """Test resolving absolute key path within keys_dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a key file
        key_file = os.path.join(tmpdir, "test_key")
        with open(key_file, "w") as f:
            f.write("test key content")

        # Absolute path within keys_dir should work
        path = _resolve_key_path(key_file, keys_dir=tmpdir)
        assert path == os.path.abspath(key_file)


def test_resolve_key_path_absolute_outside_keys_dir():
    """Test that absolute paths outside keys_dir are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a key file outside keys_dir
        parent_dir = os.path.dirname(tmpdir)
        outside_key = os.path.join(parent_dir, "outside_key")
        with open(outside_key, "w") as f:
            f.write("outside key")

        # Absolute path outside keys_dir should be rejected
        path = _resolve_key_path(outside_key, keys_dir=tmpdir)
        assert path == ""

        # Clean up
        os.remove(outside_key)


def test_resolve_key_path_empty():
    """Test resolving empty key path."""
    path = _resolve_key_path("", keys_dir="/app/keys")
    assert path == ""


def test_resolve_key_path_traversal_forward_slash():
    """Test that path traversal with ../ is blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a key file
        key_path = os.path.join(tmpdir, "valid_key")
        with open(key_path, "w") as f:
            f.write("valid-key")

        # Create a file outside the keys directory
        parent_dir = os.path.dirname(tmpdir)
        outside_file = os.path.join(parent_dir, "outside_key")
        with open(outside_file, "w") as f:
            f.write("outside-key")

        # Try to access it via path traversal
        result = _resolve_key_path("../outside_key", keys_dir=tmpdir)
        assert result == ""

        # Clean up
        os.remove(outside_file)


def test_resolve_key_path_traversal_backslash():
    """Test that path traversal with ..\\ is blocked on Windows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a key file
        key_path = os.path.join(tmpdir, "valid_key")
        with open(key_path, "w") as f:
            f.write("valid-key")

        # Try path traversal with backslash (Windows style)
        # Note: os.path.normpath will normalize this on any OS
        result = _resolve_key_path("..\\outside_key", keys_dir=tmpdir)
        assert result == ""


def test_resolve_key_path_multiple_traversal_attempts():
    """Test multiple levels of path traversal are blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a nested structure
        nested_dir = os.path.join(tmpdir, "nested", "deep")
        os.makedirs(nested_dir, exist_ok=True)

        # Create file in nested dir
        nested_file = os.path.join(nested_dir, "nested_key")
        with open(nested_file, "w") as f:
            f.write("nested-key")

        # Try multiple traversal levels
        traversal_attempts = [
            "../../outside",
            "../../../etc/passwd",
            "....//....//etc/passwd",
        ]

        for attempt in traversal_attempts:
            result = _resolve_key_path(attempt, keys_dir=nested_dir)
            assert result == "", f"Should block traversal: {attempt}"


def test_resolve_key_path_normal_file_access_still_works():
    """Test that normal file access still works after security fixes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a valid key file
        key_path = os.path.join(tmpdir, "valid_key")
        with open(key_path, "w") as f:
            f.write("valid-key-content")

        # Relative path should still work
        result = _resolve_key_path("valid_key", keys_dir=tmpdir)
        assert result == os.path.abspath(key_path)

        # Absolute path within keys_dir should still work
        result2 = _resolve_key_path(key_path, keys_dir=tmpdir)
        assert result2 == os.path.abspath(key_path)


def test_resolve_key_path_absolute_same_as_keys_dir():
    """Test that absolute path pointing to keys_dir itself is rejected (not a file)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Absolute path to keys_dir itself should be rejected (it's a directory, not a file)
        result = _resolve_key_path(tmpdir, keys_dir=tmpdir)
        assert result == ""


def test_validate_file_path_directory_rejection():
    """Test that directory paths are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a subdirectory
        subdir = os.path.join(tmpdir, "subdir")
        os.makedirs(subdir, exist_ok=True)

        # Directory should be rejected
        result = _validate_file_path(subdir, tmpdir)
        assert result is False


def test_validate_file_path_symlink_rejection():
    """Test that symlinks are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a regular file
        target_file = os.path.join(tmpdir, "target_file")
        with open(target_file, "w") as f:
            f.write("target content")

        # Create a symlink to the target
        symlink_path = os.path.join(tmpdir, "symlink")
        os.symlink(target_file, symlink_path)

        # Symlink should be rejected
        result = _validate_file_path(symlink_path, tmpdir)
        assert result is False


def test_validate_file_path_non_existent():
    """Test that non-existent files are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Non-existent file should be rejected
        nonexistent = os.path.join(tmpdir, "nonexistent_file")
        result = _validate_file_path(nonexistent, tmpdir)
        assert result is False


def test_validate_file_path_outside_directory():
    """Test that files outside allowed directory are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file outside the allowed directory
        parent_dir = os.path.dirname(tmpdir)
        outside_file = os.path.join(parent_dir, "outside_file")
        with open(outside_file, "w") as f:
            f.write("outside content")

        try:
            # File outside directory should be rejected
            result = _validate_file_path(outside_file, tmpdir)
            assert result is False
        finally:
            # Clean up
            os.remove(outside_file)


def test_validate_file_path_regular_file_allowed():
    """Test that regular files within allowed directory are allowed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a regular file
        regular_file = os.path.join(tmpdir, "regular_file")
        with open(regular_file, "w") as f:
            f.write("file content")

        # Regular file should be allowed
        result = _validate_file_path(regular_file, tmpdir)
        assert result is True


def test_resolve_secret_directory_rejection():
    """Test that secret resolution rejects directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a subdirectory (not a file)
        subdir = os.path.join(tmpdir, "subdir")
        os.makedirs(subdir, exist_ok=True)

        # Try to resolve a directory as a secret (should fail)
        result = _resolve_secret("subdir", secrets_dir=tmpdir)
        assert result == ""


def test_resolve_secret_symlink_rejection():
    """Test that secret resolution rejects symlinks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a target secret file
        target_secret = os.path.join(tmpdir, "target_secret")
        with open(target_secret, "w") as f:
            f.write("target-secret")

        # Create a symlink
        symlink_name = "symlink_secret"
        symlink_path = os.path.join(tmpdir, symlink_name)
        os.symlink(target_secret, symlink_path)

        # Symlink should be rejected
        result = _resolve_secret(symlink_name, secrets_dir=tmpdir)
        assert result == ""


def test_resolve_key_path_directory_rejection():
    """Test that key path resolution rejects directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a subdirectory (not a file)
        subdir = os.path.join(tmpdir, "subdir")
        os.makedirs(subdir, exist_ok=True)

        # Try to resolve a directory as a key path (should fail)
        result = _resolve_key_path("subdir", keys_dir=tmpdir)
        assert result == ""


def test_resolve_key_path_symlink_rejection():
    """Test that key path resolution rejects symlinks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a target key file
        target_key = os.path.join(tmpdir, "target_key")
        with open(target_key, "w") as f:
            f.write("target-key")

        # Create a symlink
        symlink_name = "symlink_key"
        symlink_path = os.path.join(tmpdir, symlink_name)
        os.symlink(target_key, symlink_path)

        # Symlink should be rejected
        result = _resolve_key_path(symlink_name, keys_dir=tmpdir)
        assert result == ""


def test_resolve_secret_regular_file_still_works():
    """Test that regular files still work after adding file validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a regular secret file
        secret_path = os.path.join(tmpdir, "valid_secret")
        with open(secret_path, "w") as f:
            f.write("valid-secret-content")

        # Regular file should still work
        result = _resolve_secret("valid_secret", secrets_dir=tmpdir)
        assert result == "valid-secret-content"


def test_resolve_key_path_regular_file_still_works():
    """Test that regular files still work after adding file validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a regular key file
        key_path = os.path.join(tmpdir, "valid_key")
        with open(key_path, "w") as f:
            f.write("valid-key-content")

        # Regular file should still work (relative path)
        result = _resolve_key_path("valid_key", keys_dir=tmpdir)
        assert result == os.path.abspath(key_path)

        # Regular file should still work (absolute path)
        result2 = _resolve_key_path(key_path, keys_dir=tmpdir)
        assert result2 == os.path.abspath(key_path)

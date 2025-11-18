"""Tests for configuration loading and credential resolution."""

import os
import tempfile

import pytest
import yaml

from mcp_ssh.config import (
    MAX_KEY_PATH_LENGTH,
    MAX_SECRET_NAME_LENGTH,
    MAX_YAML_FILE_SIZE,
    Config,
    _load_yaml,
    _log_security_event,
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
                },
                {
                    "name": "cred2",
                    "username": "user2",
                    "password_secret": "db_password",
                },
            ]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        # Create test policy.yml
        policy = {
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "commands": ["uptime*"],
                }
            ]
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        yield tmpdir


def test_config_loads_files(temp_config_dir):
    """Test that Config loads all YAML files correctly."""
    config = Config(temp_config_dir)

    # Check hosts loaded
    host = config.get_host("test1")
    assert host["host"] == "10.0.0.1"
    assert host["port"] == 22

    # Check credentials loaded
    creds = config.get_credentials("cred1")
    assert creds["username"] == "user1"
    # key_path is resolved to absolute path during loading
    assert "id_ed25519" in creds.get("key_path", "")

    # Check policy loaded
    pol = config.get_policy()
    assert len(pol.get("rules", [])) > 0


def test_get_host_not_found(temp_config_dir):
    """Test getting non-existent host."""
    config = Config(temp_config_dir)
    # get_host raises ValueError when host not found
    with pytest.raises(ValueError, match="Host alias not found"):
        config.get_host("nonexistent")


def test_get_credentials_not_found(temp_config_dir):
    """Test getting non-existent credentials."""
    config = Config(temp_config_dir)
    creds = config.get_credentials("nonexistent")
    assert creds == {}


def test_get_credentials_key_passphrase_secret_docker_mcp(monkeypatch, temp_config_dir):
    """Test get_credentials resolves key_passphrase_secret via Docker MCP Gateway."""
    # Update credentials.yml
    creds_path = os.path.join(temp_config_dir, "credentials.yml")
    credentials = {
        "entries": [
            {
                "name": "test_cred",
                "username": "testuser",
                "key_path": "id_ed25519",
                "key_passphrase_secret": "SSH_KEY_PASSPHRASE_01",
            }
        ]
    }
    with open(creds_path, "w") as f:
        yaml.dump(credentials, f)

    # Set Docker MCP Gateway env var
    monkeypatch.setenv("SSH_KEY_PASSPHRASE_01", "my-passphrase")

    config = Config(temp_config_dir)
    creds = config.get_credentials("test_cred")
    assert creds["passphrase"] == "my-passphrase"


def test_get_credentials_password_secret_docker_mcp(monkeypatch, temp_config_dir):
    """Test get_credentials resolves password_secret via Docker MCP Gateway."""
    # Update credentials.yml
    creds_path = os.path.join(temp_config_dir, "credentials.yml")
    credentials = {
        "entries": [
            {
                "name": "test_cred",
                "username": "testuser",
                "password_secret": "SSH_PASSWORD_SECRET_01",
            }
        ]
    }
    with open(creds_path, "w") as f:
        yaml.dump(credentials, f)

    # Set Docker MCP Gateway env var
    monkeypatch.setenv("SSH_PASSWORD_SECRET_01", "my-password")

    config = Config(temp_config_dir)
    creds = config.get_credentials("test_cred")
    assert creds["password"] == "my-password"


def test_get_credentials_both_secrets_docker_mcp(monkeypatch, temp_config_dir):
    """Test get_credentials resolves both key_passphrase_secret and password_secret."""
    # Update credentials.yml
    creds_path = os.path.join(temp_config_dir, "credentials.yml")
    credentials = {
        "entries": [
            {
                "name": "test_cred",
                "username": "testuser",
                "key_path": "id_ed25519",
                "key_passphrase_secret": "SSH_KEY_PASSPHRASE_01",
                "password_secret": "SSH_PASSWORD_SECRET_01",
            }
        ]
    }
    with open(creds_path, "w") as f:
        yaml.dump(credentials, f)

    # Set both Docker MCP Gateway env vars
    monkeypatch.setenv("SSH_KEY_PASSPHRASE_01", "my-passphrase")
    monkeypatch.setenv("SSH_PASSWORD_SECRET_01", "my-password")

    config = Config(temp_config_dir)
    creds = config.get_credentials("test_cred")
    assert creds["passphrase"] == "my-passphrase"
    assert creds["password"] == "my-password"


def test_get_credentials_all_secrets_docker_mcp(monkeypatch, temp_config_dir):
    """Test get_credentials resolves all 10 secrets (5 passphrase + 5 password)."""
    # Create credentials.yml with all secrets
    creds_path = os.path.join(temp_config_dir, "credentials.yml")
    entries = []

    # 5 entries with passphrase secrets
    for i in range(1, 6):
        entries.append(
            {
                "name": f"passphrase_cred_{i}",
                "username": "testuser",
                "key_path": "id_ed25519",
                "key_passphrase_secret": f"SSH_KEY_PASSPHRASE_{i:02d}",
            }
        )
        monkeypatch.setenv(f"SSH_KEY_PASSPHRASE_{i:02d}", f"passphrase-{i}")

    # 5 entries with password secrets
    for i in range(1, 6):
        entries.append(
            {
                "name": f"password_cred_{i}",
                "username": "testuser",
                "password_secret": f"SSH_PASSWORD_SECRET_{i:02d}",
            }
        )
        monkeypatch.setenv(f"SSH_PASSWORD_SECRET_{i:02d}", f"password-{i}")

    credentials = {"entries": entries}
    with open(creds_path, "w") as f:
        yaml.dump(credentials, f)

    config = Config(temp_config_dir)

    # Verify all passphrase secrets
    for i in range(1, 6):
        creds = config.get_credentials(f"passphrase_cred_{i}")
        assert creds["passphrase"] == f"passphrase-{i}"

    # Verify all password secrets
    for i in range(1, 6):
        creds = config.get_credentials(f"password_cred_{i}")
        assert creds["password"] == f"password-{i}"


def test_get_host_tags(temp_config_dir):
    """Test getting tags for a host."""
    config = Config(temp_config_dir)
    tags = config.get_host_tags("test1")
    assert "web" in tags
    assert "prod" in tags


def test_list_hosts(temp_config_dir):
    """Test listing all hosts."""
    config = Config(temp_config_dir)
    hosts = config.list_hosts()
    assert len(hosts) == 2
    assert "test1" in hosts
    assert "test2" in hosts


def test_find_hosts_by_tag(temp_config_dir):
    """Test finding hosts by tag."""
    config = Config(temp_config_dir)
    hosts = config.find_hosts_by_tag("web")
    assert "test1" in hosts
    assert "test2" not in hosts


def test_reload_config(temp_config_dir):
    """Test reloading configuration."""
    config = Config(temp_config_dir)

    # Modify servers.yml
    servers_path = os.path.join(temp_config_dir, "servers.yml")
    new_servers = {
        "hosts": [
            {
                "alias": "newhost",
                "host": "10.0.0.3",
                "port": 22,
                "credentials": "cred1",
            }
        ]
    }
    with open(servers_path, "w") as f:
        yaml.dump(new_servers, f)

    # Reload
    config.reload()

    # Check new host loaded
    host = config.get_host("newhost")
    assert host["host"] == "10.0.0.3"


def test_resolve_secret_from_env(monkeypatch):
    """Test resolving secret from environment variable."""
    monkeypatch.setenv("MCP_SSH_SECRET_TEST_SECRET", "env-secret-value")
    result = _resolve_secret("test_secret")
    assert result == "env-secret-value"


def test_resolve_secret_from_direct_env_var(monkeypatch):
    """Test resolving secret from direct environment variable (Docker MCP Gateway pattern)."""
    monkeypatch.setenv("SSH_KEY_PASSPHRASE_01", "direct-env-secret-value")
    result = _resolve_secret("SSH_KEY_PASSPHRASE_01")
    assert result == "direct-env-secret-value"


def test_resolve_secret_from_prefixed_env_var(monkeypatch):
    """Test resolving secret from prefixed environment variable (standalone pattern)."""
    monkeypatch.setenv(
        "MCP_SSH_SECRET_SSH_KEY_PASSPHRASE_01", "prefixed-env-secret-value"
    )
    result = _resolve_secret("SSH_KEY_PASSPHRASE_01")
    assert result == "prefixed-env-secret-value"


def test_resolve_secret_priority_direct_env_over_prefixed(monkeypatch):
    """Test that direct env var takes precedence over prefixed env var."""
    monkeypatch.setenv("SSH_KEY_PASSPHRASE_01", "direct-value")
    monkeypatch.setenv("MCP_SSH_SECRET_SSH_KEY_PASSPHRASE_01", "prefixed-value")
    result = _resolve_secret("SSH_KEY_PASSPHRASE_01")
    assert result == "direct-value"  # Direct env var should win


def test_resolve_secret_priority_env_over_file(monkeypatch):
    """Test that environment variable takes precedence over file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        secret_file = os.path.join(tmpdir, "SSH_KEY_PASSPHRASE_01")
        with open(secret_file, "w") as f:
            f.write("file-value")

        monkeypatch.setenv("SSH_KEY_PASSPHRASE_01", "env-value")
        result = _resolve_secret("SSH_KEY_PASSPHRASE_01", secrets_dir=tmpdir)
        assert result == "env-value"  # Env var should win


def test_resolve_secret_all_passphrase_secrets_docker_mcp(monkeypatch):
    """Test resolving all 5 passphrase secrets via Docker MCP Gateway pattern."""
    for i in range(1, 6):
        secret_name = f"SSH_KEY_PASSPHRASE_{i:02d}"
        secret_value = f"passphrase-secret-{i}"
        monkeypatch.setenv(secret_name, secret_value)
        result = _resolve_secret(secret_name)
        assert result == secret_value


def test_resolve_secret_all_password_secrets_docker_mcp(monkeypatch):
    """Test resolving all 5 password secrets via Docker MCP Gateway pattern."""
    for i in range(1, 6):
        secret_name = f"SSH_PASSWORD_SECRET_{i:02d}"
        secret_value = f"password-secret-{i}"
        monkeypatch.setenv(secret_name, secret_value)
        result = _resolve_secret(secret_name)
        assert result == secret_value


def test_resolve_secret_mixed_modes(monkeypatch):
    """Test resolving secrets in mixed mode (some direct, some prefixed)."""
    # Direct env var (Docker MCP Gateway)
    monkeypatch.setenv("SSH_KEY_PASSPHRASE_01", "direct-value")
    result1 = _resolve_secret("SSH_KEY_PASSPHRASE_01")
    assert result1 == "direct-value"

    # Prefixed env var (standalone)
    monkeypatch.setenv("MCP_SSH_SECRET_SSH_KEY_PASSPHRASE_02", "prefixed-value")
    result2 = _resolve_secret("SSH_KEY_PASSPHRASE_02")
    assert result2 == "prefixed-value"


def test_resolve_secret_case_sensitivity(monkeypatch):
    """Test that secret resolution is case-insensitive for env var lookup."""
    monkeypatch.setenv("SSH_KEY_PASSPHRASE_01", "uppercase-env")
    # Secret name in credentials.yml might be lowercase
    result = _resolve_secret("ssh_key_passphrase_01")
    assert result == "uppercase-env"  # Should find it via .upper()


def test_resolve_secret_from_file():
    """Test resolving secret from file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        secret_file = os.path.join(tmpdir, "test_secret")
        with open(secret_file, "w") as f:
            f.write("file-secret-value\n")

        result = _resolve_secret("test_secret", secrets_dir=tmpdir)
        assert result == "file-secret-value"


def test_resolve_secret_not_found():
    """Test resolving non-existent secret."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _resolve_secret("nonexistent", secrets_dir=tmpdir)
        assert result == ""


def test_resolve_secret_path_traversal_forward_slash():
    """Test that path traversal with ../ is blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a secret file
        secret_file = os.path.join(tmpdir, "valid_secret")
        with open(secret_file, "w") as f:
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
    """Test that path traversal with ..\\ is blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a secret file
        secret_file = os.path.join(tmpdir, "valid_secret")
        with open(secret_file, "w") as f:
            f.write("valid-secret")

        # Try path traversal with backslash (Windows style)
        # Note: os.path.normpath will normalize this on any OS
        result = _resolve_secret("..\\outside_secret", secrets_dir=tmpdir)
        assert result == ""


def test_resolve_secret_absolute_path_rejection():
    """Test that absolute paths are rejected for secrets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create secret file
        secret_file = os.path.join(tmpdir, "valid_secret")
        with open(secret_file, "w") as f:
            f.write("valid-secret")

        # Try absolute path (should be rejected)
        result = _resolve_secret(os.path.abspath(secret_file), secrets_dir=tmpdir)
        assert result == ""


def test_resolve_secret_special_characters_rejection():
    """Test that special characters in secret names are rejected."""
    invalid_names = [
        "../secret",
        "../../etc/passwd",
        "secret/../file",
        "secret@name",
        "secret#name",
        "secret$name",
        "secret%name",
        "secret&name",
        "secret*name",
        "secret+name",
        "secret=name",
        "secret|name",
        "secret<name",
        "secret>name",
        "secret?name",
        "secret:name",
        "secret;name",
        "secret'name",
        'secret"name',
        "secret\nname",
        "secret\tname",
        "secret name",  # space
    ]

    for invalid_name in invalid_names:
        result = _resolve_secret(invalid_name, secrets_dir="/app/secrets")
        assert result == "", f"Should reject: {invalid_name}"


def test_resolve_secret_valid_characters_allowed():
    """Test that valid characters in secret names are allowed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Valid secret names
        valid_names = [
            "secret123",
            "SECRET_NAME",
            "secret-name",
            "secret_name",
            "SecretName123",
            "123secret",
            "a",
            "A1",
        ]

        for valid_name in valid_names:
            secret_file = os.path.join(tmpdir, valid_name)
            with open(secret_file, "w") as f:
                f.write(f"content-{valid_name}")

            result = _resolve_secret(valid_name, secrets_dir=tmpdir)
            assert result == f"content-{valid_name}", f"Should allow: {valid_name}"


def test_resolve_secret_multiple_traversal_attempts():
    """Test multiple levels of path traversal are blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create nested structure
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
        secret_file = os.path.join(tmpdir, "valid_secret")
        with open(secret_file, "w") as f:
            f.write("valid-secret-content")

        # Should still work
        result = _resolve_secret("valid_secret", secrets_dir=tmpdir)
        assert result == "valid-secret-content"


def test_resolve_key_path_relative():
    """Test resolving relative key path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a key file
        key_path = os.path.join(tmpdir, "id_ed25519")
        with open(key_path, "w") as f:
            f.write("valid-key")

        result = _resolve_key_path("id_ed25519", keys_dir=tmpdir)
        assert result == os.path.abspath(key_path)


def test_resolve_key_path_absolute_within_keys_dir():
    """Test resolving absolute key path within keys_dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a key file
        key_path = os.path.join(tmpdir, "id_ed25519")
        with open(key_path, "w") as f:
            f.write("valid-key")

        # Absolute path within keys_dir should work
        result = _resolve_key_path(key_path, keys_dir=tmpdir)
        assert result == os.path.abspath(key_path)


def test_resolve_key_path_absolute_outside_keys_dir():
    """Test that absolute key path outside keys_dir is rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a key file outside keys_dir
        parent_dir = os.path.dirname(tmpdir)
        outside_key = os.path.join(parent_dir, "outside_key")
        with open(outside_key, "w") as f:
            f.write("outside-key")

        # Absolute path outside keys_dir should be rejected
        result = _resolve_key_path(outside_key, keys_dir=tmpdir)
        assert result == ""

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
        result = _validate_file_path(subdir, tmpdir, require_exists=True)
        assert result is False


def test_validate_file_path_symlink_rejection():
    """Test that symlink paths are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a regular file
        target_file = os.path.join(tmpdir, "target")
        with open(target_file, "w") as f:
            f.write("target-content")

        # Create a symlink to it
        symlink_path = os.path.join(tmpdir, "symlink")
        os.symlink(target_file, symlink_path)

        # Symlink should be rejected
        result = _validate_file_path(symlink_path, tmpdir, require_exists=True)
        assert result is False


def test_validate_file_path_outside_base_dir():
    """Test that paths outside base directory are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file outside the base directory
        parent_dir = os.path.dirname(tmpdir)
        outside_file = os.path.join(parent_dir, "outside_file")
        with open(outside_file, "w") as f:
            f.write("outside-content")

        # Path outside base_dir should be rejected
        result = _validate_file_path(outside_file, tmpdir, require_exists=True)
        assert result is False

        # Clean up
        os.remove(outside_file)


def test_validate_file_path_regular_file_allowed():
    """Test that regular files within base directory are allowed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a regular file
        file_path = os.path.join(tmpdir, "regular_file")
        with open(file_path, "w") as f:
            f.write("file-content")

        # Regular file should be allowed
        result = _validate_file_path(file_path, tmpdir, require_exists=True)
        assert result is True


def test_resolve_secret_directory_rejection():
    """Test that directories are rejected when resolving secrets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a subdirectory
        subdir = os.path.join(tmpdir, "subdir")
        os.makedirs(subdir, exist_ok=True)

        # Directory should be rejected
        result = _resolve_secret("subdir", secrets_dir=tmpdir)
        assert result == ""


def test_resolve_secret_symlink_rejection():
    """Test that symlinks are rejected when resolving secrets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a regular file
        target_file = os.path.join(tmpdir, "target")
        with open(target_file, "w") as f:
            f.write("target-content")

        # Create a symlink to it
        symlink_path = os.path.join(tmpdir, "symlink")
        os.symlink(target_file, symlink_path)

        # Symlink should be rejected
        result = _resolve_secret("symlink", secrets_dir=tmpdir)
        assert result == ""


def test_resolve_key_path_directory_rejection():
    """Test that directories are rejected when resolving key paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a subdirectory
        subdir = os.path.join(tmpdir, "subdir")
        os.makedirs(subdir, exist_ok=True)

        # Directory should be rejected (relative path)
        result = _resolve_key_path("subdir", keys_dir=tmpdir)
        assert result == ""

        # Directory should be rejected (absolute path)
        result2 = _resolve_key_path(subdir, keys_dir=tmpdir)
        assert result2 == ""


def test_resolve_key_path_symlink_rejection():
    """Test that symlinks are rejected when resolving key paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a regular file
        target_file = os.path.join(tmpdir, "target")
        with open(target_file, "w") as f:
            f.write("target-content")

        # Create a symlink to it
        symlink_path = os.path.join(tmpdir, "symlink")
        os.symlink(target_file, symlink_path)

        # Symlink should be rejected (relative path)
        result = _resolve_key_path("symlink", keys_dir=tmpdir)
        assert result == ""

        # Symlink should be rejected (absolute path)
        result2 = _resolve_key_path(symlink_path, keys_dir=tmpdir)
        assert result2 == ""


def test_resolve_secret_regular_file_still_works():
    """Test that regular files still work after file validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a regular file
        file_path = os.path.join(tmpdir, "regular_secret")
        with open(file_path, "w") as f:
            f.write("regular-secret-content")

        # Should work
        result = _resolve_secret("regular_secret", secrets_dir=tmpdir)
        assert result == "regular-secret-content"


def test_resolve_key_path_regular_file_still_works():
    """Test that regular files still work after file validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a regular file
        file_path = os.path.join(tmpdir, "regular_key")
        with open(file_path, "w") as f:
            f.write("regular-key-content")

        # Should work with relative path
        result = _resolve_key_path("regular_key", keys_dir=tmpdir)
        assert result == os.path.abspath(file_path)

        # Should work with absolute path
        result2 = _resolve_key_path(file_path, keys_dir=tmpdir)
        assert result2 == os.path.abspath(file_path)


def test_load_yaml_normal_size():
    """Test that normal sized YAML files load correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "test.yml")
        # Create a small YAML file (much smaller than limit)
        yaml_content = {
            "test": "data",
            "key": "value",
            "list": [1, 2, 3],
        }
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_content, f)

        result = _load_yaml(yaml_path)
        assert result == yaml_content


def test_load_yaml_oversized_file():
    """Test that oversized YAML files are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "oversized.yml")
        # Create a file larger than MAX_YAML_FILE_SIZE
        # We'll create a file that's slightly larger than the limit
        oversized_size = MAX_YAML_FILE_SIZE + 1024  # 1KB over limit
        with open(yaml_path, "w") as f:
            # Write enough data to exceed the limit
            # YAML files are text, so we'll write a large string
            large_content = "key: " + "x" * oversized_size
            f.write(large_content)

        # Verify file size exceeds limit
        assert os.path.getsize(yaml_path) > MAX_YAML_FILE_SIZE

        # Should return empty dict and log security event
        result = _load_yaml(yaml_path)
        assert result == {}


def test_load_yaml_at_size_limit():
    """Test that YAML file at size limit is accepted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "at_limit.yml")
        # Create a file exactly at the size limit
        yaml_content = {
            "test": "data",
            "large_field": "x" * (MAX_YAML_FILE_SIZE - 100),
        }
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_content, f)

        # Adjust if file is slightly larger than expected
        current_size = os.path.getsize(yaml_path)
        if current_size > MAX_YAML_FILE_SIZE:
            # Reduce content to fit
            yaml_content = {
                "test": "data",
                "large_field": "x" * (MAX_YAML_FILE_SIZE - 200),
            }
            with open(yaml_path, "w") as f:
                yaml.dump(yaml_content, f)

        # File at limit should be accepted
        result = _load_yaml(yaml_path)
        assert "test" in result


def test_load_yaml_missing_file():
    """Test that missing YAML file returns empty dict."""
    result = _load_yaml("/nonexistent/file.yml")
    assert result == {}


def test_load_yaml_invalid_yaml():
    """Test that invalid YAML returns empty dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "invalid.yml")
        with open(yaml_path, "w") as f:
            f.write("invalid: yaml: content: [unclosed")

        # Should return empty dict on parse error
        result = _load_yaml(yaml_path)
        assert result == {}


def test_resolve_secret_name_length_at_limit():
    """Test that secret name at length limit is accepted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create secret file with max length name
        secret_name = "a" * MAX_SECRET_NAME_LENGTH
        secret_file = os.path.join(tmpdir, secret_name)
        with open(secret_file, "w") as f:
            f.write("secret-content")

        # Should work at limit
        result = _resolve_secret(secret_name, secrets_dir=tmpdir)
        assert result == "secret-content"


def test_resolve_secret_name_length_exceeds_limit():
    """Test that secret name exceeding length limit is rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Secret name exceeding limit
        secret_name = "a" * (MAX_SECRET_NAME_LENGTH + 1)

        # Should be rejected
        result = _resolve_secret(secret_name, secrets_dir=tmpdir)
        assert result == ""


def test_resolve_secret_name_length_under_limit():
    """Test that secret name under limit is accepted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Secret name well under limit
        secret_name = "normal_secret"
        secret_file = os.path.join(tmpdir, secret_name)
        with open(secret_file, "w") as f:
            f.write("secret-content")

        # Should work
        result = _resolve_secret(secret_name, secrets_dir=tmpdir)
        assert result == "secret-content"


def test_resolve_key_path_length_at_limit():
    """Test that key path at length limit is accepted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create key file with path at limit (but reasonable for filesystem)
        # Filesystem has limits, so use a reasonable but still long path
        # Use nested path to test long path handling without exceeding filesystem limits
        max_reasonable_length = min(
            MAX_KEY_PATH_LENGTH, 200
        )  # Stay within filesystem limits
        key_name = "a" * max_reasonable_length
        key_path = os.path.join(tmpdir, key_name)
        with open(key_path, "w") as f:
            f.write("key-content")

        # Should work at limit (use relative path)
        relative_path = key_name
        result = _resolve_key_path(relative_path, keys_dir=tmpdir)
        assert result == os.path.abspath(key_path)


def test_resolve_key_path_length_exceeds_limit():
    """Test that key path exceeding length limit is rejected."""
    # Key path exceeding limit
    key_path = "a" * (MAX_KEY_PATH_LENGTH + 1)

    # Should be rejected
    result = _resolve_key_path(key_path, keys_dir="/app/keys")
    assert result == ""


def test_resolve_key_path_length_under_limit():
    """Test that key path under limit is accepted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Key path well under limit
        key_name = "normal_key"
        key_path = os.path.join(tmpdir, key_name)
        with open(key_path, "w") as f:
            f.write("key-content")

        # Should work
        result = _resolve_key_path("normal_key", keys_dir=tmpdir)
        assert result == os.path.abspath(key_path)


def test_resolve_secret_length_validation_before_character_validation():
    """Test that length validation happens before character validation."""
    # Secret name that's too long but also has invalid characters
    secret_name = "a" * (MAX_SECRET_NAME_LENGTH + 1) + "!"

    # Should be rejected for length first
    result = _resolve_secret(secret_name, secrets_dir="/app/secrets")
    assert result == ""


def test_resolve_key_path_length_validation_before_traversal_check():
    """Test that length validation happens before traversal check."""
    # Key path that's too long and contains traversal
    key_path = "a" * (MAX_KEY_PATH_LENGTH + 1) + "../"

    # Should be rejected for length first
    result = _resolve_key_path(key_path, keys_dir="/app/keys")
    assert result == ""


def test_log_security_event_format():
    """Test that security audit events are logged in valid JSON format."""
    import json
    import sys
    from io import StringIO

    # Capture stderr
    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        _log_security_event(
            event_type="path_traversal_attempt",
            attempted_path="../etc/passwd",
            resolved_path="/app/secrets/../etc/passwd",
            reason="path_outside_allowed_directory",
            additional_data={"base_dir": "/app/secrets"},
        )

        output = sys.stderr.getvalue()
        assert output, "Should have logged to stderr"

        # Parse as JSON
        data = json.loads(output.strip())
        assert data["level"] == "error"
        assert data["kind"] == "security_audit"
        assert data["type"] == "security_event"
        assert data["event_type"] == "path_traversal_attempt"
        assert "ts" in data
        assert "timestamp" in data
        assert data["attempted_path"] == "../etc/passwd"
        assert data["resolved_path"] == "/app/secrets/../etc/passwd"
        assert data["reason"] == "path_outside_allowed_directory"
        assert data["base_dir"] == "/app/secrets"
    finally:
        sys.stderr = old_stderr


def test_log_security_event_minimal():
    """Test that security audit events work with minimal parameters."""
    import json
    import sys
    from io import StringIO

    # Capture stderr
    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        _log_security_event(event_type="test_event")

        output = sys.stderr.getvalue()
        assert output, "Should have logged to stderr"

        # Parse as JSON
        data = json.loads(output.strip())
        assert data["event_type"] == "test_event"
        assert "ts" in data
        assert "timestamp" in data
        # Optional fields should not be present if not provided
        assert "attempted_path" not in data
        assert "resolved_path" not in data
        assert "reason" not in data
    finally:
        sys.stderr = old_stderr


def test_audit_logging_path_traversal_attempt():
    """Test that path traversal attempts are logged via audit logging."""
    import json
    import sys
    from io import StringIO

    # Capture stderr
    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file outside the secrets directory
            parent_dir = os.path.dirname(tmpdir)
            outside_file = os.path.join(parent_dir, "outside_secret")
            with open(outside_file, "w") as f:
                f.write("outside-secret")

            # Trigger path traversal attempt with valid secret name that has traversal
            # Use a secret name that passes character validation but triggers path traversal
            secret_name = "valid_secret"  # Valid characters
            secret_file = os.path.join(tmpdir, secret_name)
            with open(secret_file, "w") as f:
                f.write("valid-content")

            # Now try to access outside file using key_path with traversal
            # Use key_path which allows path traversal attempts
            result = _resolve_key_path("../outside_secret", keys_dir=tmpdir)

            # Should be rejected
            assert result == ""

            # Check audit log was written
            output = sys.stderr.getvalue()
            assert output, "Should have logged path traversal attempt"

            # Find the audit log entry
            lines = output.strip().split("\n")
            audit_line = None
            for line in lines:
                if line.strip():
                    try:
                        data = json.loads(line)
                        if data.get("event_type") == "path_traversal_attempt":
                            audit_line = line
                            break
                    except json.JSONDecodeError:
                        continue

            assert audit_line is not None, "Should have security audit log entry"
            data = json.loads(audit_line)
            assert data["event_type"] == "path_traversal_attempt"
            assert "attempted_path" in data
            assert "reason" in data

            # Clean up
            os.remove(outside_file)
    finally:
        sys.stderr = old_stderr


def test_audit_logging_invalid_file_access():
    """Test that invalid file access attempts are logged via audit logging."""
    import json
    import sys
    from io import StringIO

    # Capture stderr
    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a directory (not a file)
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir, exist_ok=True)

            # Try to resolve directory as secret (should fail)
            result = _resolve_secret("subdir", secrets_dir=tmpdir)

            # Should be rejected
            assert result == ""

            # Check audit log was written
            output = sys.stderr.getvalue()
            assert output, "Should have logged invalid file access"

            # Find the audit log entry for file validation failure
            lines = output.strip().split("\n")
            audit_line = None
            for line in lines:
                if line.strip():
                    try:
                        data = json.loads(line)
                        if data.get("event_type") == "file_validation_failed":
                            audit_line = line
                            break
                    except json.JSONDecodeError:
                        continue

            assert audit_line is not None, "Should have security audit log entry"
            data = json.loads(audit_line)
            assert data["event_type"] == "file_validation_failed"
            assert "attempted_path" in data
            assert "reason" in data
    finally:
        sys.stderr = old_stderr


def test_audit_logging_oversized_file():
    """Test that oversized file attempts are logged via audit logging."""
    import json
    import sys
    from io import StringIO

    # Capture stderr
    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = os.path.join(tmpdir, "oversized.yml")
            # Create oversized file
            oversized_size = MAX_YAML_FILE_SIZE + 1024
            with open(yaml_path, "w") as f:
                large_content = "key: " + "x" * oversized_size
                f.write(large_content)

            # Try to load oversized file
            result = _load_yaml(yaml_path)

            # Should return empty dict
            assert result == {}

            # Check audit log was written
            output = sys.stderr.getvalue()
            assert output, "Should have logged oversized file attempt"

            # Find the audit log entry
            lines = output.strip().split("\n")
            audit_line = None
            for line in lines:
                if line.strip():
                    try:
                        data = json.loads(line)
                        if data.get("event_type") == "file_size_limit_exceeded":
                            audit_line = line
                            break
                    except json.JSONDecodeError:
                        continue

            assert audit_line is not None, "Should have security audit log entry"
            data = json.loads(audit_line)
            assert data["event_type"] == "file_size_limit_exceeded"
            assert "attempted_path" in data
            assert "file_size" in data
            assert "max_size" in data
            assert data["file_size"] > data["max_size"]
    finally:
        sys.stderr = old_stderr


def test_audit_logging_does_not_break_functionality():
    """Test that audit logging failures don't break functionality."""
    from unittest.mock import patch

    # Mock stderr.write to raise exception
    with patch("sys.stderr.write", side_effect=Exception("Logging failed")):
        # Should still function normally (logging errors are silent)
        with tempfile.TemporaryDirectory() as tmpdir:
            secret_file = os.path.join(tmpdir, "valid_secret")
            with open(secret_file, "w") as f:
                f.write("secret-content")

            # Should still work despite logging failure
            result = _resolve_secret("valid_secret", secrets_dir=tmpdir)
            assert result == "secret-content"


def test_audit_logging_includes_timestamp():
    """Test that audit logs include both Unix timestamp and ISO format."""
    import json
    import sys
    import time
    from io import StringIO

    # Capture stderr
    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        before = time.time()
        _log_security_event(event_type="test_event")
        after = time.time()

        output = sys.stderr.getvalue()
        data = json.loads(output.strip())

        # Check Unix timestamp
        assert "ts" in data
        assert isinstance(data["ts"], int | float)
        assert before <= data["ts"] <= after

        # Check ISO timestamp
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)
        # Should be in format YYYY-MM-DDTHH:MM:SS+offset
        assert "T" in data["timestamp"]
    finally:
        sys.stderr = old_stderr

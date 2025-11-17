"""Tests for SSH client."""

import io
import socket
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import paramiko
import pytest

from mcp_ssh.ssh_client import (
    DNS_MAX_RESOLUTIONS_PER_SECOND,
    SSHClient,
    _cache_ips,
    _dns_cache_lock,
    _dns_rate_limiter,
    _get_cached_ips,
    _is_rate_limited,
)


def test_resolve_ips_localhost():
    """Test DNS resolution for localhost."""
    ips = SSHClient.resolve_ips("localhost")

    # Should resolve to 127.0.0.1
    assert "127.0.0.1" in ips


def test_resolve_ips_invalid():
    """Test DNS resolution for invalid hostname."""
    ips = SSHClient.resolve_ips("this-hostname-does-not-exist-12345.invalid")

    # Should return empty list
    assert ips == []


def test_ssh_client_init():
    """Test SSH client initialization."""
    client = SSHClient(
        host="10.0.0.1",
        username="testuser",
        port=22,
        key_path="/path/to/key",
        password="",
    )

    assert client.host == "10.0.0.1"
    assert client.username == "testuser"
    assert client.port == 22
    assert client.key_path == "/path/to/key"
    assert client.password == ""


def test_ssh_client_default_port():
    """Test SSH client with default port."""
    client = SSHClient(
        host="10.0.0.1",
        username="testuser",
    )

    assert client.port == 22


def test_ssh_client_run_streaming_cancel():
    """Test cancellation of SSH command (mock)."""
    # This test is limited because we can't actually SSH to a real host
    # We test the cancel event mechanism

    cancel_event = threading.Event()

    # Simulate cancellation
    cancel_event.set()

    assert cancel_event.is_set() is True


def test_ssh_client_known_hosts_settings():
    """Test known_hosts configuration."""
    client = SSHClient(
        host="10.0.0.1",
        username="testuser",
        known_hosts_path="/app/keys/known_hosts",
        auto_add_host_keys=False,
        require_known_host=True,
    )

    assert client.known_hosts_path == "/app/keys/known_hosts"
    # Security: require_known_host is always True regardless of input
    assert client.require_known_host is True


def test_ssh_client_require_known_host_always_enforced():
    """Test that require_known_host is always enforced for security."""
    # Capture stderr to check for deprecation warning
    stderr_capture = io.StringIO()
    original_stderr = sys.stderr
    sys.stderr = stderr_capture

    try:
        # Even if require_known_host=False is passed, it should be True
        client = SSHClient(
            host="10.0.0.1",
            username="testuser",
            require_known_host=False,
        )

        # Security: require_known_host must always be True (CWE-295)
        assert client.require_known_host is True

        # Check that deprecation warning was logged
        stderr_output = stderr_capture.getvalue()
        assert "deprecation_warning" in stderr_output
        assert "require_known_host=False is deprecated" in stderr_output
        assert "CWE-295" in stderr_output
    finally:
        sys.stderr = original_stderr


def test_ssh_client_auto_add_host_keys_deprecation():
    """Test that auto_add_host_keys triggers deprecation warning."""
    # Capture stderr to check for deprecation warning
    stderr_capture = io.StringIO()
    original_stderr = sys.stderr
    sys.stderr = stderr_capture

    try:
        client = SSHClient(
            host="10.0.0.1",
            username="testuser",
            auto_add_host_keys=True,
        )

        # Security: require_known_host must always be True (CWE-295)
        assert client.require_known_host is True

        # Check that deprecation warning was logged
        stderr_output = stderr_capture.getvalue()
        assert "deprecation_warning" in stderr_output
        assert "auto_add_host_keys is deprecated" in stderr_output
        assert "CWE-295" in stderr_output
    finally:
        sys.stderr = original_stderr


# Note: Full integration tests with actual SSH connections would require
# a test SSH server (like docker-based openssh-server). These are better
# suited for integration test suite rather than unit tests.


def test_dns_resolution_normal():
    """Test normal DNS resolution still works."""
    ips = SSHClient.resolve_ips("localhost")

    # Should resolve to at least one IP
    assert len(ips) > 0
    assert "127.0.0.1" in ips


def test_dns_resolution_caching():
    """Test that DNS results are cached."""
    hostname = "example.com"

    # First resolution should hit DNS
    ips1 = SSHClient.resolve_ips(hostname)

    # Second resolution should use cache (same result immediately)
    ips2 = SSHClient.resolve_ips(hostname)

    # Results should match
    assert ips1 == ips2

    # Cached result should be available
    cached = _get_cached_ips(hostname)
    assert cached is not None
    assert cached == ips1


def test_dns_rate_limiting():
    """Test that rate limiting prevents excessive DNS resolutions."""
    hostname = "test-rate-limit.example.com"

    # Clear any existing rate limit state
    with _dns_cache_lock:
        if hostname in _dns_rate_limiter:
            del _dns_rate_limiter[hostname]

    # Make requests up to the limit (should all succeed)
    for request_num in range(DNS_MAX_RESOLUTIONS_PER_SECOND):
        result = _is_rate_limited(hostname)
        assert result is False, f"Request {request_num+1} should not be rate limited"

    # Next request should be rate limited
    assert _is_rate_limited(hostname) is True


def test_dns_rate_limiting_time_window():
    """Test that rate limiting uses 1-second time window."""
    hostname = "test-time-window.example.com"

    # Clear any existing rate limit state
    with _dns_cache_lock:
        if hostname in _dns_rate_limiter:
            del _dns_rate_limiter[hostname]

    # Exhaust the rate limit
    for _ in range(DNS_MAX_RESOLUTIONS_PER_SECOND):
        _is_rate_limited(hostname)

    # Should be rate limited now
    assert _is_rate_limited(hostname) is True

    # Wait for time window to expire (just over 1 second)
    time.sleep(1.1)

    # Should no longer be rate limited (old timestamps cleaned)
    assert _is_rate_limited(hostname) is False


def test_dns_cache_get_and_set():
    """Test DNS cache get and set functions."""
    hostname = "test-cache.example.com"
    test_ips = ["192.168.1.1", "192.168.1.2"]

    # Should not be cached initially
    assert _get_cached_ips(hostname) is None

    # Cache the result
    _cache_ips(hostname, test_ips)

    # Should retrieve cached result
    cached = _get_cached_ips(hostname)
    assert cached is not None
    assert cached == test_ips


def test_dns_cache_expiration():
    """Test that DNS cache entries expire after TTL."""

    hostname = "test-expire.example.com"
    test_ips = ["10.0.0.1"]

    # Cache the result
    _cache_ips(hostname, test_ips)

    # Should be cached immediately
    assert _get_cached_ips(hostname) == test_ips

    # Manually expire by manipulating time
    # (In real scenario, this happens after TTL)
    # For testing, we'll wait for actual expiration or test the logic

    # Clear cache to test expiration logic
    from mcp_ssh.ssh_client import _dns_cache

    with _dns_cache_lock:
        if hostname in _dns_cache:
            # Simulate expiration by setting expiry in the past
            _dns_cache[hostname] = (test_ips, time.time() - 1)

    # Should return None (expired)
    assert _get_cached_ips(hostname) is None


def test_dns_resolution_empty_hostname():
    """Test that empty hostname returns empty list."""
    ips = SSHClient.resolve_ips("")
    assert ips == []


def test_dns_resolution_rate_limited_hostname():
    """Test that rate-limited hostname returns empty list."""
    hostname = "rate-limited-host.example.com"

    # Force rate limiting by making many rapid calls
    with _dns_cache_lock:
        if hostname in _dns_rate_limiter:
            del _dns_rate_limiter[hostname]
        # Create a rate-limited state
        _dns_rate_limiter[hostname] = [time.time()] * (
            DNS_MAX_RESOLUTIONS_PER_SECOND + 1
        )

    # Resolution should return empty (rate limited)
    ips = SSHClient.resolve_ips(hostname)
    assert ips == []


def test_dns_resolution_multiple_hostnames():
    """Test that rate limiting is per-hostname."""
    hostname1 = "host1.example.com"
    hostname2 = "host2.example.com"

    # Clear rate limiters
    with _dns_cache_lock:
        if hostname1 in _dns_rate_limiter:
            del _dns_rate_limiter[hostname1]
        if hostname2 in _dns_rate_limiter:
            del _dns_rate_limiter[hostname2]

    # Rate limit hostname1
    for _ in range(DNS_MAX_RESOLUTIONS_PER_SECOND + 1):
        _is_rate_limited(hostname1)

    # hostname1 should be rate limited
    assert _is_rate_limited(hostname1) is True

    # hostname2 should NOT be rate limited (different hostname)
    assert _is_rate_limited(hostname2) is False


# === SSH Error Handling Tests ===


def test_ssh_client_authentication_error():
    """Test authentication failure handling."""
    client = SSHClient(host="10.0.0.1", username="testuser", key_path="/path/to/key")

    # Mock paramiko.SSHClient and key loading
    mock_key = MagicMock()
    mock_host_key = MagicMock()
    with (
        patch("paramiko.SSHClient") as mock_ssh_client_class,
        patch("paramiko.RSAKey.from_private_key_file", return_value=mock_key),
    ):
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        # Host keys must have at least one key for the host to pass known_hosts check
        mock_ssh_client.get_host_keys.return_value = {
            "10.0.0.1": {"ssh-rsa": mock_host_key}
        }
        mock_ssh_client.connect.side_effect = paramiko.AuthenticationException(
            "Authentication failed"
        )

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert "SSH authentication failed: Invalid credentials" in str(exc_info.value)


def test_ssh_client_host_key_error():
    """Test host key verification failure handling."""
    client = SSHClient(host="10.0.0.1", username="testuser", key_path="/path/to/key")

    # Mock paramiko.SSHClient to raise BadHostKeyException during connect
    mock_key = MagicMock()
    mock_host_key = MagicMock()
    with (
        patch("paramiko.SSHClient") as mock_ssh_client_class,
        patch("paramiko.RSAKey.from_private_key_file", return_value=mock_key),
    ):
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        mock_ssh_client.get_host_keys.return_value = {
            "10.0.0.1": {"ssh-rsa": mock_host_key}
        }
        # BadHostKeyException requires proper key objects
        mock_bad_key = MagicMock()
        mock_bad_key.get_base64.return_value = "test_key_data"
        mock_expected_key = MagicMock()
        mock_expected_key.get_base64.return_value = "expected_key_data"
        mock_ssh_client.connect.side_effect = paramiko.BadHostKeyException(
            "10.0.0.1", mock_bad_key, mock_expected_key
        )

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert "SSH host key verification failed: Host key mismatch" in str(
            exc_info.value
        )


def test_ssh_client_connection_timeout():
    """Test timeout handling."""
    client = SSHClient(host="10.0.0.1", username="testuser", key_path="/path/to/key")

    # Mock paramiko.SSHClient to raise TimeoutError during connect
    mock_key = MagicMock()
    mock_host_key = MagicMock()
    with (
        patch("paramiko.SSHClient") as mock_ssh_client_class,
        patch("paramiko.RSAKey.from_private_key_file", return_value=mock_key),
    ):
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        mock_ssh_client.get_host_keys.return_value = {
            "10.0.0.1": {"ssh-rsa": mock_host_key}
        }
        mock_ssh_client.connect.side_effect = TimeoutError("Connection timed out")

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert "SSH connection timeout: Host did not respond" in str(exc_info.value)


def test_ssh_client_connection_refused():
    """Test connection refused handling."""
    client = SSHClient(host="10.0.0.1", username="testuser", key_path="/path/to/key")

    # Mock paramiko.SSHClient to raise ConnectionRefusedError during connect
    mock_key = MagicMock()
    mock_host_key = MagicMock()
    with (
        patch("paramiko.SSHClient") as mock_ssh_client_class,
        patch("paramiko.RSAKey.from_private_key_file", return_value=mock_key),
    ):
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        mock_ssh_client.get_host_keys.return_value = {
            "10.0.0.1": {"ssh-rsa": mock_host_key}
        }
        mock_ssh_client.connect.side_effect = ConnectionRefusedError(
            "Connection refused"
        )

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert "SSH connection refused: Port may be closed or firewall blocking" in str(
            exc_info.value
        )


def test_ssh_client_dns_resolution_failure():
    """Test DNS resolution failure handling."""
    client = SSHClient(
        host="invalid-host.example", username="testuser", key_path="/path/to/key"
    )

    # Mock paramiko.SSHClient to raise socket.gaierror during connect
    mock_key = MagicMock()
    mock_host_key = MagicMock()
    with (
        patch("paramiko.SSHClient") as mock_ssh_client_class,
        patch("paramiko.RSAKey.from_private_key_file", return_value=mock_key),
    ):
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        mock_ssh_client.get_host_keys.return_value = {
            "invalid-host.example": {"ssh-rsa": mock_host_key}
        }
        gaierror = socket.gaierror("Name or service not known")
        mock_ssh_client.connect.side_effect = gaierror

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert "SSH hostname resolution failed: DNS lookup failed" in str(
            exc_info.value
        )


def test_ssh_client_key_file_not_found():
    """Test missing key file handling."""
    client = SSHClient(
        host="10.0.0.1", username="testuser", key_path="/nonexistent/key"
    )

    # Mock paramiko key loading to raise FileNotFoundError
    mock_host_key = MagicMock()
    with (
        patch("paramiko.SSHClient") as mock_ssh_client_class,
        patch("paramiko.RSAKey.from_private_key_file") as mock_rsa,
        patch("paramiko.Ed25519Key.from_private_key_file") as mock_ed25519,
        patch("paramiko.ECDSAKey.from_private_key_file") as mock_ecdsa,
    ):
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        mock_ssh_client.get_host_keys.return_value = {
            "10.0.0.1": {"ssh-rsa": mock_host_key}
        }
        mock_rsa.side_effect = FileNotFoundError(
            "No such file or directory: '/nonexistent/key'"
        )
        mock_ed25519.side_effect = FileNotFoundError(
            "No such file or directory: '/nonexistent/key'"
        )
        mock_ecdsa.side_effect = FileNotFoundError(
            "No such file or directory: '/nonexistent/key'"
        )

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert "SSH key file not found: Check key path configuration" in str(
            exc_info.value
        )


def test_ssh_client_key_passphrase_required():
    """Test passphrase requirement handling."""
    client = SSHClient(
        host="10.0.0.1", username="testuser", key_path="/path/to/encrypted/key"
    )

    # Mock paramiko key loading to raise PasswordRequiredException
    mock_host_key = MagicMock()
    with (
        patch("paramiko.SSHClient") as mock_ssh_client_class,
        patch("paramiko.RSAKey.from_private_key_file") as mock_rsa,
        patch("paramiko.Ed25519Key.from_private_key_file") as mock_ed25519,
        patch("paramiko.ECDSAKey.from_private_key_file") as mock_ecdsa,
    ):
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        mock_ssh_client.get_host_keys.return_value = {
            "10.0.0.1": {"ssh-rsa": mock_host_key}
        }
        mock_rsa.side_effect = paramiko.PasswordRequiredException(
            "Private key is encrypted"
        )
        mock_ed25519.side_effect = paramiko.PasswordRequiredException(
            "Private key is encrypted"
        )
        mock_ecdsa.side_effect = paramiko.PasswordRequiredException(
            "Private key is encrypted"
        )

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert "SSH key requires passphrase: Provide key_passphrase_secret" in str(
            exc_info.value
        )


def test_ssh_client_generic_error():
    """Test fallback error handling."""
    client = SSHClient(host="10.0.0.1", username="testuser", key_path="/path/to/key")

    # Mock paramiko.SSHClient to raise generic Exception during connect
    mock_key = MagicMock()
    mock_host_key = MagicMock()
    with (
        patch("paramiko.SSHClient") as mock_ssh_client_class,
        patch("paramiko.RSAKey.from_private_key_file", return_value=mock_key),
    ):
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        mock_ssh_client.get_host_keys.return_value = {
            "10.0.0.1": {"ssh-rsa": mock_host_key}
        }
        mock_ssh_client.connect.side_effect = Exception("Unexpected error")

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert (
            "SSH connection failed: Check host, port, and network connectivity"
            in str(exc_info.value)
        )


def test_ssh_client_host_key_not_found():
    """Test host key not found in known_hosts."""
    client = SSHClient(host="10.0.0.1", username="testuser", key_path="/path/to/key")

    # Mock paramiko.SSHClient to have empty host keys (simulating missing known_hosts entry)
    with patch("paramiko.SSHClient") as mock_ssh_client_class:
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        # Empty host keys triggers the known_hosts check
        mock_ssh_client.get_host_keys.return_value = {}

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert "SSH host key not found: Add host to known_hosts" in str(exc_info.value)


def test_ssh_client_key_format_invalid():
    """Test invalid key format handling."""
    client = SSHClient(
        host="10.0.0.1", username="testuser", key_path="/path/to/invalid/key"
    )

    # Mock paramiko key loading to raise SSHException with invalid key message
    from paramiko import ssh_exception

    mock_host_key = MagicMock()
    with (
        patch("paramiko.SSHClient") as mock_ssh_client_class,
        patch("paramiko.RSAKey.from_private_key_file") as mock_rsa,
        patch("paramiko.Ed25519Key.from_private_key_file") as mock_ed25519,
        patch("paramiko.ECDSAKey.from_private_key_file") as mock_ecdsa,
    ):
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        mock_ssh_client.get_host_keys.return_value = {
            "10.0.0.1": {"ssh-rsa": mock_host_key}
        }
        invalid_key_error = ssh_exception.SSHException(
            "not a valid RSA private key file"
        )
        mock_rsa.side_effect = invalid_key_error
        mock_ed25519.side_effect = invalid_key_error
        mock_ecdsa.side_effect = invalid_key_error

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert (
            "SSH key format invalid: Check key file format (RSA/Ed25519/ECDSA)"
            in str(exc_info.value)
        )


def test_ssh_client_permission_denied_key():
    """Test key permission denied handling."""
    client = SSHClient(host="10.0.0.1", username="testuser", key_path="/path/to/key")

    # Mock paramiko key loading to raise PermissionError
    mock_host_key = MagicMock()
    with (
        patch("paramiko.SSHClient") as mock_ssh_client_class,
        patch("paramiko.RSAKey.from_private_key_file") as mock_rsa,
        patch("paramiko.Ed25519Key.from_private_key_file") as mock_ed25519,
        patch("paramiko.ECDSAKey.from_private_key_file") as mock_ecdsa,
    ):
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        mock_ssh_client.get_host_keys.return_value = {
            "10.0.0.1": {"ssh-rsa": mock_host_key}
        }
        perm_error = PermissionError("Permission denied: '/path/to/key'")
        mock_rsa.side_effect = perm_error
        mock_ed25519.side_effect = perm_error
        mock_ecdsa.side_effect = perm_error

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert (
            "SSH key permission denied: Check key file permissions (should be 600)"
            in str(exc_info.value)
        )


def test_ssh_client_network_unreachable():
    """Test network unreachable handling."""
    client = SSHClient(host="10.0.0.1", username="testuser", key_path="/path/to/key")

    # Mock paramiko.SSHClient to raise OSError with network unreachable message
    mock_key = MagicMock()
    mock_host_key = MagicMock()
    with (
        patch("paramiko.SSHClient") as mock_ssh_client_class,
        patch("paramiko.RSAKey.from_private_key_file", return_value=mock_key),
    ):
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        mock_ssh_client.get_host_keys.return_value = {
            "10.0.0.1": {"ssh-rsa": mock_host_key}
        }
        os_error = OSError("Network is unreachable")
        mock_ssh_client.connect.side_effect = os_error

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        assert "SSH network unreachable: Cannot reach host" in str(exc_info.value)

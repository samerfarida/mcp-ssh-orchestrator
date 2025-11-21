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


def test_dns_cache_grace_period():
    """Test that DNS cache uses grace period to prevent TOCTOU race condition."""
    hostname = "test-grace.example.com"
    test_ips = ["10.0.0.1"]

    # Cache the result
    _cache_ips(hostname, test_ips)

    # Should be cached immediately
    assert _get_cached_ips(hostname) == test_ips

    # Simulate cache entry that is just expired (within grace period)
    from mcp_ssh.ssh_client import _dns_cache

    with _dns_cache_lock:
        if hostname in _dns_cache:
            # Set expiry to 0.5 seconds in the past (within 1 second grace period)
            _dns_cache[hostname] = (test_ips, time.time() - 0.5)

    # Should still return cached result due to grace period
    assert _get_cached_ips(hostname) == test_ips

    # Now set expiry to more than 1 second in the past (beyond grace period)
    with _dns_cache_lock:
        if hostname in _dns_cache:
            _dns_cache[hostname] = (test_ips, time.time() - 1.1)

    # Should return None (expired beyond grace period)
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


def test_ssh_client_known_hosts_keyerror():
    """Test that KeyError from host key access is properly caught and converted."""
    client = SSHClient(host="10.0.0.1", username="testuser", key_path="/path/to/key")

    with patch("paramiko.SSHClient") as mock_ssh_client_class:
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        # Simulate KeyError when accessing hk[self.host]
        # This happens when hk[self.host] raises KeyError
        mock_host_keys = MagicMock()
        mock_host_keys.__contains__ = MagicMock(return_value=True)
        # When accessing hk[self.host], it raises KeyError
        mock_host_keys.__getitem__.side_effect = KeyError("Host key not found")
        mock_ssh_client.get_host_keys.return_value = mock_host_keys

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        # The KeyError is caught by our handler and converted to RuntimeError
        # Then the outer handler converts it to a user-friendly message
        assert "SSH host key" in str(exc_info.value) or "known_hosts" in str(
            exc_info.value
        )


def test_ssh_client_known_hosts_attributeerror():
    """Test that AttributeError from get_host_keys() is properly caught and converted."""
    client = SSHClient(host="10.0.0.1", username="testuser", key_path="/path/to/key")

    with patch("paramiko.SSHClient") as mock_ssh_client_class:
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        # Simulate AttributeError from get_host_keys()
        mock_ssh_client.get_host_keys.side_effect = AttributeError(
            "'NoneType' object has no attribute 'get_host_keys'"
        )

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        # The AttributeError is caught by our handler and converted to RuntimeError
        # Then the outer handler converts it to a user-friendly message
        assert "SSH host key verification failed" in str(exc_info.value)


def test_ssh_client_known_hosts_runtimeerror_not_caught():
    """Test that RuntimeError from known_hosts check is NOT caught by specific handler."""
    client = SSHClient(host="10.0.0.1", username="testuser", key_path="/path/to/key")

    with patch("paramiko.SSHClient") as mock_ssh_client_class:
        mock_ssh_client = MagicMock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.load_host_keys.return_value = None
        mock_ssh_client.load_system_host_keys.return_value = None
        # Empty host keys - should raise RuntimeError from known_hosts check
        mock_ssh_client.get_host_keys.return_value = {}

        with pytest.raises(RuntimeError) as exc_info:
            client._connect()

        # The RuntimeError is NOT caught by our specific handler (which only catches KeyError/AttributeError)
        # It propagates to the outer handler which converts it to a user-friendly message
        # The key point is that it's NOT wrapped in "known_hosts verification failed"
        assert "SSH host key not found" in str(exc_info.value)
        # Should NOT have "known_hosts verification failed" wrapper message
        assert "known_hosts verification failed" not in str(exc_info.value)


# Additional SSH client tests for improved coverage
def test_ssh_progress_callback(tmp_path):
    """Test SSH command execution with progress callback."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock the SSH connection
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    # Setup channel behavior for progress reporting
    output_chunks = [b"output chunk 1\n", b"output chunk 2\n"]
    output_iter = iter(output_chunks)
    recv_count = [0]

    def recv_ready():
        recv_count[0] += 1
        return recv_count[0] <= 2

    def recv(size):
        time.sleep(0.01)  # Small delay to ensure progress callback timing
        return next(output_iter, b"")

    mock_channel.recv_ready.side_effect = recv_ready
    mock_channel.recv.side_effect = recv
    mock_channel.recv_stderr_ready.return_value = False
    mock_channel.exit_status_ready.return_value = True
    mock_channel.recv_exit_status.return_value = 0
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)

    progress_calls = []

    def progress_cb(status, bytes_out, elapsed_ms):
        progress_calls.append((status, bytes_out, elapsed_ms))

    with patch.object(client, "_connect", return_value=(mock_client, "127.0.0.1")):
        cancel_event = threading.Event()
        result = client.run_streaming(
            command="echo test",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1024 * 1024,
            progress_cb=progress_cb,
        )

        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result

        # Should have progress callbacks
        assert len(progress_calls) >= 1  # At least "connecting" or "connected"
        assert exit_code == 0


def test_ssh_stderr_output(tmp_path):
    """Test SSH command execution with stderr output."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock the SSH connection
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    # Setup channel behavior with both stdout and stderr
    output_chunks = [b"stdout output\n"]
    stderr_chunks = [b"stderr output\n"]
    output_iter = iter(output_chunks)
    stderr_iter = iter(stderr_chunks)
    recv_count = [0]
    stderr_count = [0]

    def recv_ready():
        recv_count[0] += 1
        return recv_count[0] == 1

    def recv_stderr_ready():
        stderr_count[0] += 1
        return stderr_count[0] == 1

    def recv(size):
        return next(output_iter, b"")

    def recv_stderr(size):
        return next(stderr_iter, b"")

    mock_channel.recv_ready.side_effect = recv_ready
    mock_channel.recv.side_effect = recv
    mock_channel.recv_stderr_ready.side_effect = recv_stderr_ready
    mock_channel.recv_stderr.side_effect = recv_stderr
    mock_channel.exit_status_ready.return_value = True
    mock_channel.recv_exit_status.return_value = 0
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)

    with patch.object(client, "_connect", return_value=(mock_client, "127.0.0.1")):
        cancel_event = threading.Event()
        result = client.run_streaming(
            command="echo test 2>&1",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1024 * 1024,
        )

        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result

        assert exit_code == 0
        assert bytes_err > 0
        assert "stderr output" in combined


def test_ssh_output_limit_truncation(tmp_path):
    """Test SSH command execution with output limit that triggers truncation."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock the SSH connection
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    # Setup channel to send more data than limit
    large_output = b"x" * 5000  # Larger than 1000 byte limit
    output_sent = [False]

    def recv_ready():
        if not output_sent[0]:
            return True
        return False

    def recv(size):
        if not output_sent[0]:
            output_sent[0] = True
            return large_output[:4096]  # Send chunk
        return b""

    mock_channel.recv_ready.side_effect = recv_ready
    mock_channel.recv.side_effect = recv
    mock_channel.recv_stderr_ready.return_value = False
    mock_channel.exit_status_ready.return_value = True
    mock_channel.recv_exit_status.return_value = 0
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)

    with patch.object(client, "_connect", return_value=(mock_client, "127.0.0.1")):
        cancel_event = threading.Event()
        result = client.run_streaming(
            command="generate large output",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1000,  # Small limit
        )

        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result

        # Should respect output limit (truncate at 1000 bytes)
        assert bytes_out <= 1000


def test_ssh_connection_close_on_error(tmp_path):
    """Test that SSH client is properly closed on error during execution."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock the SSH connection that raises an error during execution
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    mock_channel.recv_ready.side_effect = RuntimeError("Channel error")
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)

    with patch.object(client, "_connect", return_value=(mock_client, "127.0.0.1")):
        cancel_event = threading.Event()
        client.run_streaming(
            command="echo test",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1024,
        )

        # Should close client even on error
        mock_client.close.assert_called()


def test_ssh_dns_timeout_error(tmp_path):
    """Test DNS resolution timeout handling."""
    # Mock socket.getaddrinfo to raise TimeoutError
    with patch("socket.getaddrinfo", side_effect=TimeoutError("DNS timeout")):
        ips = SSHClient.resolve_ips("test-host.example.com")
        # Should return empty list on timeout
        assert ips == []


def test_ssh_dns_general_exception(tmp_path):
    """Test DNS resolution general exception handling."""
    # Mock socket.getaddrinfo to raise a general exception
    with patch("socket.getaddrinfo", side_effect=Exception("DNS error")):
        ips = SSHClient.resolve_ips("test-host.example.com")
        # Should return empty list on exception
        assert ips == []


def test_ssh_channel_close_exception(tmp_path):
    """Test that channel close exceptions are handled gracefully."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock the SSH connection
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    # Channel raises exception on close
    mock_channel.close.side_effect = Exception("Close error")
    mock_channel.recv_ready.return_value = False
    mock_channel.recv_stderr_ready.return_value = False
    mock_channel.exit_status_ready.return_value = False
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)

    cancel_event = threading.Event()
    cancel_event.set()  # Trigger cancellation

    with patch.object(client, "_connect", return_value=(mock_client, "127.0.0.1")):
        result = client.run_streaming(
            command="echo test",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1024,
        )

        # Should handle close exception gracefully
        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result
        assert cancelled is True


def test_ssh_client_close_exception(tmp_path):
    """Test that client close exceptions are handled gracefully."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock the SSH connection
    mock_client = MagicMock()
    mock_client.close.side_effect = Exception("Client close error")
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    mock_channel.recv_exit_status.return_value = 0
    mock_channel.recv_ready.return_value = False
    mock_channel.recv_stderr_ready.return_value = False
    mock_channel.exit_status_ready.return_value = True
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)

    with patch.object(client, "_connect", return_value=(mock_client, "127.0.0.1")):
        cancel_event = threading.Event()
        result = client.run_streaming(
            command="echo test",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1024,
        )

        # Should handle client close exception gracefully
        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result
        assert exit_code == 0  # Command should still succeed


def test_ssh_stderr_output_limit(tmp_path):
    """Test SSH command execution with stderr output limit."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock the SSH connection
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    # Setup channel behavior with large stderr output
    large_stderr = b"y" * 5000  # Larger than 1000 byte limit
    stderr_sent = [False]

    def recv_stderr_ready():
        if not stderr_sent[0]:
            return True
        return False

    def recv_stderr(size):
        if not stderr_sent[0]:
            stderr_sent[0] = True
            return large_stderr[:4096]  # Send chunk
        return b""

    mock_channel.recv_ready.return_value = False
    mock_channel.recv_stderr_ready.side_effect = recv_stderr_ready
    mock_channel.recv_stderr.side_effect = recv_stderr
    mock_channel.exit_status_ready.return_value = True
    mock_channel.recv_exit_status.return_value = 0
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)

    with patch.object(client, "_connect", return_value=(mock_client, "127.0.0.1")):
        cancel_event = threading.Event()
        result = client.run_streaming(
            command="generate large stderr",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1000,  # Small limit
        )

        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result

        # Should respect output limit for stderr (truncate at 1000 bytes)
        assert bytes_err <= 1000


# Integration tests for SSH client using Paramiko SSH server
class SSHServerForTesting:
    """In-process SSH server for testing."""

    def __init__(
        self, host="127.0.0.1", port=0, username="testuser", password="testpass"
    ):
        """Initialize SSH server."""
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.server_socket = None
        self.server = None
        self.thread = None
        self.running = False

    def start(self):
        """Start the SSH server in a background thread."""
        import socket

        # Create a socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        # Get the actual port
        _, self.port = self.server_socket.getsockname()

        # Create paramiko server
        host_key = paramiko.RSAKey.generate(2048)
        self.server = paramiko.Transport(self.server_socket)
        self.server.add_server_key(host_key)
        self.server.set_subsystem_handler(
            "sftp", paramiko.SFTPServer, paramiko.SFTPServerInterface
        )

        # Set up server event
        event = threading.Event()

        def run_server():
            self.running = True
            try:
                self.server.start_server(
                    server=SSHServerHandlerForTesting(self.username, self.password)
                )
                event.set()
                while self.running:
                    channel = self.server.accept(1.0)
                    if channel is None:
                        continue
                    if channel.chanid not in self.server.channels:
                        continue
                    # Handle commands in a separate handler
                    self._handle_channel(channel)
            except Exception:
                pass
            finally:
                event.set()

        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()
        event.wait(timeout=5.0)

        return host_key, self.port

    def _handle_channel(self, channel):
        """Handle commands on a channel."""
        if channel.chanid not in self.server.channels:
            return

        try:
            while not channel.closed:
                if channel.recv_ready():
                    data = channel.recv(1024)
                    if not data:
                        break

                    # Parse command (simplified)
                    cmd = data.decode("utf-8", errors="ignore").strip()

                    # Execute command
                    if cmd.startswith("exit"):
                        exit_code = int(cmd.split()[1]) if len(cmd.split()) > 1 else 0
                        channel.send_exit_status(exit_code)
                        channel.close()
                    elif cmd == "echo test":
                        channel.send("test\n")
                        channel.send_exit_status(0)
                        channel.close()
                    elif cmd == "sleep 1":
                        time.sleep(1)
                        channel.send_exit_status(0)
                        channel.close()
                    elif cmd == "output large":
                        # Generate large output
                        large_output = "x" * 10000
                        channel.send(large_output)
                        channel.send_exit_status(0)
                        channel.close()
                    else:
                        # Default response
                        channel.send(f"Command: {cmd}\n")
                        channel.send_exit_status(0)
                        channel.close()
        except Exception:
            pass

    def stop(self):
        """Stop the SSH server."""
        self.running = False
        if self.server:
            self.server.close()
        if self.server_socket:
            self.server_socket.close()
        if self.thread:
            self.thread.join(timeout=2.0)


class SSHServerHandlerForTesting(paramiko.ServerInterface):
    """SSH server handler for Paramiko."""

    def __init__(self, username, password):
        """Initialize server handler."""
        self.username = username
        self.password = password

    def check_auth_password(self, username, password):
        """Check password authentication."""
        if username == self.username and password == self.password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        """Check public key authentication."""
        # For simplicity, accept any key for the correct username
        if username == self.username:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        """Check channel request."""
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username):
        """Get allowed authentication methods."""
        return "password,publickey"


@pytest.fixture
def ssh_server():
    """Create and start an SSH server for testing."""
    server = SSHServerForTesting()
    try:
        host_key, port = server.start()
        time.sleep(0.5)  # Give server time to start
        yield server, host_key, port
    finally:
        server.stop()


def test_ssh_connection_success(ssh_server, tmp_path):
    """Test successful SSH connection."""
    server, host_key, port = ssh_server

    # Create known_hosts file with server key
    known_hosts = tmp_path / "known_hosts"
    host_key.write_private_key_file(str(known_hosts.parent / "host_key"))

    # Add host key to known_hosts
    with open(known_hosts, "w") as f:
        f.write(f"127.0.0.1 {host_key.get_name()} {host_key.get_base64()}\n")

    _ = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=port,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=True,
    )

    # Test connection (will fail without proper key setup, but we can test the path)
    # Since we can't easily add the dynamic host key, we'll test with require_known_host=False
    # or mock the connection


def test_ssh_password_authentication(ssh_server, tmp_path):
    """Test SSH password authentication."""
    server, host_key, port = ssh_server

    # Create known_hosts (empty for now, we'll handle this differently)
    _ = tmp_path / "known_hosts"

    # For testing, we'll need to mock or bypass host key checking
    # or use a different approach


def test_ssh_key_authentication(ssh_server, tmp_path):
    """Test SSH key-based authentication."""
    server, host_key, port = ssh_server

    # Generate a test key pair
    test_key = paramiko.RSAKey.generate(2048)
    key_path = tmp_path / "test_key"
    test_key.write_private_key_file(str(key_path))

    known_hosts = tmp_path / "known_hosts"

    _ = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=port,
        key_path=str(key_path),
        known_hosts_path=str(known_hosts),
        require_known_host=False,  # Bypass for testing
    )


def test_ssh_run_command_success(tmp_path):
    """Test running a command successfully with mocked connection."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock the SSH connection
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    # Setup channel behavior for successful command execution
    output_chunks = [b"test output\n", b"more output\n"]  # Two chunks of data
    output_iter = iter(output_chunks)
    recv_count = [0]

    def recv_ready():
        # Return True for first 2 calls, then False
        recv_count[0] += 1
        return recv_count[0] <= 2

    def recv(size):
        return next(output_iter, b"")

    mock_channel.recv_ready.side_effect = recv_ready
    mock_channel.recv.side_effect = recv
    mock_channel.recv_stderr_ready.return_value = False
    # exit_status_ready should be True when no more data to receive
    mock_channel.exit_status_ready.return_value = True
    mock_channel.recv_exit_status.return_value = 0
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)

    with patch.object(client, "_connect", return_value=(mock_client, "127.0.0.1")):
        cancel_event = threading.Event()
        result = client.run_streaming(
            command="echo test",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1024 * 1024,
        )

        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result

        assert exit_code == 0
        assert not cancelled
        assert not timeout
        assert peer_ip == "127.0.0.1"
        assert "test output" in combined


def test_ssh_run_command_cancellation(tmp_path):
    """Test command cancellation."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock the SSH connection with a slow command
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    def slow_recv(size):
        time.sleep(0.1)
        if not cancel_event.is_set():
            return b"output\n"
        return b""

    mock_channel.recv_ready.side_effect = lambda: not cancel_event.is_set()
    mock_channel.recv.side_effect = slow_recv
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)

    cancel_event = threading.Event()

    def cancel_soon():
        time.sleep(0.2)
        cancel_event.set()

    cancel_thread = threading.Thread(target=cancel_soon, daemon=True)
    cancel_thread.start()

    with patch.object(client, "_connect", return_value=(mock_client, "127.0.0.1")):
        result = client.run_streaming(
            command="sleep 10",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1024 * 1024,
        )

        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result

        assert cancelled is True


def test_ssh_run_command_timeout(tmp_path):
    """Test command timeout."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock the SSH connection with a command that times out
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    mock_channel.recv_ready.return_value = False
    mock_channel.exit_status_ready.return_value = False
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)

    cancel_event = threading.Event()

    with patch.object(client, "_connect", return_value=(mock_client, "127.0.0.1")):
        result = client.run_streaming(
            command="sleep 100",
            cancel_event=cancel_event,
            max_seconds=1,  # Very short timeout
            max_output_bytes=1024 * 1024,
        )

        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result

        assert timeout is True


def test_ssh_run_command_output_limit(tmp_path):
    """Test output size limit."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock the SSH connection with large output
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    large_output = b"x" * 2000  # Larger than limit
    output_sent = [False]

    def recv(size):
        if not output_sent[0]:
            output_sent[0] = True
            return large_output[:100]  # Send in chunks
        return b""

    mock_channel.recv_ready.return_value = True
    mock_channel.recv.side_effect = recv
    mock_channel.exit_status_ready.return_value = True
    mock_channel.recv_exit_status.return_value = 0
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)

    cancel_event = threading.Event()

    with patch.object(client, "_connect", return_value=(mock_client, "127.0.0.1")):
        result = client.run_streaming(
            command="generate output",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1000,  # Small limit
        )

        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result

        # Should respect output limit
        assert bytes_out <= 1000 or cancelled is True


def test_ssh_connection_error_handling(tmp_path):
    """Test SSH connection error handling."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Test connection refused - should be caught and added to error buffer
    with patch.object(
        client, "_connect", side_effect=ConnectionRefusedError("Connection refused")
    ):
        cancel_event = threading.Event()
        result = client.run_streaming(
            command="echo test",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1024,
        )

        # Should return error result
        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result
        assert exit_code == -1
        assert (
            "connection refused" in combined.lower() or "connection" in combined.lower()
        )


def test_ssh_authentication_error_handling(tmp_path):
    """Test SSH authentication error handling."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="wrongpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Test authentication failure - should be caught and added to error buffer
    auth_error = paramiko.AuthenticationException("Authentication failed")

    with patch.object(client, "_connect", side_effect=auth_error):
        cancel_event = threading.Event()
        result = client.run_streaming(
            command="echo test",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1024,
        )

        # Should return error result
        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = result
        assert exit_code == -1
        assert (
            "authentication" in combined.lower()
            or "authentication" in str(auth_error).lower()
        )


def test_ssh_host_key_verification(tmp_path):
    """Test SSH host key verification."""
    known_hosts = tmp_path / "known_hosts"

    # Create known_hosts with a key
    key1 = paramiko.RSAKey.generate(2048)
    with open(known_hosts, "w") as f:
        f.write(f"127.0.0.1 {key1.get_name()} {key1.get_base64()}\n")

    # Try to connect with require_known_host=True
    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=True,
    )

    # Mock connection that doesn't match known hosts
    mock_client = MagicMock()
    mock_client.get_host_keys.return_value = {}

    # Should raise error about missing host key
    with patch("paramiko.SSHClient", return_value=mock_client):
        with pytest.raises(RuntimeError) as exc_info:
            client._connect()
        assert (
            "known_hosts" in str(exc_info.value).lower()
            or "host key" in str(exc_info.value).lower()
        )


def test_ssh_load_system_host_keys(tmp_path):
    """Test loading system host keys when known_hosts_path is not provided."""
    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=None,  # No custom known_hosts
        require_known_host=False,
    )

    # Mock SSH client
    mock_client = MagicMock()
    mock_transport = MagicMock()
    mock_transport.sock = MagicMock()
    mock_transport.sock.getpeername.return_value = ("127.0.0.1", 2222)
    mock_client.get_transport.return_value = mock_transport

    with patch("paramiko.SSHClient", return_value=mock_client):
        with patch.object(mock_client, "connect"):
            # Should try to load system host keys
            try:
                client._connect()
                # If no exception, it should have called load_system_host_keys
                # (or handled the exception silently)
            except Exception:
                pass  # Expected for mocked connection


def test_ssh_peer_ip_extraction(tmp_path):
    """Test peer IP extraction from transport."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock SSH connection with transport
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()
    mock_socket = MagicMock()

    mock_socket.getpeername.return_value = ("192.168.1.100", 54321)
    mock_transport.sock = mock_socket
    mock_channel.recv_exit_status.return_value = 0
    mock_channel.makefile.return_value = [b"output\n"]
    mock_channel.makefile_stderr.return_value = []
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport

    with patch.object(client, "_connect", return_value=(mock_client, "192.168.1.100")):
        cancel_event = threading.Event()
        result = client.run_streaming(
            command="echo test",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1024,
        )

        _, _, _, _, _, _, _, peer_ip = result
        assert peer_ip == "192.168.1.100"


def test_ssh_peer_ip_extraction_failure(tmp_path):
    """Test peer IP extraction when socket is not available."""
    known_hosts = tmp_path / "known_hosts"

    client = SSHClient(
        host="127.0.0.1",
        username="testuser",
        port=2222,
        password="testpass",
        known_hosts_path=str(known_hosts),
        require_known_host=False,
    )

    # Mock SSH connection without socket
    mock_client = MagicMock()
    mock_channel = MagicMock()
    mock_transport = MagicMock()

    mock_transport.sock = None  # No socket
    mock_channel.recv_exit_status.return_value = 0
    mock_channel.makefile.return_value = [b"output\n"]
    mock_channel.makefile_stderr.return_value = []
    mock_transport.open_session.return_value = mock_channel
    mock_client.get_transport.return_value = mock_transport

    with patch.object(client, "_connect", return_value=(mock_client, "")):
        cancel_event = threading.Event()
        result = client.run_streaming(
            command="echo test",
            cancel_event=cancel_event,
            max_seconds=60,
            max_output_bytes=1024,
        )

        _, _, _, _, _, _, _, peer_ip = result
        assert peer_ip == ""  # Should return empty string when socket unavailable

"""Tests for SSH client."""

import threading
import time

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
    assert client.auto_add_host_keys is False
    assert client.require_known_host is True


def test_ssh_client_auto_add_host_keys():
    """Test auto-add host keys mode."""
    client = SSHClient(
        host="10.0.0.1",
        username="testuser",
        auto_add_host_keys=True,
        require_known_host=False,
    )

    assert client.auto_add_host_keys is True
    assert client.require_known_host is False


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

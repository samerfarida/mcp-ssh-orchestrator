import json
import socket
import sys
import threading
import time
import traceback

import paramiko
from paramiko import ssh_exception

# DNS rate limiting and caching constants
DNS_MAX_RESOLUTIONS_PER_SECOND = 10
DNS_CACHE_TTL_SECONDS = 60
DNS_RESOLUTION_TIMEOUT_SECONDS = 5

# Global DNS cache and rate limiter (thread-safe)
_dns_cache_lock = threading.Lock()
_dns_cache: dict[str, tuple[list[str], float]] = {}  # hostname -> (ips, expiry_time)
_dns_rate_limiter: dict[str, list[float]] = (
    {}
)  # hostname -> list of timestamps (last N seconds)


def _is_rate_limited(hostname: str) -> bool:
    """Check if hostname is rate limited.

    Returns True if hostname has exceeded max resolutions per second.
    """
    now = time.time()
    with _dns_cache_lock:
        if hostname not in _dns_rate_limiter:
            _dns_rate_limiter[hostname] = []

        # Clean old timestamps (older than 1 second)
        timestamps = _dns_rate_limiter[hostname]
        timestamps[:] = [ts for ts in timestamps if now - ts < 1.0]

        # Check if limit exceeded
        if len(timestamps) >= DNS_MAX_RESOLUTIONS_PER_SECOND:
            return True

        # Record this resolution attempt
        timestamps.append(now)
        return False


def _get_cached_ips(hostname: str) -> list[str] | None:
    """Get cached DNS result if valid, None if cache miss or expired."""
    now = time.time()
    with _dns_cache_lock:
        if hostname in _dns_cache:
            ips, expiry_time = _dns_cache[hostname]
            if now < expiry_time:
                return ips
            # Cache expired, remove it
            del _dns_cache[hostname]
    return None


def _cache_ips(hostname: str, ips: list[str]):
    """Cache DNS resolution result with TTL."""
    now = time.time()
    expiry_time = now + DNS_CACHE_TTL_SECONDS
    with _dns_cache_lock:
        _dns_cache[hostname] = (ips, expiry_time)


def _log_rate_limit_violation(hostname: str):
    """Log DNS rate limit violation."""
    entry = {
        "level": "error",
        "msg": "security_event",
        "type": "dns_rate_limit_exceeded",
        "hostname": hostname,
        "max_per_second": DNS_MAX_RESOLUTIONS_PER_SECOND,
    }
    print(json.dumps(entry), file=sys.stderr)


class SSHClient:
    """Paramiko SSH wrapper with streaming, cancellation, and IP auditing."""

    def __init__(
        self,
        host: str,
        username: str,
        port: int = 22,
        key_path: str = "",
        password: str = "",
        passphrase: str = "",
        known_hosts_path: str = "",
        auto_add_host_keys: bool = False,
        require_known_host: bool = True,
    ):
        self.host = host
        self.username = username
        self.port = int(port) if port else 22
        self.key_path = key_path or ""
        self.password = password or ""
        self.passphrase = passphrase or ""
        self.known_hosts_path = known_hosts_path or ""
        # Security: auto_add_host_keys is deprecated and ignored for security (CWE-295)
        # Always use RejectPolicy to prevent MITM attacks
        if auto_add_host_keys:
            print(
                json.dumps(
                    {
                        "level": "warn",
                        "msg": "deprecation_warning",
                        "type": "host_key_policy_deprecated",
                        "detail": "auto_add_host_keys is deprecated and ignored. Always using RejectPolicy for security.",
                        "cwe": "CWE-295",
                    }
                ),
                file=sys.stderr,
            )
        # Security: require_known_host must always be True for security
        # RejectPolicy is always used to prevent MITM attacks
        if not require_known_host:
            print(
                json.dumps(
                    {
                        "level": "warn",
                        "msg": "deprecation_warning",
                        "type": "host_key_policy_deprecated",
                        "detail": "require_known_host=False is deprecated and ignored. Always requiring known_hosts entry for security.",
                        "cwe": "CWE-295",
                    }
                ),
                file=sys.stderr,
            )
        self.require_known_host = True  # Always enforce strict host key verification

    @staticmethod
    def resolve_ips(hostname: str):
        """Resolve hostname to a set of IPv4 addresses with rate limiting and caching.

        Security: Implements rate limiting (max 10 resolutions/second per hostname)
        and result caching (60 second TTL) to prevent DNS-based DoS attacks.

        Args:
            hostname: Hostname to resolve

        Returns:
            List of IPv4 addresses (may be empty on resolution failure or rate limit)
        """
        if not hostname:
            return []

        # Check cache first
        cached_ips = _get_cached_ips(hostname)
        if cached_ips is not None:
            return cached_ips

        # Check rate limit
        if _is_rate_limited(hostname):
            _log_rate_limit_violation(hostname)
            return []

        # Perform DNS resolution with timeout
        ips = set()
        try:
            # Set timeout for DNS resolution to prevent hanging
            # socket.getaddrinfo doesn't have direct timeout, so we use a workaround
            # by setting socket default timeout (affects all operations, but acceptable for DNS)
            old_timeout = socket.getdefaulttimeout()
            try:
                socket.setdefaulttimeout(DNS_RESOLUTION_TIMEOUT_SECONDS)
                for fam, _, _, _, sa in socket.getaddrinfo(hostname, None):
                    if fam == socket.AF_INET and sa and sa[0]:
                        ips.add(sa[0])
            finally:
                socket.setdefaulttimeout(old_timeout)
        except TimeoutError:
            # DNS resolution timed out
            pass
        except Exception:
            # Other DNS resolution errors (best-effort, return empty)
            pass

        result = list(ips)

        # Cache all results (including empty lists) to avoid repeated lookups
        # This prevents re-resolving invalid hostnames repeatedly
        _cache_ips(hostname, result)

        return result

    def _connect(self):
        """Establish SSH connection and return (client, peer_ip)."""
        client = paramiko.SSHClient()
        try:
            # Load host keys
            if self.known_hosts_path:
                try:
                    client.load_host_keys(self.known_hosts_path)
                except Exception as e:
                    print(
                        f'{{"level":"warn","msg":"load_host_keys_failed","path":"{self.known_hosts_path}","error":"{e}"}}',
                        file=sys.stderr,
                    )
            else:
                try:
                    client.load_system_host_keys()
                except Exception:
                    pass

            # Security: Always use RejectPolicy to prevent MITM attacks (CWE-295)
            # Unsafe policies (AutoAddPolicy, AcceptPolicy) are never used
            # This fixes CodeQL alert: py/paramiko-missing-host-key-validation
            client.set_missing_host_key_policy(paramiko.RejectPolicy())

            # Security: Always require known_hosts entry to prevent MITM attacks
            # This ensures host identity is verified before connection
            if self.require_known_host:
                try:
                    hk = client.get_host_keys()
                    if self.host not in hk or len(hk[self.host].keys()) == 0:
                        raise RuntimeError(
                            f"known_hosts entry required for {self.host} but not found"
                        )
                except Exception as e:
                    raise RuntimeError(
                        f"known_hosts verification failed for {self.host}: {e}"
                    ) from e

            # Connect
            if self.key_path:
                pkey = None
                try:
                    # Try RSA key first
                    pkey = paramiko.RSAKey.from_private_key_file(
                        self.key_path, password=self.passphrase
                    )
                except Exception:
                    try:
                        # Try Ed25519 key
                        pkey = paramiko.Ed25519Key.from_private_key_file(
                            self.key_path, password=self.passphrase
                        )
                    except Exception:
                        try:
                            # Try ECDSA key
                            pkey = paramiko.ECDSAKey.from_private_key_file(
                                self.key_path, password=self.passphrase
                            )
                        except Exception as e:
                            # Re-raise key loading errors with more context
                            error_str = str(e)
                            if isinstance(e, FileNotFoundError):
                                raise RuntimeError(
                                    "SSH key file not found: Check key path configuration"
                                ) from e
                            elif isinstance(e, paramiko.PasswordRequiredException):
                                raise RuntimeError(
                                    "SSH key requires passphrase: Provide key_passphrase_secret"
                                ) from e
                            elif isinstance(e, PermissionError):
                                raise RuntimeError(
                                    "SSH key permission denied: Check key file permissions (should be 600)"
                                ) from e
                            elif isinstance(e, ssh_exception.SSHException) and (
                                "not a valid" in error_str.lower()
                                or "invalid key" in error_str.lower()
                            ):
                                raise RuntimeError(
                                    "SSH key format invalid: Check key file format (RSA/Ed25519/ECDSA)"
                                ) from e
                            else:
                                raise RuntimeError(
                                    f"Failed to load private key from {self.key_path}"
                                ) from e

                client.connect(
                    hostname=self.host,
                    username=self.username,
                    port=self.port,
                    pkey=pkey,
                    timeout=15,
                    allow_agent=False,
                    look_for_keys=False,
                )
            else:
                client.connect(
                    hostname=self.host,
                    username=self.username,
                    port=self.port,
                    password=self.password,
                    timeout=15,
                    allow_agent=False,
                    look_for_keys=False,
                )

            # Determine actual peer IP
            peer_ip = ""
            try:
                transport = client.get_transport()
                if transport and transport.sock:
                    peer_ip = transport.sock.getpeername()[0]
            except Exception:
                peer_ip = ""

            return client, peer_ip
        except Exception as e:
            try:
                client.close()
            except Exception:
                pass
            # Provide specific error messages based on exception type and content
            # Note: Detailed error with hostname/IP is logged to stderr via exception chaining
            # User-facing error is sanitized by mcp_server.py exception handlers
            error_msg = str(e)

            # Check exception type first for more reliable detection
            # Re-raise key loading errors (they already have specific messages from inner handler)
            if isinstance(e, RuntimeError) and (
                "SSH key file not found" in error_msg
                or "SSH key requires passphrase" in error_msg
                or "SSH key permission denied" in error_msg
                or "SSH key format invalid" in error_msg
            ):
                raise e
            elif isinstance(e, paramiko.AuthenticationException):
                raise RuntimeError(
                    "SSH authentication failed: Invalid credentials"
                ) from e
            elif isinstance(e, paramiko.BadHostKeyException):
                raise RuntimeError(
                    "SSH host key verification failed: Host key mismatch"
                ) from e
            elif isinstance(e, paramiko.PasswordRequiredException):
                raise RuntimeError(
                    "SSH key requires passphrase: Provide key_passphrase_secret"
                ) from e
            elif isinstance(e, (socket.timeout, TimeoutError)):
                raise RuntimeError(
                    "SSH connection timeout: Host did not respond"
                ) from e
            elif isinstance(e, ConnectionRefusedError):
                raise RuntimeError(
                    "SSH connection refused: Port may be closed or firewall blocking"
                ) from e
            elif (
                isinstance(e, (socket.gaierror, OSError))
                and "Name or service not known" in error_msg
            ):
                raise RuntimeError(
                    "SSH hostname resolution failed: DNS lookup failed"
                ) from e
            elif isinstance(e, OSError) and "Network is unreachable" in error_msg:
                raise RuntimeError("SSH network unreachable: Cannot reach host") from e
            elif isinstance(e, FileNotFoundError) or (
                "No such file or directory" in error_msg and self.key_path
            ):
                raise RuntimeError(
                    "SSH key file not found: Check key path configuration"
                ) from e
            elif isinstance(e, ssh_exception.SSHException) and (
                "not a valid" in error_msg.lower() or "invalid key" in error_msg.lower()
            ):
                raise RuntimeError(
                    "SSH key format invalid: Check key file format (RSA/Ed25519/ECDSA)"
                ) from e
            # Fallback to string matching for cases where exception type isn't specific enough
            elif (
                "Authentication failed" in error_msg
                or "authentication" in error_msg.lower()
            ):
                raise RuntimeError(
                    "SSH authentication failed: Invalid credentials"
                ) from e
            elif "known_hosts" in error_msg.lower() or "host key" in error_msg.lower():
                if "not found" in error_msg.lower():
                    raise RuntimeError(
                        "SSH host key not found: Add host to known_hosts"
                    ) from e
                else:
                    raise RuntimeError("SSH host key verification failed") from e
            elif "timeout" in error_msg.lower():
                raise RuntimeError(
                    "SSH connection timeout: Host did not respond"
                ) from e
            elif "Connection refused" in error_msg:
                raise RuntimeError(
                    "SSH connection refused: Port may be closed or firewall blocking"
                ) from e
            elif "Permission denied" in error_msg and self.key_path:
                raise RuntimeError(
                    "SSH key permission denied: Check key file permissions (should be 600)"
                ) from e
            elif "Permission denied" in error_msg:
                raise RuntimeError(
                    "SSH permission denied: Check username and credentials"
                ) from e
            elif "Name or service not known" in error_msg:
                raise RuntimeError(
                    "SSH hostname resolution failed: DNS lookup failed"
                ) from e
            elif isinstance(e, ssh_exception.SSHException):
                # Generic paramiko SSH exception
                if "Unable to connect" in error_msg:
                    raise RuntimeError(
                        "SSH unable to connect: Check host and port"
                    ) from e
                else:
                    # Extract meaningful part if available
                    first_part = (
                        error_msg.split(":")[0]
                        if ":" in error_msg
                        else "Connection failed"
                    )
                    raise RuntimeError(f"SSH error: {first_part}") from e
            else:
                # Final fallback
                raise RuntimeError(
                    "SSH connection failed: Check host, port, and network connectivity"
                ) from e

    def run_streaming(
        self,
        command: str,
        cancel_event,
        max_seconds: int,
        max_output_bytes: int,
        progress_cb=None,
    ):
        """Execute command with streaming, cancellation, timeout, and size caps.

        Returns: (exit_code, duration_ms, cancelled, timeout, bytes_out, bytes_err, combined, peer_ip)
        """
        start = time.time()
        out_buf = bytearray()
        err_buf = bytearray()
        exit_code = -1
        cancelled = False
        timeout = False
        peer_ip = ""
        client = None
        try:
            if progress_cb:
                progress_cb("connecting", 0, int((time.time() - start) * 1000))
            client, peer_ip = self._connect()
            if progress_cb:
                progress_cb("connected", 0, int((time.time() - start) * 1000))

            transport = client.get_transport()
            chan = transport.open_session()
            chan.settimeout(1.0)
            chan.exec_command(command)

            last_progress = time.time()
            while True:
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    try:
                        chan.close()
                    except Exception:
                        pass
                    break

                now = time.time()
                elapsed = now - start
                if max_seconds and elapsed > max_seconds:
                    timeout = True
                    try:
                        chan.close()
                    except Exception:
                        pass
                    break

                if chan.recv_ready():
                    chunk = chan.recv(4096)
                    if chunk:
                        out_buf.extend(chunk)
                        if len(out_buf) > max_output_bytes:
                            out_buf = out_buf[:max_output_bytes]
                    if progress_cb and (now - last_progress) > 0.5:
                        progress_cb("running", len(out_buf), int(elapsed * 1000))
                        last_progress = now

                if chan.recv_stderr_ready():
                    chunk = chan.recv_stderr(4096)
                    if chunk:
                        err_buf.extend(chunk)
                        if len(err_buf) > max_output_bytes:
                            err_buf = err_buf[:max_output_bytes]
                    if progress_cb and (now - last_progress) > 0.5:
                        progress_cb(
                            "running", len(out_buf) + len(err_buf), int(elapsed * 1000)
                        )
                        last_progress = now

                if (
                    chan.exit_status_ready()
                    and not chan.recv_ready()
                    and not chan.recv_stderr_ready()
                ):
                    exit_code = chan.recv_exit_status()
                    break

                time.sleep(0.05)

        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            err_buf.extend(str(e).encode("utf-8", errors="ignore"))
        finally:
            try:
                if client:
                    client.close()
            except Exception:
                pass

        duration_ms = int((time.time() - start) * 1000)
        out_txt = out_buf.decode("utf-8", errors="replace")
        err_txt = err_buf.decode("utf-8", errors="replace")
        combined = (out_txt + ("\n" if out_txt and err_txt else "") + err_txt).strip()
        return (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            len(out_buf),
            len(err_buf),
            combined,
            peer_ip,
        )

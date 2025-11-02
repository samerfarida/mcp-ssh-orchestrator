import socket
import sys
import time
import traceback

import paramiko


class AcceptPolicy(paramiko.MissingHostKeyPolicy):
    """Accept unknown host keys without saving them."""

    def missing_host_key(self, client, hostname, key):
        # Accept the key but don't save it
        pass


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
        self.auto_add_host_keys = bool(auto_add_host_keys)
        self.require_known_host = bool(require_known_host)

    @staticmethod
    def resolve_ips(hostname: str):
        """Resolve hostname to a set of IPv4 addresses (best-effort)."""
        ips = set()
        try:
            for fam, _, _, _, sa in socket.getaddrinfo(hostname, None):
                if fam == socket.AF_INET and sa and sa[0]:
                    ips.add(sa[0])
        except Exception:
            pass
        return list(ips)

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

            # Strict or permissive behavior
            if self.auto_add_host_keys:
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            elif not self.require_known_host:
                client.set_missing_host_key_policy(AcceptPolicy())
            else:
                client.set_missing_host_key_policy(paramiko.RejectPolicy())

            # If strict is requested, ensure an entry exists before connecting
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
            # Provide generic error messages (sensitive details logged separately)
            # Note: Detailed error with hostname/IP is logged to stderr via exception chaining
            # User-facing error is sanitized by mcp_server.py exception handlers
            if "Authentication failed" in str(e):
                raise RuntimeError("SSH authentication failed") from e
            elif "No such file or directory" in str(e) and self.key_path:
                raise RuntimeError("SSH key file not found") from e
            elif "Permission denied" in str(e):
                raise RuntimeError("SSH permission denied") from e
            elif "Connection refused" in str(e):
                raise RuntimeError("SSH connection refused") from e
            elif "Name or service not known" in str(e):
                raise RuntimeError("SSH hostname not found") from e
            else:
                raise RuntimeError("SSH connection failed") from e

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

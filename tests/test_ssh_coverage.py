"""Additional SSH client tests for improved coverage."""

import threading
import time
from unittest.mock import MagicMock, patch

from mcp_ssh.ssh_client import SSHClient


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

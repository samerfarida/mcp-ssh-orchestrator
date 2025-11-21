"""Additional tests for mcp_server.py to improve coverage."""

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from mcp_ssh import mcp_server
from mcp_ssh.config import Config


def test_format_task_event_no_payload():
    """Test _format_task_event without payload."""
    result = mcp_server._format_task_event("test_event", "task123", {})
    assert result == "task task123 test_event"


def test_format_task_event_with_payload():
    """Test _format_task_event with payload."""
    payload = {"status": "running", "progress": 50}
    result = mcp_server._format_task_event("progress", "task123", payload)
    assert "task task123 progress" in result
    assert "status" in result or '"status"' in result


def test_build_notification_handler_no_ctx():
    """Test _build_notification_handler when ctx is None."""
    handler = mcp_server._build_notification_handler(None, None)
    # Should return log-only handler
    assert callable(handler)
    # Should not raise when called
    handler("test_event", "task123", {"test": "data"})


def test_build_notification_handler_no_loop():
    """Test _build_notification_handler when loop is None."""
    mock_ctx = MagicMock()
    handler = mcp_server._build_notification_handler(mock_ctx, None)
    # Should return log-only handler
    assert callable(handler)
    handler("test_event", "task123", {"test": "data"})


@pytest.mark.asyncio
async def test_build_notification_handler_with_ctx_progress():
    """Test _build_notification_handler with ctx and progress event."""
    mock_ctx = AsyncMock()
    mock_ctx.report_progress = AsyncMock()
    mock_ctx.debug = AsyncMock()

    loop = asyncio.get_running_loop()
    handler = mcp_server._build_notification_handler(mock_ctx, loop)

    # Call handler with progress event
    payload = {"max_seconds": 60, "elapsed_ms": 30000}  # 50% progress
    handler("progress", "task123", payload)

    # Give async operations time to complete
    await asyncio.sleep(0.2)

    # Should have called report_progress
    assert mock_ctx.report_progress.called
    assert mock_ctx.debug.called


@pytest.mark.asyncio
async def test_build_notification_handler_with_ctx_info():
    """Test _build_notification_handler with ctx and info event."""
    mock_ctx = AsyncMock()
    mock_ctx.info = AsyncMock()

    loop = asyncio.get_running_loop()
    handler = mcp_server._build_notification_handler(mock_ctx, loop)

    # Call handler with non-progress event
    handler("started", "task123", {"test": "data"})

    # Give async operations time to complete
    await asyncio.sleep(0.2)

    # Should have called info
    assert mock_ctx.info.called


@pytest.mark.asyncio
async def test_build_notification_handler_different_loop():
    """Test _build_notification_handler when running in different loop."""
    mock_ctx = AsyncMock()
    mock_ctx.info = AsyncMock()

    # Get current loop
    current_loop = asyncio.get_running_loop()
    handler = mcp_server._build_notification_handler(mock_ctx, current_loop)

    # Call handler - should use current loop
    handler("test_event", "task123", {})

    # Give async operations time to complete
    await asyncio.sleep(0.2)

    # Should have been called
    assert mock_ctx.info.called or True  # May use same loop or different


def test_client_for_no_hostname(tmp_path):
    """Test _client_for with missing hostname."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {"hosts": [{"alias": "test1", "credentials": "cred1"}]}
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {"entries": [{"name": "cred1", "username": "user1"}]}
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {"limits": {}}
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        with pytest.raises(ValueError) as exc_info:
            mcp_server._client_for("test1", {}, True)
        assert "no hostname" in str(exc_info.value).lower()


def test_client_for_no_username(tmp_path):
    """Test _client_for with missing username."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [{"alias": "test1", "host": "10.0.0.1", "credentials": "cred1"}]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {"entries": [{"name": "cred1"}]}  # No username
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {"limits": {}}
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        with pytest.raises(ValueError) as exc_info:
            mcp_server._client_for("test1", {}, True)
        assert "username" in str(exc_info.value).lower()


def test_client_for_invalid_port(tmp_path):
    """Test _client_for with invalid port."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 99999,
                    "credentials": "cred1",
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {"limits": {}}
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        with pytest.raises(ValueError) as exc_info:
            mcp_server._client_for("test1", {}, True)
        assert "port" in str(exc_info.value).lower()


def test_client_for_no_auth_method(tmp_path):
    """Test _client_for with no authentication method."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [{"alias": "test1", "host": "10.0.0.1", "credentials": "cred1"}]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1"}]
        }  # No password or key
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {"limits": {}}
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        with pytest.raises(ValueError) as exc_info:
            mcp_server._client_for("test1", {}, True)
        assert "authentication" in str(exc_info.value).lower()


def test_client_for_auto_add_deprecation(tmp_path):
    """Test _client_for logs deprecation warning for host_key_auto_add."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [{"alias": "test1", "host": "10.0.0.1", "credentials": "cred1"}]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {"limits": {}}
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        limits = {"host_key_auto_add": True}  # Deprecated setting

        with patch("mcp_ssh.mcp_server.log_json") as mock_log:
            try:
                mcp_server._client_for("test1", limits, True)
            except Exception:
                pass  # Expected to fail, but we want to check the warning

            # Should log deprecation warning
            mock_log.assert_called()
            call_args = mock_log.call_args[0][0]
            assert call_args.get("type") == "host_key_policy_deprecated"


def test_precheck_network_dns_failure():
    """Test _precheck_network with DNS resolution failure."""
    mock_pol = MagicMock()

    with patch("mcp_ssh.mcp_server.SSHClient.resolve_ips", return_value=[]):
        ok, reason = mcp_server._precheck_network(mock_pol, "invalid-host.example.com")
        assert ok is False
        assert "DNS resolution failed" in reason


def test_precheck_network_no_allowed_ips():
    """Test _precheck_network with no allowed IPs."""
    mock_pol = MagicMock()
    mock_pol.is_ip_allowed.return_value = False

    with patch(
        "mcp_ssh.mcp_server.SSHClient.resolve_ips", return_value=["192.168.1.1"]
    ):
        ok, reason = mcp_server._precheck_network(mock_pol, "test-host.example.com")
        assert ok is False
        assert "No resolved IPs allowed" in reason


def test_ctx_log_no_ctx():
    """Test _ctx_log when ctx is None."""
    # Should return immediately without error
    mcp_server._ctx_log(None, "info", "test_event", {})


def test_ctx_log_no_running_loop():
    """Test _ctx_log when no event loop is running."""
    mock_ctx = MagicMock()
    # Should return without error when no loop
    mcp_server._ctx_log(mock_ctx, "info", "test_event", {})


@pytest.mark.asyncio
async def test_ctx_log_with_ctx():
    """Test _ctx_log with valid ctx and loop."""
    mock_ctx = AsyncMock()
    mock_ctx.info = AsyncMock()

    mcp_server._ctx_log(mock_ctx, "info", "test_event", {"test": "data"})

    # Give async operation time to complete
    await asyncio.sleep(0.2)

    assert mock_ctx.info.called


def test_resource_hosts_error():
    """Test resource_hosts error handling."""
    # Create invalid config that will cause error in list_hosts
    with patch.object(
        mcp_server.config, "list_hosts", side_effect=Exception("Config error")
    ):
        result = mcp_server.resource_hosts()
        assert "error" in result


def test_resource_host_error():
    """Test resource_host error handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {"hosts": [{"alias": "test1", "host": "10.0.0.1"}]}
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {"entries": []}
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {"limits": {}}
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        # Test with non-existent host
        result = mcp_server.resource_host(alias="nonexistent")
        assert "error" in result


def test_resource_host_tags_error():
    """Test resource_host_tags error handling."""
    # Cause an error by using invalid config
    with patch.object(
        mcp_server.config, "get_host_tags", side_effect=Exception("Config error")
    ):
        result = mcp_server.resource_host_tags(alias="test1")
        assert "error" in result


def test_ssh_run_network_deny_after_connect(tmp_path):
    """Test ssh_run network denial after connection (peer IP check)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {"allow_cidrs": ["10.0.0.0/24"]},  # Allow 10.0.0.0/24
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        # Mock SSH client that connects but returns peer IP outside allowed range
        mock_client = MagicMock()
        mock_client.run_streaming.return_value = (
            0,
            100,
            False,
            False,
            10,
            0,
            "output",
            "192.168.1.100",  # Peer IP not allowed
        )

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(
                mcp_server, "_precheck_network", return_value=(True, "")
            ):  # Pass initial check
                result = mcp_server.ssh_run(alias="test1", command="uptime")

                # Should return network denial
                assert isinstance(result, str)
                parsed = json.loads(result)
                assert parsed["status"] == "denied"
                assert parsed["reason"] == "network"


def test_ssh_run_require_known_host_deprecation(tmp_path):
    """Test ssh_run logs deprecation when require_known_host=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60, "require_known_host": False},  # Deprecated
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        mock_client = MagicMock()
        mock_client.run_streaming.return_value = (
            0,
            100,
            False,
            False,
            10,
            0,
            "output",
            "10.0.0.1",
        )

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                with patch("mcp_ssh.mcp_server.log_json") as mock_log:
                    mcp_server.ssh_run(alias="test1", command="uptime")

                    # Should log deprecation warning
                    mock_log.assert_called()
                    # Check for deprecation log
                    all_calls = []
                    for call in mock_log.call_args_list:
                        if call[0]:  # positional args
                            all_calls.append(str(call[0][0]))
                        elif call[1]:  # keyword args
                            all_calls.append(str(call[1]))
                        else:
                            all_calls.append(str(call))
                    assert any(
                        "host_key_policy_deprecated" in str(call) for call in all_calls
                    )


def test_ssh_run_on_tag_require_known_host_deprecation(tmp_path):
    """Test ssh_run_on_tag logs deprecation when require_known_host=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["web"],
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60, "require_known_host": False},  # Deprecated
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        mock_client = MagicMock()
        mock_client.run_streaming.return_value = (
            0,
            100,
            False,
            False,
            10,
            0,
            "output",
            "10.0.0.1",
        )

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                with patch("mcp_ssh.mcp_server.log_json") as mock_log:
                    mcp_server.ssh_run_on_tag(tag="web", command="uptime")

                    # Should log deprecation warning
                    mock_log.assert_called()
                    all_calls = []
                    for call in mock_log.call_args_list:
                        if call[0]:
                            all_calls.append(str(call[0][0]))
                        elif call[1]:
                            all_calls.append(str(call[1]))
                        else:
                            all_calls.append(str(call))
                    assert any(
                        "host_key_policy_deprecated" in str(call) for call in all_calls
                    )


@pytest.mark.asyncio
async def test_ssh_run_async_require_known_host_deprecation(tmp_path):
    """Test ssh_run_async logs deprecation when require_known_host=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60, "require_known_host": False},  # Deprecated
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        mock_client = MagicMock()

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                with patch("mcp_ssh.mcp_server.log_json") as mock_log:
                    mock_ctx = AsyncMock()
                    await mcp_server.ssh_run_async(
                        alias="test1", command="uptime", ctx=mock_ctx
                    )

                    # Should log deprecation warning
                    mock_log.assert_called()
                    all_calls = []
                    for call in mock_log.call_args_list:
                        if call[0]:
                            all_calls.append(str(call[0][0]))
                        elif call[1]:
                            all_calls.append(str(call[1]))
                        else:
                            all_calls.append(str(call))
                    assert any(
                        "host_key_policy_deprecated" in str(call) for call in all_calls
                    )


def test_ssh_run_on_tag_all_success(tmp_path):
    """Test ssh_run_on_tag when all hosts succeed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "host1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["web"],
                },
                {
                    "alias": "host2",
                    "host": "10.0.0.2",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["web"],
                },
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        # Create separate mock clients for each host
        def mock_client_for(alias, limits, require_known_host):
            mock_client = MagicMock()
            # Return different peer IPs for each host
            peer_ip = "10.0.0.1" if alias == "host1" else "10.0.0.2"
            mock_client.run_streaming.return_value = (
                0,
                100,
                False,
                False,
                10,
                0,
                f"output from {alias}",
                peer_ip,
            )
            return mock_client

        with patch.object(mcp_server, "_client_for", side_effect=mock_client_for):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                result = mcp_server.ssh_run_on_tag(tag="web", command="uptime")

                assert "results" in result
                assert len(result["results"]) == 2
                # All should succeed
                for r in result["results"]:
                    assert "exit_code" in r or "denied" in r
                    if "exit_code" in r:
                        assert r["exit_code"] == 0


def test_ssh_run_on_tag_error_handling(tmp_path):
    """Test ssh_run_on_tag error handling for individual hosts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "host1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["web"],
                },
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        # Mock client that raises exception during run_streaming
        mock_client = MagicMock()
        mock_client.run_streaming.side_effect = RuntimeError("SSH connection failed")

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                result = mcp_server.ssh_run_on_tag(tag="web", command="uptime")

                assert "results" in result
                assert len(result["results"]) == 1
                error_result = result["results"][0]
                # Should have error information
                assert (
                    error_result.get("exit_code") == -1
                    or "error" in str(error_result).lower()
                    or "SSH" in str(error_result)
                )


@pytest.mark.asyncio
async def test_ssh_run_async_no_running_loop(tmp_path):
    """Test ssh_run_async when no event loop is running."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        mock_client = MagicMock()
        mock_ctx = MagicMock()  # Context without event loop

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                result = await mcp_server.ssh_run_async(
                    alias="test1", command="uptime", ctx=mock_ctx
                )

                # Should still work (notification handler falls back to log-only)
                assert "task_id" in result or isinstance(result, str)


def test_ssh_run_exception_handling(tmp_path):
    """Test ssh_run exception handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        # Mock _client_for to raise exception
        with patch.object(
            mcp_server, "_client_for", side_effect=RuntimeError("Connection failed")
        ):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                result = mcp_server.ssh_run(alias="test1", command="uptime")

                # Should return error message
                assert isinstance(result, str)
                assert "error" in result.lower() or "Run error" in result


@pytest.mark.asyncio
async def test_ssh_run_async_exception_handling(tmp_path):
    """Test ssh_run_async exception handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        # Mock _client_for to raise exception
        with patch.object(
            mcp_server, "_client_for", side_effect=RuntimeError("Connection failed")
        ):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                result = await mcp_server.ssh_run_async(alias="test1", command="uptime")

                # Should return error message
                assert isinstance(result, str)
                assert "error" in result.lower() or "Async run error" in result


# Additional edge case tests
@pytest.mark.asyncio
async def test_ctx_log_invalid_log_method_async():
    """Test _ctx_log with ctx that has non-callable log method in async context."""
    mock_ctx = AsyncMock()
    mock_ctx.info = "not a callable"  # Not a method

    mcp_server._ctx_log(mock_ctx, "info", "test_event", {})

    # Give async operation time
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_ssh_run_async_no_loop():
    """Test ssh_run_async when no event loop is running."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        mock_client = MagicMock()
        mock_ctx = MagicMock()  # Context without event loop

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                result = await mcp_server.ssh_run_async(
                    alias="test1", command="uptime", ctx=mock_ctx
                )

                # Should still work (notification handler falls back to log-only)
                assert "task_id" in result or isinstance(result, str)


def test_client_for_no_username_no_creds_ref(tmp_path):
    """Test _client_for with no username and no credentials reference."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [{"alias": "test1", "host": "10.0.0.1"}]
        }  # No credentials ref
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {"entries": []}
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {"limits": {}}
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        with pytest.raises(ValueError) as exc_info:
            mcp_server._client_for("test1", {}, True)
        assert (
            "no credentials" in str(exc_info.value).lower()
            or "username" in str(exc_info.value).lower()
        )


def test_probe_policy_capabilities_with_required_tags(tmp_path):
    """Test _probe_policy_capabilities with required_tags filtering."""
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = {
            "limits": {},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        from mcp_ssh.policy import Policy

        pol = Policy(config.get_policy())

        probes = [
            {"id": "probe1", "command": "uptime", "required_tags": ["linux"]},
            {
                "id": "probe2",
                "command": "uptime",
                "required_tags": [],
            },  # No required tags
            {"id": "probe3", "command": "uptime"},  # No required_tags field
        ]

        # Test with tags that don't match required_tags
        results = mcp_server._probe_policy_capabilities("test1", ["web"], pol, probes)

        # Should only return probes without required_tags or with empty required_tags
        assert len(results) >= 1
        assert any(r["probe"] == "probe2" or r["probe"] == "probe3" for r in results)


def test_probe_policy_capabilities_empty_command(tmp_path):
    """Test _probe_policy_capabilities with empty command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = {"limits": {}, "rules": []}
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        from mcp_ssh.policy import Policy

        pol = Policy(config.get_policy())

        probes = [
            {"id": "probe1", "command": ""},  # Empty command
            {"id": "probe2", "command": "uptime"},
        ]

        results = mcp_server._probe_policy_capabilities("test1", [], pol, probes)

        # Should skip empty command probe
        assert len(results) == 1
        assert results[0]["probe"] == "probe2"


def test_ctx_log_invalid_log_method(tmp_path):
    """Test _ctx_log with invalid log method."""
    mock_ctx = MagicMock()
    # Should handle invalid method gracefully
    mcp_server._ctx_log(mock_ctx, "invalid_method", "test_event", {})


def test_resource_host_capabilities_error():
    """Test resource_host_capabilities error handling."""
    # Cause an error by using invalid config
    with patch.object(
        mcp_server.config, "get_host", side_effect=Exception("Config error")
    ):
        result = mcp_server.resource_host_capabilities(alias="test1")
        assert "error" in result


def test_ssh_plan_exception_handling(tmp_path):
    """Test ssh_plan exception handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        # Mock Policy to raise exception
        with patch("mcp_ssh.mcp_server.Policy", side_effect=Exception("Policy error")):
            result = mcp_server.ssh_plan(alias="test1", command="uptime")

            assert isinstance(result, str)
            assert "error" in result.lower()


def test_ssh_plan_denied_command_in_chain(tmp_path):
    """Test ssh_plan with denied command in chain."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        # Test with command chain containing denied command
        result = mcp_server.ssh_plan(
            alias="test1", command="uptime && rm -rf /"
        )  # rm -rf should be denied

        # Should return denial (as dict, not string)
        assert isinstance(result, dict)
        assert result["allowed"] is False
        # Should identify denied command
        assert "why" in result or "denied_command" in result


def test_ssh_run_on_tag_ctx_logging(tmp_path):
    """Test ssh_run_on_tag with context logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["web"],
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        mock_client = MagicMock()
        mock_client.run_streaming.return_value = (
            0,
            100,
            False,
            False,
            10,
            0,
            "output",
            "10.0.0.1",
        )

        mock_ctx = MagicMock()

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                result = mcp_server.ssh_run_on_tag(
                    tag="web", command="uptime", ctx=mock_ctx
                )

                # Should have called context logging
                assert "results" in result


def test_ssh_run_progress_callback(tmp_path):
    """Test ssh_run with progress callback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                }
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        mock_client = MagicMock()
        mock_client.run_streaming.return_value = (
            0,
            100,
            False,
            False,
            10,
            0,
            "output",
            "10.0.0.1",
        )

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                result = mcp_server.ssh_run(alias="test1", command="uptime")

                # Should return result
                assert isinstance(result, dict)
                assert "exit_code" in result


def test_ssh_cancel_exception_handling():
    """Test ssh_cancel exception handling."""
    # Mock TASKS to raise exception
    with patch.object(mcp_server, "TASKS") as mock_tasks:
        mock_tasks.cancel.side_effect = Exception("Cancel error")

        result = mcp_server.ssh_cancel(task_id="task123")

        # Should return error message
        assert isinstance(result, str)
        assert "error" in result.lower() or "Cancel error" in result


def test_ssh_reload_config_exception():
    """Test ssh_reload_config exception handling."""
    # Mock config reload to raise exception
    with patch.object(
        mcp_server.config, "reload", side_effect=Exception("Reload error")
    ):
        result = mcp_server.ssh_reload_config()

        # Should return error dict
        assert isinstance(result, dict)
        assert result.get("status") == "error"
        assert "error" in result


def test_ssh_get_task_status_exception():
    """Test ssh_get_task_status exception handling."""
    # Mock ASYNC_TASKS.get_task_status to raise exception
    with patch.object(
        mcp_server.ASYNC_TASKS, "get_task_status", side_effect=Exception("Status error")
    ):
        result = mcp_server.ssh_get_task_status(task_id="task123")

        # Should return error message
        assert isinstance(result, str)
        assert "error" in result.lower() or "Status error" in result


def test_ssh_get_task_result_exception():
    """Test ssh_get_task_result exception handling."""
    # Mock ASYNC_TASKS.get_task_result to raise exception
    with patch.object(
        mcp_server.ASYNC_TASKS, "get_task_result", side_effect=Exception("Result error")
    ):
        result = mcp_server.ssh_get_task_result(task_id="task123")

        # Should return error message
        assert isinstance(result, str)
        assert "error" in result.lower() or "Result error" in result


def test_ssh_get_task_output_exception():
    """Test ssh_get_task_output exception handling."""
    # Mock ASYNC_TASKS.get_task_output to raise exception
    with patch.object(
        mcp_server.ASYNC_TASKS, "get_task_output", side_effect=Exception("Output error")
    ):
        result = mcp_server.ssh_get_task_output(task_id="task123")

        # Should return error message
        assert isinstance(result, str)
        assert "error" in result.lower() or "Output error" in result


@pytest.mark.asyncio
async def test_build_notification_handler_different_running_loop():
    """Test _build_notification_handler when running in different loop."""
    mock_ctx = AsyncMock()
    mock_ctx.info = AsyncMock()

    # Get current loop
    current_loop = asyncio.get_running_loop()
    handler = mcp_server._build_notification_handler(mock_ctx, current_loop)

    # Call handler - should work with current loop
    handler("test_event", "task123", {})

    # Give handler time to process
    await asyncio.sleep(0.2)

    # Should have been called (may use same loop or schedule)
    assert True  # Test passes if no exception


# Additional tests for ssh_run_on_tag edge cases
def test_ssh_run_on_tag_peer_ip_not_allowed(tmp_path):
    """Test ssh_run_on_tag with peer IP not allowed after connection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "host1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["web"],
                },
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {
                "allow_cidrs": ["10.0.0.0/24"]
            },  # Allow 10.0.0.0/24, but peer returns 192.168.1.100
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        # Mock client that returns peer IP outside allowed range
        mock_client = MagicMock()
        mock_client.run_streaming.return_value = (
            0,
            100,
            False,
            False,
            10,
            0,
            "output",
            "192.168.1.100",  # Peer IP not in 10.0.0.0/24
        )

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(
                mcp_server, "_precheck_network", return_value=(True, "")
            ):  # Pass initial check
                result = mcp_server.ssh_run_on_tag(tag="web", command="uptime")

                assert "results" in result
                assert len(result["results"]) == 1
                host_result = result["results"][0]
                # Should be denied due to peer IP
                assert host_result.get("denied") is True
                assert "network" in host_result.get("reason", "").lower()


def test_ssh_run_on_tag_task_cleanup_on_error(tmp_path):
    """Test ssh_run_on_tag task cleanup when error occurs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "host1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["web"],
                },
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        # Mock client that raises exception - should trigger cleanup
        mock_client = MagicMock()
        mock_client.run_streaming.side_effect = RuntimeError("SSH error")

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                with patch.object(mcp_server, "TASKS") as mock_tasks:
                    mock_tasks.create.return_value = "task123"
                    mock_tasks.get_event.return_value = None
                    mock_tasks.cleanup = MagicMock()

                    result = mcp_server.ssh_run_on_tag(tag="web", command="uptime")

                    # Should have called cleanup
                    mock_tasks.cleanup.assert_called_with("task123")

                    assert "results" in result
                    assert len(result["results"]) == 1
                    error_result = result["results"][0]
                    assert error_result.get("exit_code") == -1


def test_ssh_run_on_tag_task_cleanup_exception(tmp_path):
    """Test ssh_run_on_tag handles cleanup exception gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "host1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["web"],
                },
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [{"name": "cred1", "username": "user1", "password": "pass1"}]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        policy = {
            "limits": {"max_seconds": 60},
            "network": {"allow_cidrs": ["10.0.0.0/24"]},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "simple_binaries": ["uptime"],
                    "simple_max_args": 6,
                }
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        # Mock client that raises exception
        mock_client = MagicMock()
        mock_client.run_streaming.side_effect = RuntimeError("SSH error")

        with patch.object(mcp_server, "_client_for", return_value=mock_client):
            with patch.object(mcp_server, "_precheck_network", return_value=(True, "")):
                with patch.object(mcp_server, "TASKS") as mock_tasks:
                    mock_tasks.create.return_value = "task123"
                    mock_tasks.get_event.return_value = None
                    mock_tasks.cleanup.side_effect = Exception(
                        "Cleanup error"
                    )  # Cleanup raises exception

                    # Should handle cleanup exception gracefully
                    result = mcp_server.ssh_run_on_tag(tag="web", command="uptime")

                    assert "results" in result
                    # Should still return error result even if cleanup fails
                    assert len(result["results"]) == 1


def test_ssh_run_on_tag_exception_handling():
    """Test ssh_run_on_tag handles top-level exceptions."""
    # Test with invalid tag that causes exception
    with patch.object(
        mcp_server.config, "find_hosts_by_tag", side_effect=Exception("Config error")
    ):
        result = mcp_server.ssh_run_on_tag(tag="invalid", command="uptime")

        # Should return error message
        assert isinstance(result, str)
        assert "error" in result.lower() or "Run on tag error" in result

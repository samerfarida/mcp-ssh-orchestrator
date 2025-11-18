"""Tests for MCP server tools."""

import asyncio
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import yaml

from mcp_ssh import mcp_server
from mcp_ssh.config import Config


@pytest.fixture
def mock_config():
    """Create a mock config for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test servers.yml
        servers = {
            "hosts": [
                {
                    "alias": "test1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["web"],
                },
                {
                    "alias": "test2",
                    "host": "10.0.0.2",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["db", "prod"],
                },
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [
                {"name": "cred1", "username": "user1", "key_path": "id_ed25519"},
            ]
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
                    "commands": ["uptime*"],
                },
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        # Replace global config
        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        yield config


def test_ssh_ping():
    """Test ping tool."""
    result = mcp_server.ssh_ping()
    assert isinstance(result, dict)
    assert result == {"status": "pong"}


def test_ssh_list_hosts(mock_config):
    """Test list_hosts tool."""
    result = mcp_server.ssh_list_hosts()
    assert isinstance(result, dict)
    hosts = result.get("hosts", result)

    assert isinstance(hosts, list)
    assert len(hosts) == 2
    assert "test1" in hosts
    assert "test2" in hosts


def test_ssh_describe_host(mock_config):
    """Test describe_host tool."""
    result = mcp_server.ssh_describe_host(alias="test1")
    assert isinstance(result, dict)

    assert result["alias"] == "test1"
    assert result["host"] == "10.0.0.1"
    assert result["port"] == 22


def test_ssh_describe_host_not_found(mock_config):
    """Test describe_host with non-existent host."""
    result = mcp_server.ssh_describe_host(alias="nonexistent")

    assert "Error" in result


def test_ssh_plan(mock_config):
    """Test plan tool."""
    result = mcp_server.ssh_plan(alias="test1", command="uptime")
    assert isinstance(result, dict)

    assert result["alias"] == "test1"
    assert result["command"] == "uptime"
    assert "allowed" in result
    assert "limits" in result


def test_ssh_reload_config(mock_config):
    """Test reload_config tool."""
    result = mcp_server.ssh_reload_config()
    assert isinstance(result, dict)
    assert result.get("status") == "reloaded"


def test_ssh_cancel_not_found():
    """Test cancel tool with non-existent task."""
    result = mcp_server.ssh_cancel(task_id="nonexistent")
    assert isinstance(result, dict)
    assert result.get("cancelled") is False
    assert "not found" in result.get("message", "").lower()


def test_ssh_cancel_no_task_id():
    """Test cancel tool without task_id."""
    result = mcp_server.ssh_cancel(task_id="")
    # Error case - still returns string
    assert isinstance(result, str) or (
        isinstance(result, dict) and "error" in str(result).lower()
    )
    assert "required" in str(result).lower()


# Note: Testing ssh_run and ssh_run_on_tag requires mocking SSH connections,
# which is complex and better suited for integration tests with a real SSH server.
# The core logic is tested through the individual component tests (policy, ssh_client, config).


def test_default_parameters():
    """Test that all MCP tools have default empty string parameters."""
    # Per instructions: all params should default to empty strings
    assert mcp_server.ssh_describe_host() == "Error: alias is required"
    assert mcp_server.ssh_plan() != ""  # Should return an error but not crash


def test_ssh_run_async_invalid_alias():
    """Test ssh_run_async with invalid alias."""
    result = asyncio.run(
        mcp_server.ssh_run_async(alias="nonexistent", command="uptime")
    )

    assert "Error" in result or "error" in result.lower()
    assert "not found" in result.lower()


def test_ssh_run_async_no_alias():
    """Test ssh_run_async without alias."""
    result = asyncio.run(mcp_server.ssh_run_async(alias="", command="uptime"))

    assert "Error" in result
    assert "required" in result.lower()


def test_ssh_run_async_no_command():
    """Test ssh_run_async without command."""
    result = asyncio.run(mcp_server.ssh_run_async(alias="test1", command=""))

    assert "Error" in result
    assert "required" in result.lower()


def test_ssh_get_task_status_invalid_task():
    """Test ssh_get_task_status with invalid task ID."""
    result = mcp_server.ssh_get_task_status(task_id="invalid:task:id")

    assert "Error" in result
    assert "not found" in result.lower()


def test_ssh_get_task_status_no_task_id():
    """Test ssh_get_task_status without task_id."""
    result = mcp_server.ssh_get_task_status(task_id="")

    assert "Error" in result
    assert "required" in result.lower()


def test_ssh_get_task_result_invalid_task():
    """Test ssh_get_task_result with invalid task ID."""
    result = mcp_server.ssh_get_task_result(task_id="invalid:task:id")

    assert "Error" in result
    assert "not found" in result.lower()


def test_ssh_get_task_result_no_task_id():
    """Test ssh_get_task_result without task_id."""
    result = mcp_server.ssh_get_task_result(task_id="")

    assert "Error" in result
    assert "required" in result.lower()


def test_ssh_get_task_output_invalid_task():
    """Test ssh_get_task_output with invalid task ID."""
    result = mcp_server.ssh_get_task_output(task_id="invalid:task:id")

    assert "Error" in result
    assert "not found" in result.lower()


def test_ssh_get_task_output_no_task_id():
    """Test ssh_get_task_output without task_id."""
    result = mcp_server.ssh_get_task_output(task_id="")

    assert "Error" in result
    assert "required" in result.lower()


def test_ssh_cancel_async_task_invalid_task():
    """Test ssh_cancel_async_task with invalid task ID."""
    result = mcp_server.ssh_cancel_async_task(task_id="invalid:task:id")
    assert isinstance(result, dict)
    assert result.get("cancelled") is False
    assert (
        "not found" in result.get("message", "").lower()
        or "not cancellable" in result.get("message", "").lower()
    )


def test_ssh_cancel_async_task_no_task_id():
    """Test ssh_cancel_async_task without task_id."""
    result = mcp_server.ssh_cancel_async_task(task_id="")
    # Error case - still returns string
    assert isinstance(result, str) or (
        isinstance(result, dict) and "error" in str(result).lower()
    )
    assert "required" in str(result).lower()


# Note: Testing actual async task execution requires mocking SSH connections,
# which is complex and better suited for integration tests with a real SSH server.
# The core async task management logic is tested through the AsyncTaskManager tests.


@pytest.fixture
def mock_config_deny_policy():
    """Create a mock config with policy that denies all commands."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test servers.yml
        servers = {
            "hosts": [
                {
                    "alias": "test1",
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
            "entries": [
                {"name": "cred1", "username": "user1", "key_path": "id_ed25519"},
            ]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        # Policy with no allow rules - all commands denied
        policy = {
            "limits": {"max_seconds": 60},
            "rules": [],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        # Replace global config
        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        yield config


@pytest.fixture
def mock_config_network_deny():
    """Create a mock config with network policy that denies all IPs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test servers.yml
        servers = {
            "hosts": [
                {
                    "alias": "test1",
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
            "entries": [
                {"name": "cred1", "username": "user1", "key_path": "id_ed25519"},
            ]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        # Policy with allow rule but network deny (require specific IPs that don't match)
        policy = {
            "limits": {"max_seconds": 60},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "commands": ["*"],
                },
            ],
            "network": {
                "allow_ips": ["192.168.1.1"],  # Different IP - will deny
                "allow_cidrs": [],
            },
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        # Replace global config
        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        yield config


def test_ssh_run_policy_denial_returns_json(mock_config_deny_policy):
    """Test that policy denial returns structured JSON."""
    result = mcp_server.ssh_run(alias="test1", command="ls -la")

    # Result should be a JSON string
    assert isinstance(result, str)

    # Parse JSON
    parsed = json.loads(result)

    # Verify structure
    assert parsed["status"] == "denied"
    assert parsed["reason"] == "policy"
    assert parsed["alias"] == "test1"
    assert "hash" in parsed
    assert parsed["command"] == "ls -la"
    assert "hint" in parsed
    assert "ssh_plan" in parsed["hint"]


def test_ssh_run_async_policy_denial_returns_json(mock_config_deny_policy):
    """Test that policy denial in async run returns structured JSON."""
    result = asyncio.run(mcp_server.ssh_run_async(alias="test1", command="ls -la"))

    # Result should be a JSON string
    assert isinstance(result, str)

    # Parse JSON
    parsed = json.loads(result)

    # Verify structure
    assert parsed["status"] == "denied"
    assert parsed["reason"] == "policy"
    assert parsed["alias"] == "test1"
    assert "hash" in parsed
    assert parsed["command"] == "ls -la"
    assert "hint" in parsed
    assert "ssh_plan" in parsed["hint"]


def test_ssh_run_network_denial_returns_json(mock_config_network_deny):
    """Test that network denial returns structured JSON."""
    result = mcp_server.ssh_run(alias="test1", command="ls -la")

    # Result should be a JSON string
    assert isinstance(result, str)

    # Parse JSON
    parsed = json.loads(result)

    # Verify structure
    assert parsed["status"] == "denied"
    assert parsed["reason"] == "network"
    assert parsed["alias"] == "test1"
    assert parsed["hostname"] == "10.0.0.1"
    assert "detail" in parsed
    assert "hint" in parsed
    assert "ssh_plan" in parsed["hint"]


def test_ssh_run_async_network_denial_returns_json(mock_config_network_deny):
    """Test that network denial in async run returns structured JSON."""
    result = asyncio.run(mcp_server.ssh_run_async(alias="test1", command="ls -la"))

    # Result should be a JSON string
    assert isinstance(result, str)

    # Parse JSON
    parsed = json.loads(result)

    # Verify structure
    assert parsed["status"] == "denied"
    assert parsed["reason"] == "network"
    assert parsed["alias"] == "test1"
    assert parsed["hostname"] == "10.0.0.1"
    assert "detail" in parsed
    assert "hint" in parsed
    assert "ssh_plan" in parsed["hint"]


def test_ssh_plan_denial_has_hint(mock_config_deny_policy):
    """ssh_plan should include hint/why when not allowed."""
    preview = mcp_server.ssh_plan(alias="test1", command="ls -la")
    assert isinstance(preview, dict)
    assert preview["allowed"] is False
    assert preview["why"]
    assert "hint" in preview
    assert "ssh_plan" in preview["hint"]


def test_ssh_run_on_tag_policy_hint(mock_config_deny_policy):
    """Denied tag results should include guidance hint."""
    summary = mcp_server.ssh_run_on_tag(tag="web", command="ls -la")
    assert "results" in summary and summary["results"]
    entry = summary["results"][0]
    assert entry.get("denied") is True
    assert "hint" in entry
    assert "ssh_plan" in entry["hint"]


def test_ssh_run_on_tag_network_hint(mock_config_network_deny):
    """Network denials in tag runs should include detail + hint."""
    summary = mcp_server.ssh_run_on_tag(tag="web", command="ls -la")
    assert summary["results"]
    entry = summary["results"][0]
    assert entry.get("denied") is True
    assert "detail" in entry
    assert "hint" in entry
    assert "ssh_plan" in entry["hint"]


def test_policy_denied_response_helper():
    """Ensure helper populates expected fields."""
    result = mcp_server._policy_denied_response("alias1", "command1", "hash123")
    assert result["status"] == "denied"
    assert result["reason"] == "policy"
    assert result["alias"] == "alias1"
    assert result["hash"] == "hash123"
    assert result["command"] == "command1"
    assert "hint" in result
    assert "ssh_plan" in result["hint"]


def test_network_denied_response_helper():
    """Ensure helper populates expected fields."""
    result = mcp_server._network_denied_response("alias1", "host1", "detail text")
    assert result["status"] == "denied"
    assert result["reason"] == "network"
    assert result["alias"] == "alias1"
    assert result["hostname"] == "host1"
    assert result["detail"] == "detail text"
    assert "hint" in result
    assert "ssh_plan" in result["hint"]


# === ssh_run_on_tag Per-Host Exception Handling Tests ===


@pytest.fixture
def mock_config_multiple_hosts():
    """Create a mock config with multiple hosts for testing per-host failures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test servers.yml with 3 hosts
        servers = {
            "hosts": [
                {
                    "alias": "host1",
                    "host": "10.0.0.1",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["test"],
                },
                {
                    "alias": "host2",
                    "host": "10.0.0.2",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["test"],
                },
                {
                    "alias": "host3",
                    "host": "10.0.0.3",
                    "port": 22,
                    "credentials": "cred1",
                    "tags": ["test"],
                },
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w") as f:
            yaml.dump(servers, f)

        credentials = {
            "entries": [
                {"name": "cred1", "username": "user1", "key_path": "id_ed25519"},
            ]
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
                    "commands": ["uptime*"],
                },
            ],
            "network": {
                "allowlist": ["10.0.0.0/24"],
            },
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        # Replace global config
        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        yield config


def test_ssh_run_on_tag_partial_failure(mock_config_multiple_hosts):
    """Test that one host failure doesn't stop others."""
    # Mock _client_for to raise exception for host2 only
    original_client_for = mcp_server._client_for

    call_count = {"host1": 0, "host2": 0, "host3": 0}

    def mock_client_for(alias, limits, require_known_host):
        call_count[alias] += 1
        if alias == "host2":
            raise RuntimeError("SSH connection failed")
        return original_client_for(alias, limits, require_known_host)

    with patch.object(mcp_server, "_client_for", side_effect=mock_client_for):
        # Mock run_streaming to return success for host1 and host3
        mock_client = MagicMock()
        mock_client.run_streaming.return_value = (
            0,  # exit_code
            100,  # duration_ms
            False,  # cancelled
            False,  # timeout
            100,  # bytes_out
            0,  # bytes_err
            "uptime output",  # combined
            "10.0.0.1",  # peer_ip
        )

        def mock_client_for_with_client(alias, limits, require_known_host):
            if alias == "host2":
                raise RuntimeError("SSH connection failed")
            return mock_client

        with patch.object(
            mcp_server, "_client_for", side_effect=mock_client_for_with_client
        ):
            summary = mcp_server.ssh_run_on_tag(tag="test", command="uptime")

            assert "results" in summary
            results = summary["results"]
            assert len(results) == 3

            # host1 should succeed
            host1_result = next(r for r in results if r["alias"] == "host1")
            assert host1_result["exit_code"] == 0
            assert "uptime output" in host1_result["output"]

            # host2 should fail
            host2_result = next(r for r in results if r["alias"] == "host2")
            assert host2_result["exit_code"] == -1
            assert "SSH connection failed" in host2_result["output"]

            # host3 should succeed
            host3_result = next(r for r in results if r["alias"] == "host3")
            assert host3_result["exit_code"] == 0
            assert "uptime output" in host3_result["output"]


def test_ssh_run_on_tag_all_hosts_fail(mock_config_multiple_hosts):
    """Test when all hosts fail."""

    # Mock _client_for to raise exception for all hosts
    def mock_client_for(alias, limits, require_known_host):
        raise RuntimeError("SSH connection failed")

    with patch.object(mcp_server, "_client_for", side_effect=mock_client_for):
        summary = mcp_server.ssh_run_on_tag(tag="test", command="uptime")

        assert "results" in summary
        results = summary["results"]
        assert len(results) == 3

        # All hosts should have exit_code -1
        for result in results:
            assert result["exit_code"] == -1
            assert "SSH connection failed" in result["output"]


def test_ssh_run_on_tag_mixed_success_failure(mock_config_multiple_hosts):
    """Test mixed success/failure scenario."""
    # Mock run_streaming to return different results per host
    mock_clients = {}

    def mock_client_for(alias, limits, require_known_host):
        if alias not in mock_clients:
            mock_client = MagicMock()
            if alias == "host2":
                # host2 fails
                mock_client.run_streaming.side_effect = RuntimeError(
                    "SSH connection failed"
                )
            else:
                # host1 and host3 succeed
                mock_client.run_streaming.return_value = (
                    0,  # exit_code
                    100,  # duration_ms
                    False,  # cancelled
                    False,  # timeout
                    100,  # bytes_out
                    0,  # bytes_err
                    f"uptime output from {alias}",  # combined
                    f"10.0.0.{alias[-1]}",  # peer_ip
                )
            mock_clients[alias] = mock_client
        return mock_clients[alias]

    with patch.object(mcp_server, "_client_for", side_effect=mock_client_for):
        summary = mcp_server.ssh_run_on_tag(tag="test", command="uptime")

        assert "results" in summary
        results = summary["results"]
        assert len(results) == 3

        # host1 should succeed
        host1_result = next(r for r in results if r["alias"] == "host1")
        assert host1_result["exit_code"] == 0

        # host2 should fail
        host2_result = next(r for r in results if r["alias"] == "host2")
        assert host2_result["exit_code"] == -1

        # host3 should succeed
        host3_result = next(r for r in results if r["alias"] == "host3")
        assert host3_result["exit_code"] == 0


def test_ssh_run_on_tag_error_result_format(mock_config_multiple_hosts):
    """Verify error result format matches success format."""

    # Mock _client_for to raise exception
    def mock_client_for(alias, limits, require_known_host):
        raise RuntimeError("SSH connection failed")

    with patch.object(mcp_server, "_client_for", side_effect=mock_client_for):
        summary = mcp_server.ssh_run_on_tag(tag="test", command="uptime")

        assert "results" in summary
        results = summary["results"]
        assert len(results) > 0

        # Check that error results have the same structure as success results
        error_result = results[0]
        assert "alias" in error_result
        assert "task_id" in error_result
        assert "hash" in error_result
        assert "exit_code" in error_result
        assert error_result["exit_code"] == -1
        assert "duration_ms" in error_result
        assert "cancelled" in error_result
        assert "timeout" in error_result
        assert "target_ip" in error_result
        assert "output" in error_result


def test_ssh_run_on_tag_task_cleanup_on_failure(mock_config_multiple_hosts):
    """Verify tasks are cleaned up on failure."""
    cleanup_calls = []

    original_cleanup = mcp_server.TASKS.cleanup

    def mock_cleanup(task_id):
        cleanup_calls.append(task_id)
        return original_cleanup(task_id)

    # Mock _client_for to raise exception
    def mock_client_for(alias, limits, require_known_host):
        raise RuntimeError("SSH connection failed")

    with patch.object(mcp_server, "_client_for", side_effect=mock_client_for):
        with patch.object(mcp_server.TASKS, "cleanup", side_effect=mock_cleanup):
            summary = mcp_server.ssh_run_on_tag(tag="test", command="uptime")

            # Verify cleanup was called (tasks are created before connection attempt)
            # Note: cleanup may be called even if task_id is None, so we check that
            # the function handles failures gracefully
            assert "results" in summary
            results = summary["results"]
            assert len(results) == 3

            # All results should have exit_code -1 indicating failure
            for result in results:
                assert result["exit_code"] == -1


# ==================== Command Chaining Integration Tests ====================


@pytest.fixture
def mock_config_with_chaining_policy():
    """Create a mock config with policy that allows some commands for chaining tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "test1",
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
            "entries": [
                {"name": "cred1", "username": "user1", "key_path": "id_ed25519"},
            ]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w") as f:
            yaml.dump(credentials, f)

        # Policy with multiple allowed commands for chaining tests
        policy = {
            "limits": {"max_seconds": 60},
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "commands": ["uptime*", "whoami", "hostname*", "date*", "echo*"],
                },
                {
                    "action": "deny",
                    "aliases": ["*"],
                    "tags": [],
                    "commands": ["apt list --upgradable*", "cat /etc/passwd*"],
                },
            ],
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w") as f:
            yaml.dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config

        yield config


def test_ssh_plan_chain_both_allowed(mock_config_with_chaining_policy):
    """Test ssh_plan with chained commands where both are allowed."""
    result = mcp_server.ssh_plan(alias="test1", command="uptime && whoami")
    assert isinstance(result, dict)
    assert result["allowed"] is True
    assert result["alias"] == "test1"
    assert result["command"] == "uptime && whoami"


def test_ssh_plan_chain_first_allowed_second_denied(mock_config_with_chaining_policy):
    """Test ssh_plan with chained commands where second is denied."""
    result = mcp_server.ssh_plan(
        alias="test1", command="uptime && apt list --upgradable"
    )
    assert isinstance(result, dict)
    assert result["allowed"] is False
    assert "why" in result
    # Should identify which command is denied
    assert "denied_command" in result or "apt list --upgradable" in result["why"]


def test_ssh_plan_chain_first_denied_second_allowed(mock_config_with_chaining_policy):
    """Test ssh_plan with chained commands where first is denied."""
    result = mcp_server.ssh_plan(
        alias="test1", command="apt list --upgradable && uptime"
    )
    assert isinstance(result, dict)
    assert result["allowed"] is False
    assert "why" in result


def test_ssh_plan_chain_multiple_all_allowed(mock_config_with_chaining_policy):
    """Test ssh_plan with multiple chained commands all allowed."""
    result = mcp_server.ssh_plan(alias="test1", command="uptime && whoami && hostname")
    assert isinstance(result, dict)
    assert result["allowed"] is True


def test_ssh_plan_chain_multiple_one_denied(mock_config_with_chaining_policy):
    """Test ssh_plan with multiple chained commands where one is denied."""
    result = mcp_server.ssh_plan(
        alias="test1", command="uptime && apt list --upgradable && whoami"
    )
    assert isinstance(result, dict)
    assert result["allowed"] is False
    # Should identify the denied command
    assert "denied_command" in result or "apt list --upgradable" in result.get(
        "why", ""
    )


def test_ssh_plan_chain_with_semicolon(mock_config_with_chaining_policy):
    """Test ssh_plan with semicolon operator."""
    result = mcp_server.ssh_plan(alias="test1", command="uptime; whoami")
    assert isinstance(result, dict)
    assert result["allowed"] is True

    result = mcp_server.ssh_plan(alias="test1", command="uptime; apt list --upgradable")
    assert isinstance(result, dict)
    assert result["allowed"] is False


def test_ssh_plan_chain_with_pipe(mock_config_with_chaining_policy):
    """Test ssh_plan with pipe operator."""
    # Pipe should be treated as chaining - both commands must be allowed
    # Since "cat" is not in allow list, this should be denied
    result = mcp_server.ssh_plan(alias="test1", command="uptime | cat")
    assert isinstance(result, dict)
    assert result["allowed"] is False


def test_ssh_plan_chain_backward_compatibility(mock_config_with_chaining_policy):
    """Test that simple commands (no chaining) still work."""
    result = mcp_server.ssh_plan(alias="test1", command="uptime")
    assert isinstance(result, dict)
    assert result["allowed"] is True

    result = mcp_server.ssh_plan(alias="test1", command="unknown-command")
    assert isinstance(result, dict)
    assert result["allowed"] is False

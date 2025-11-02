"""Tests for MCP server tools."""

import json
import os
import tempfile

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
    assert result == "pong"


def test_ssh_list_hosts(mock_config):
    """Test list_hosts tool."""
    result = mcp_server.ssh_list_hosts()
    hosts = json.loads(result)

    assert isinstance(hosts, list)
    assert len(hosts) == 2
    assert "test1" in hosts
    assert "test2" in hosts


def test_ssh_describe_host(mock_config):
    """Test describe_host tool."""
    result = mcp_server.ssh_describe_host(alias="test1")
    host = json.loads(result)

    assert host["alias"] == "test1"
    assert host["host"] == "10.0.0.1"
    assert host["port"] == 22


def test_ssh_describe_host_not_found(mock_config):
    """Test describe_host with non-existent host."""
    result = mcp_server.ssh_describe_host(alias="nonexistent")

    assert "Error" in result


def test_ssh_plan(mock_config):
    """Test plan tool."""
    result = mcp_server.ssh_plan(alias="test1", command="uptime")
    plan = json.loads(result)

    assert plan["alias"] == "test1"
    assert plan["command"] == "uptime"
    assert "allowed" in plan
    assert "limits" in plan


def test_ssh_reload_config(mock_config):
    """Test reload_config tool."""
    result = mcp_server.ssh_reload_config()

    assert "reloaded" in result.lower()


def test_ssh_cancel_not_found():
    """Test cancel tool with non-existent task."""
    result = mcp_server.ssh_cancel(task_id="nonexistent")

    assert "not found" in result.lower()


def test_ssh_cancel_no_task_id():
    """Test cancel tool without task_id."""
    result = mcp_server.ssh_cancel(task_id="")

    assert "required" in result.lower()


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
    result = mcp_server.ssh_run_async(alias="nonexistent", command="uptime")

    assert "Error" in result or "error" in result.lower()
    assert "not found" in result.lower()


def test_ssh_run_async_no_alias():
    """Test ssh_run_async without alias."""
    result = mcp_server.ssh_run_async(alias="", command="uptime")

    assert "Error" in result
    assert "required" in result.lower()


def test_ssh_run_async_no_command():
    """Test ssh_run_async without command."""
    result = mcp_server.ssh_run_async(alias="test1", command="")

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

    assert "Error" in result or "not found" in result.lower()


def test_ssh_cancel_async_task_no_task_id():
    """Test ssh_cancel_async_task without task_id."""
    result = mcp_server.ssh_cancel_async_task(task_id="")

    assert "Error" in result
    assert "required" in result.lower()


# Note: Testing actual async task execution requires mocking SSH connections,
# which is complex and better suited for integration tests with a real SSH server.
# The core async task management logic is tested through the AsyncTaskManager tests.

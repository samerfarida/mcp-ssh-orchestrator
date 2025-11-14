"""Tests for MCP prompts functionality."""

from mcp_ssh import mcp_server


def test_prompt_ssh_orchestrator_usage():
    """Test that ssh_orchestrator_usage prompt returns non-empty string."""
    result = mcp_server.ssh_orchestrator_usage()
    assert isinstance(result, str)
    assert len(result) > 0
    assert "SSH Orchestrator" in result
    assert "ssh_plan" in result
    assert "ssh_run" in result


def test_prompt_ssh_policy_denied_guidance():
    """Test that ssh_policy_denied_guidance prompt returns non-empty string."""
    result = mcp_server.ssh_policy_denied_guidance()
    assert isinstance(result, str)
    assert len(result) > 0
    assert "policy" in result.lower()
    assert "denied" in result.lower()


def test_prompt_ssh_network_denied_guidance():
    """Test that ssh_network_denied_guidance prompt returns non-empty string."""
    result = mcp_server.ssh_network_denied_guidance()
    assert isinstance(result, str)
    assert len(result) > 0
    assert "network" in result.lower()
    assert "policy" in result.lower()


def test_prompt_ssh_missing_host_guidance():
    """Test that ssh_missing_host_guidance prompt returns non-empty string."""
    result = mcp_server.ssh_missing_host_guidance()
    assert isinstance(result, str)
    assert len(result) > 0
    assert "servers.yml" in result
    assert "host" in result.lower()


def test_prompt_ssh_missing_credentials_guidance():
    """Test that ssh_missing_credentials_guidance prompt returns non-empty string."""
    result = mcp_server.ssh_missing_credentials_guidance()
    assert isinstance(result, str)
    assert len(result) > 0
    assert "credentials.yml" in result
    assert "username" in result.lower()


def test_prompt_ssh_config_change_workflow():
    """Test that ssh_config_change_workflow prompt returns non-empty string."""
    result = mcp_server.ssh_config_change_workflow()
    assert isinstance(result, str)
    assert len(result) > 0
    assert "servers.yml" in result
    assert "credentials.yml" in result
    assert "policy.yml" in result


def test_all_prompts_registered():
    """Test that all prompts are callable and return strings."""
    prompts = [
        mcp_server.ssh_orchestrator_usage,
        mcp_server.ssh_policy_denied_guidance,
        mcp_server.ssh_network_denied_guidance,
        mcp_server.ssh_missing_host_guidance,
        mcp_server.ssh_missing_credentials_guidance,
        mcp_server.ssh_config_change_workflow,
    ]

    for prompt_func in prompts:
        result = prompt_func()
        assert isinstance(result, str)
        assert len(result) > 0
        assert "SSH" in result or "ssh" in result or "orchestrator" in result.lower()

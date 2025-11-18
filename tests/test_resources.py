"""Tests for newly added MCP resources."""

import os
import tempfile

import pytest
import yaml

from mcp_ssh import mcp_server
from mcp_ssh.config import Config


@pytest.fixture
def resource_config():
    """Provision temporary config data for resource tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        servers = {
            "hosts": [
                {
                    "alias": "docker-node",
                    "host": "10.10.0.10",
                    "port": 22,
                    "credentials": "docker-creds",
                    "tags": ["docker", "production"],
                    "description": "Docker-capable node",
                },
                {
                    "alias": "web-node",
                    "host": "10.10.0.11",
                    "port": 2222,
                    "credentials": "web-creds",
                    "tags": ["web"],
                },
            ]
        }
        with open(os.path.join(tmpdir, "servers.yml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(servers, f)

        credentials = {
            "entries": [
                {"name": "docker-creds", "username": "dock", "key_path": "id_docker"},
                {"name": "web-creds", "username": "web", "key_path": "id_web"},
            ]
        }
        with open(os.path.join(tmpdir, "credentials.yml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(credentials, f)

        policy = {
            "limits": {
                "max_seconds": 45,
                "deny_substrings": ["rm -rf /"],
            },
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["*"],
                    "tags": [],
                    "commands": ["uptime*", "df -h", "docker ps*"],
                }
            ],
            "network": {
                "allow_ips": [],
                "allow_cidrs": [],
                "block_ips": [],
                "block_cidrs": [],
            },
        }
        with open(os.path.join(tmpdir, "policy.yml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(policy, f)

        config = Config(config_dir=tmpdir)
        mcp_server.config = config
        yield config


def test_resource_hosts_returns_sanitized_inventory(resource_config):
    """ssh://hosts should return sanitized metadata for all hosts."""
    payload = mcp_server.resource_hosts()
    assert isinstance(payload, dict)
    assert payload["count"] == 2
    for host in payload["hosts"]:
        assert "alias" in host
        assert "host" in host
        assert "port" in host
        assert "credentials" not in host
        assert host.get("has_credentials_ref") in (True, False)


def test_resource_host_requires_valid_alias(resource_config):
    """ssh://host/{alias} should enforce alias validation."""
    result = mcp_server.resource_host(alias="")
    assert result["error"].startswith("alias")


def test_resource_host_returns_sanitized_record(resource_config):
    """ssh://host/{alias} returns sanitized host metadata."""
    result = mcp_server.resource_host(alias="docker-node")
    assert result["alias"] == "docker-node"
    assert result["host"] == "10.10.0.10"
    assert result["has_credentials_ref"] is True
    assert "credentials" not in result


def test_resource_host_tags_success(resource_config):
    """ssh://host/{alias}/tags returns configured tags."""
    result = mcp_server.resource_host_tags(alias="docker-node")
    assert result["alias"] == "docker-node"
    assert result["tags"] == ["docker", "production"]


def test_resource_host_tags_invalid_alias(resource_config):
    """ssh://host/{alias}/tags should return an error for invalid alias."""
    result = mcp_server.resource_host_tags(alias="invalid alias!")
    assert "error" in result


def test_resource_host_capabilities_summary(resource_config):
    """ssh://host/{alias}/capabilities provides limit summary and probes."""
    summary = mcp_server.resource_host_capabilities(alias="docker-node")
    limits = summary["limits"]
    assert limits["require_known_host"] is True
    assert limits["host_key_auto_add"] is False
    assert "deny_substrings" not in limits
    assert limits["deny_patterns_enabled"] is True
    probes = summary["policy_probes"]
    assert any(p["probe"] == "docker_status" for p in probes)
    assert summary["network"]["require_known_host"] is True
    assert summary["features"]["supports_async"] is True


def test_resource_host_capabilities_invalid_alias(resource_config):
    """ssh://host/{alias}/capabilities should validate alias."""
    result = mcp_server.resource_host_capabilities(alias="")
    assert "error" in result

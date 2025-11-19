# 13. Contributing

**Purpose:** Guide for contributing to MCP SSH Orchestrator development, including setup, coding standards, and submission process.

## Overview

We welcome contributions to MCP SSH Orchestrator! This guide covers how to set up a development environment, understand the codebase, and submit contributions.

## Development Setup

### Prerequisites

### Required Software

- Python 3.11+
- Docker and Docker Compose
- Git
- SSH client
- Code editor (VS Code recommended)

### Optional Tools

- Poetry (for dependency management)
- Pre-commit hooks
- Docker Desktop

### Local Development Environment

### 1. Clone the repository

git clone <https://github.com/samerfarida/mcp-ssh-orchestrator.git>
cd mcp-ssh-orchestrator

```python

### 2. Set up Python environment:

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
pip install -e ".[dev,test]"
```

### 3. Set up pre-commit hooks

pre-commit install

```bash

### 4. Configure development environment:

# Copy example configurations
cp examples/example-servers.yml config/servers.yml
cp examples/example-credentials.yml config/credentials.yml
cp examples/example-policy.yml config/policy.yml

# Generate SSH keys for testing
ssh-keygen -t ed25519 -f keys/test_key -N ""
chmod 0400 keys/test_key
```

### Docker Development

### Development with Docker Compose

# Build development image

docker-compose -f compose/docker-compose.dev.yml build

# Run development environment

docker-compose -f compose/docker-compose.dev.yml up

# Run tests

docker-compose -f compose/docker-compose.dev.yml run mcp-ssh pytest

```dockerfile

### Development Container:

# Run development container
docker run -it --rm \
  -v $(pwd):/app \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest \
  bash
```

## Codebase Structure

### Project Layout

```bash
src/mcp_ssh/
├── __init__.py          # Package initialization
├── config.py            # Configuration management
├── mcp_server.py        # MCP server implementation
├── policy.py            # Policy engine
├── ssh_client.py        # SSH client wrapper
└── tools/
    ├── __init__.py      # Tools package
    └── utilities.py     # Utility functions

tests/
├── test_config.py       # Configuration tests
├── test_policy.py       # Policy engine tests
├── test_ssh.py          # SSH client tests
└── test_server_tools.py # MCP server tests
```

### Key Components

### MCP Server (`mcp_server.py`)

- Implements MCP protocol
- Handles tool registration
- Manages client sessions
- Provides audit logging

### Policy Engine (`policy.py`)

- Evaluates command policies
- Manages security rules
- Handles network filtering
- Provides compliance reporting

### SSH Client (`ssh_client.py`)

- Wraps SSH connections
- Manages authentication
- Handles command execution
- Provides error handling

### Configuration (`config.py`)

- Loads YAML configurations
- Validates settings
- Manages secrets
- Provides defaults

## Coding Standards

### Python Style

### Code Formatting

- Use Black for code formatting
- Use isort for import sorting
- Follow PEP 8 guidelines
- Use type hints

### Example

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(**name**)

def evaluate_policy(
    alias: str,
    command: str,
    tags: List[str]
) -> Dict[str, bool]:
    """Evaluate policy for command execution.

    Args:
        alias: Host alias
        command: Command to execute
        tags: Host tags

    Returns:
        Policy evaluation result
    """
    # Implementation here
    pass

```bash

### Documentation

### Docstring Format:

def ssh_run(alias: str, command: str) -> Dict[str, Any]:
    """Execute SSH command on target host.

    Args:
        alias: Host alias from servers.yml
        command: Command to execute

    Returns:
        Command execution result with output and exit code

    Raises:
        PolicyViolationError: If command violates policy
        SSHConnectionError: If SSH connection fails
    """
    pass
```

### Inline Comments

# Policy evaluation: check if command is allowed

if not policy.evaluate(alias, command, tags):
    raise PolicyViolationError(f"Command '{command}' not allowed for '{alias}'")

# SSH connection: establish secure connection

with SSHClient(host_config) as client:
    result = client.execute(command)

```python

### Testing

### Test Structure:

import pytest
from unittest.mock import Mock, patch
from mcp_ssh.policy import Policy

class TestPolicy:
    """Test policy engine functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.policy = Policy("tests/fixtures/policy.yml")

    def test_allow_command(self):
        """Test command allowance."""
        result = self.policy.evaluate("web1", "uptime", ["production"])
        assert result["allowed"] is True

    def test_deny_command(self):
        """Test command denial."""
        result = self.policy.evaluate("web1", "rm -rf /", ["production"])
        assert result["allowed"] is False

    @patch('mcp_ssh.policy.logger')
    def test_policy_violation_logging(self, mock_logger):
        """Test policy violation logging."""
        self.policy.evaluate("web1", "rm -rf /", ["production"])
        mock_logger.warning.assert_called_once()
```

### Test Data

# tests/fixtures/policy.yml

known_hosts_path: "/app/keys/known_hosts"

limits:
  max_seconds: 30
  max_output_bytes: 131072

rules:

- action: "allow"
    aliases: ["web1"]
    tags: ["production"]
    commands:
  - "uptime*"
  - "df -h*"

- action: "deny"
    aliases: ["*"]
    tags: ["*"]
    commands:
  - "rm -rf *"
  - "shutdown*"

```

## Development Workflow

### Feature Development

### 1. Create feature branch:

git checkout -b feature/new-policy-rule
```

### 2. Implement feature

# Add new policy rule type

class PolicyRule:
    def **init**(self, action: str, conditions: Dict[str, Any]):
        self.action = action
        self.conditions = conditions

    def evaluate(self, alias: str, command: str, tags: List[str]) -> bool:
        # Implementation
        pass

```python

### 3. Add tests:

def test_new_policy_rule():
    """Test new policy rule functionality."""
    rule = PolicyRule("allow", {"aliases": ["web1"]})
    result = rule.evaluate("web1", "uptime", ["production"])
    assert result is True
```

### 4. Update documentation

# Update wiki documentation

# Add examples to usage cookbook

# Update API reference

```bash

### Bug Fixes

### 1. Create bug fix branch:

git checkout -b bugfix/ssh-connection-timeout
```

### 2. Reproduce issue

# Create test that reproduces the bug

def test_ssh_connection_timeout():
    """Test SSH connection timeout handling."""
    with pytest.raises(SSHTimeoutError):
        ssh_client.connect("slow-host", timeout=1)

```python

### 3. Fix the issue:

# Implement fix
def connect(self, host: str, timeout: int = 30):
    """Connect to SSH host with timeout."""
    try:
        self.client.connect(host, timeout=timeout)
    except socket.timeout:
        raise SSHTimeoutError(f"Connection to {host} timed out")
```

### 4. Verify fix

# Test that fix works

def test_ssh_connection_timeout_fixed():
    """Test SSH connection timeout fix."""
    with patch('socket.socket') as mock_socket:
        mock_socket.return_value.connect.side_effect = socket.timeout()
        with pytest.raises(SSHTimeoutError):
            ssh_client.connect("slow-host", timeout=1)

```bash

### Code Review Process

### 1. Submit pull request:

git push origin feature/new-policy-rule
# Create PR on GitHub
```

### 2. Address feedback

# Make requested changes

git add .
git commit -m "Address review feedback"
git push origin feature/new-policy-rule

```bash

### 3. Merge after approval:

# Squash commits if needed
git rebase -i main
git push origin feature/new-policy-rule --force-with-lease
```

## Testing Guidelines

### Unit Tests

### Test Coverage

- Aim for 90%+ code coverage
- Test all public methods
- Test error conditions
- Test edge cases

### Test Examples

def test_config_validation():
    """Test configuration validation."""
    config = Config("tests/fixtures/config.yml")
    assert config.validate() is True

    # Test invalid config
    with pytest.raises(ConfigError):
        Config("tests/fixtures/invalid-config.yml")

def test_policy_evaluation():
    """Test policy evaluation logic."""
    policy = Policy("tests/fixtures/policy.yml")

    # Test allow case
    result = policy.evaluate("web1", "uptime", ["production"])
    assert result["allowed"] is True

    # Test deny case
    result = policy.evaluate("web1", "rm -rf /", ["production"])
    assert result["allowed"] is False

```bash

### Integration Tests

### End-to-end testing:

def test_ssh_command_execution():
    """Test complete SSH command execution flow."""
    # Set up test environment
    with DockerCompose("tests/docker-compose.yml") as compose:
        # Wait for services
        compose.wait_for_service("test-host", 22)

        # Execute command
        result = ssh_run("test-host", "uptime")

        # Verify result
        assert result["exit_code"] == 0
        assert "load average" in result["output"]
```

### MCP Inspector Testing

### Interactive Testing with MCP Inspector

The [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) provides a web-based interface for testing MCP servers. It's essential for verifying structured output, schema generation, and tool behavior.

### Setup

# Test with local Python server

cd /path/to/mcp-ssh-orchestrator
export MCP_SSH_CONFIG_DIR=$(pwd)/config
source venv/bin/activate
npx -y @modelcontextprotocol/inspector python -m mcp_ssh.mcp_server

# Or test with Docker-based server

npx -y @modelcontextprotocol/inspector docker compose -f compose/docker-compose.dev.yml run --rm -T mcp-ssh python -m mcp_ssh.mcp_server

```bash

### What to Verify:

1. **Schema Generation**: All tools should show generated JSON schemas
2. **Structured Output**: Tools return structured dicts (verify "Valid according to output schema")
3. **Error Handling**: Error cases return appropriate responses
4. **Tool Execution**: All tools execute correctly with various inputs

### Best Practices:

- Use MCP Inspector during development to verify tool changes
- Test all tools after major refactoring
- Verify schema generation for new tools
- Test edge cases and error conditions

### Performance Tests

### Load testing:

def test_concurrent_ssh_connections():
    """Test concurrent SSH connections."""
    import concurrent.futures

    def execute_command(host):
        return ssh_run(host, "uptime")

    hosts = ["web1", "web2", "web3"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(execute_command, host) for host in hosts]
        results = [future.result() for future in futures]

    # Verify all commands succeeded
    assert all(result["exit_code"] == 0 for result in results)
```

## Documentation Contributions

### Wiki Updates

### Documentation Standards

- Use clear, concise language
- Include code examples
- Provide practical use cases
- Update related sections

### Example Update

# Add new section to Usage Cookbook

## Advanced Policy Rules

**Purpose:** Demonstrate advanced policy rule configurations for complex scenarios.

### Time-based Rules

```yaml
rules:
  - action: "allow"
    aliases: ["*"]
    tags: ["production"]
    commands: ["uptime*"]
    time_restrictions:
      start_time: "09:00"
      end_time: "17:00"
      timezone: "UTC"
```

### Resource-based Rules

```yaml
rules:
  - action: "allow"
    aliases: ["*"]
    tags: ["production"]
    commands: ["df -h*"]
    resource_limits:
      max_memory: "1GB"
      max_cpu: "50%"
```

### API Documentation

### Function documentation

def ssh_run(alias: str, command: str) -> Dict[str, Any]:
    """Execute SSH command on target host.

    This function provides secure SSH command execution with policy enforcement,
    audit logging, and error handling.

    Args:
        alias: Host alias from servers.yml configuration
        command: Command to execute on the target host

    Returns:
        Dictionary containing:
            - output: Command output (str)
            - error: Error output (str)
            - exit_code: Command exit code (int)
            - execution_time: Execution duration in seconds (float)

    Raises:
        PolicyViolationError: If command violates policy rules
        SSHConnectionError: If SSH connection fails
        SSHTimeoutError: If command execution times out

    Example:
        >>> result = ssh_run("web1", "uptime")
        >>> print(result["output"])
        10:30:45 up 5 days, 2:15, 1 user, load average: 0.00, 0.01, 0.05
    """
    pass

```

## Release Process

### Version Management

### Semantic Versioning

- MAJOR: Breaking changes
- MINOR: New features
- PATCH: Bug fixes

### Version Bump

# Update version in pyproject.toml

version = "0.2.0"

# Update CHANGELOG.md

## [0.2.0] - 2024-01-15

### Added

- New policy rule types
- Enhanced audit logging
- Performance improvements

### Changed

- Updated MCP protocol version
- Improved error handling

### Fixed

- SSH connection timeout issues
- Policy evaluation bugs

```text

### Release Checklist

### Pre-release

- [ ] All tests passing
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped
- [ ] Security review completed

### Release

- [ ] Create release tag
- [ ] Build Docker image
- [ ] Push to registry
- [ ] Update GitHub release
- [ ] Announce release

## Community Guidelines

### Code of Conduct

### Our Pledge

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Respect different viewpoints

### Reporting Issues

- Use GitHub issues for bugs
- Use discussions for questions
- Be specific and provide context
- Include reproduction steps

### Getting Help

### Resources

- GitHub Discussions for questions
- GitHub Issues for bugs
- Wiki documentation
- Code examples

### Contributing

- Start with small fixes
- Ask questions early
- Follow coding standards
- Test your changes

## Next Steps

- **[FAQ](14-FAQ)** - Common development questions
- **[CHANGELOG](../CHANGELOG.md)** - Version history and releases
- **[Security Model](05-Security-Model)** - Security considerations for contributors
- **[Troubleshooting](12-Troubleshooting)** - Development environment issues

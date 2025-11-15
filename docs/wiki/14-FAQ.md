# 15. FAQ

**Purpose:** Answer common questions about MCP SSH Orchestrator, its usage, configuration, and troubleshooting.

## Overview

This FAQ addresses the most frequently asked questions about MCP SSH Orchestrator, covering installation, configuration, security, and troubleshooting.

## General Questions

### What is MCP SSH Orchestrator?

MCP SSH Orchestrator is a secure SSH fleet orchestrator built as a Model Context Protocol (MCP) server. It enables AI agents and other MCP clients to execute commands across a fleet of SSH targets with robust policy-based access control, network filtering, and comprehensive audit logging.

### Why do I need MCP SSH Orchestrator?

AI agents interacting with external systems introduce significant security risks, including prompt injection, data exfiltration, and privilege escalation. mcp-ssh-orchestrator acts as a secure gateway, mediating all agent-to-SSH interactions through a hardened policy engine, ensuring only authorized and safe commands are executed.

### How does it differ from direct SSH access?

**Direct SSH Access:**

- No policy enforcement
- No audit logging
- No network filtering
- No rate limiting
- No compliance reporting

**mcp-ssh-orchestrator:**

- Policy-based access control
- Comprehensive audit logging
- Network security filtering
- Rate limiting and timeouts
- Compliance reporting
- MCP protocol integration

### What MCP clients are supported?

- **Claude Desktop**: Primary integration target
- **OpenAI Codex**: Via Docker MCP Toolkit
- **Custom Applications**: Using MCP SDKs
- **Development Tools**: IDEs and editors with MCP support

## Installation & Setup

### How do I install mcp-ssh-orchestrator?

**Docker (Recommended):**

```bash
# Pull the image
docker pull ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

# Run with configuration
docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

**From Source:**

```bash
git clone https://github.com/samerfarida/mcp-ssh-orchestrator.git
cd mcp-ssh-orchestrator
pip install -e .
```

### What are the system requirements?

**Minimum Requirements:**

- Docker 20.10+ or Python 3.11+
- 512MB RAM
- 1GB disk space
- SSH client

**Recommended Requirements:**

- Docker 24.0+
- 2GB RAM
- 10GB disk space
- Modern CPU with 2+ cores

### How do I configure Claude Desktop?

**macOS Configuration** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ssh-orchestrator": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/config:/app/config:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/keys:/app/keys:ro",
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:latest"
      ]
    }
  }
}
```

**Windows Configuration** (`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ssh-orchestrator": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "C:\\Users\\YOUR_USERNAME\\mcp-ssh\\config:/app/config:ro",
        "-v", "C:\\Users\\YOUR_USERNAME\\mcp-ssh\\keys:/app/keys:ro",
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:latest"
      ]
    }
  }
}
```

## Configuration

### How do I configure SSH keys?

**1. Generate SSH key pair:**

```bash
ssh-keygen -t ed25519 -f ~/mcp-ssh/keys/id_ed25519 -C "mcp-ssh-orchestrator"
```

**2. Set permissions:**

```bash
chmod 0400 ~/mcp-ssh/keys/id_ed25519
chmod 0444 ~/mcp-ssh/keys/id_ed25519.pub
```

**3. Deploy public key:**

```bash
ssh-copy-id -i ~/mcp-ssh/keys/id_ed25519.pub ubuntu@10.0.0.11
```

**4. Update credentials.yml:**

```yaml
entries:
  - name: "admin"
    username: "ubuntu"
    key_path: "id_ed25519"
    key_passphrase_secret: ""
    password_secret: ""
```

### How do I configure policy rules?

**Basic Policy Configuration:**

```yaml
# policy.yml
known_hosts_path: "/app/keys/known_hosts"

limits:
  max_seconds: 30
  max_output_bytes: 131072
  host_key_auto_add: false
  require_known_host: true

rules:
  - action: "allow"
    aliases: ["web1", "web2"]
    tags: ["production"]
    commands:
      - "uptime*"
      - "df -h*"
      - "systemctl status *"

  - action: "deny"
    aliases: ["*"]
    tags: ["*"]
    commands:
      - "rm -rf *"
      - "shutdown*"
      - "reboot*"
```

### How do I add new hosts?

**1. Update servers.yml:**

```yaml
entries:
  - alias: "web1"
    hostname: "10.0.0.11"
    port: 22
    tags: ["production", "web"]

  - alias: "web2"
    hostname: "10.0.0.12"
    port: 22
    tags: ["production", "web"]
```

**2. Add host keys:**

```bash
ssh-keyscan 10.0.0.11 >> ~/mcp-ssh/keys/known_hosts
ssh-keyscan 10.0.0.12 >> ~/mcp-ssh/keys/known_hosts
```

**3. Test connectivity:**

```bash
ssh -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11
```

## Security

### Is mcp-ssh-orchestrator secure?

Yes, mcp-ssh-orchestrator implements multiple security layers:

**Policy Enforcement:**

- Command allow/deny rules
- Network filtering (CIDR allowlists/blocklists)
- Rate limiting and timeouts
- Host key verification

**Audit & Compliance:**

- Comprehensive audit logging
- Policy violation tracking
- Security event monitoring
- Compliance reporting

**Container Security:**

- Non-root execution
- Read-only filesystem
- Resource limits
- Network isolation

### How do I handle secrets?

**Docker Secrets (Recommended):**

```bash
# Create secrets
echo "your-passphrase" | docker secret create mcp_key_passphrase -
echo "your-password" | docker secret create mcp_password -

# Use in Docker Compose
services:
  mcp-ssh:
    image: ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
    secrets:
      - mcp_key_passphrase
      - mcp_password
```

**Environment Variables:**

```bash
# Set environment variables
export MCP_SSH_SECRET_KEY_PASSPHRASE="your-passphrase"
export MCP_SSH_SECRET_PASSWORD="your-password"

# Use in Docker run
docker run -i --rm \
  -e MCP_SSH_SECRET_KEY_PASSPHRASE \
  -e MCP_SSH_SECRET_PASSWORD \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

### How do I enable host key verification?

**1. Collect host keys:**

```bash
ssh-keyscan 10.0.0.11 >> ~/mcp-ssh/keys/known_hosts
ssh-keyscan 10.0.0.12 >> ~/mcp-ssh/keys/known_hosts
```

**2. Update policy:**

```yaml
# policy.yml
known_hosts_path: "/app/keys/known_hosts"
require_known_host: true
host_key_auto_add: false
```

**3. Test verification:**

```bash
ssh -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11
```

## Usage

### How do I execute commands?

**Via Claude Desktop:**

```text
Execute the command "uptime" on the production web server
```

**Via MCP Client:**

```python
result = await session.call_tool(
    "ssh_run",
    {"alias": "web1", "command": "uptime"}
)
```

**Via Docker:**

```bash
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_run","arguments":{"alias":"web1","command":"uptime"}},"id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

### How do I list available hosts?

**Via Claude Desktop:**

```text
List all available SSH hosts
```

**Via MCP Client:**

```python
result = await session.call_tool("ssh_list_hosts", {})
```

**Via Docker:**

```bash
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_list_hosts","arguments":{}},"id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

### How do I test policy rules?

**Dry Run:**

```bash
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_plan","arguments":{"alias":"web1","command":"uptime"}},"id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

**Policy Validation:**

```bash
docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest \
  python -c "
from mcp_ssh.policy import Policy
policy = Policy('/app/config/policy.yml')
print('Policy valid:', policy.validate())
"
```

## Troubleshooting

### Why is my command being denied?

**Common Causes:**

- Command not in allow list
- Host not in allow list
- Policy rule violation
- Network filtering

**Debug Steps:**

```bash
# Check policy evaluation
docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest \
  python -c "
from mcp_ssh.policy import Policy
policy = Policy('/app/config/policy.yml')
result = policy.evaluate('web1', 'uptime', ['production'])
print('Policy result:', result)
"

# Test with dry run
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_plan","arguments":{"alias":"web1","command":"uptime"}},"id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

### Why is SSH connection failing?

**Common Causes:**

- Wrong SSH key
- Host not reachable
- SSH service not running
- Host key verification failed

**Debug Steps:**

```bash
# Test SSH connectivity
ssh -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11

# Check host key
ssh-keyscan 10.0.0.11

# Test network connectivity
ping 10.0.0.11
telnet 10.0.0.11 22
```

### Why is the container not starting?

**Common Causes:**

- Configuration errors
- Permission issues
- Resource limits
- Missing dependencies

**Debug Steps:**

```bash
# Check container logs
docker logs $(docker ps -q --filter "ancestor=ghcr.io/samerfarida/mcp-ssh-orchestrator:latest")

# Test container health
docker run --rm ghcr.io/samerfarida/mcp-ssh-orchestrator:latest python -c "import mcp_ssh; print('OK')"

# Validate configuration
docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest \
  python -c "
from mcp_ssh.config import Config
config = Config('/app/config')
print('Config valid:', config.validate())
"
```

## Performance

### How many concurrent connections are supported?

**Current Limits:**

- 100 concurrent SSH connections
- 1000 commands per minute
- 1MB output per command
- 30-second timeout per command

**Resource Optimization:**

- Container resource limits (memory, CPU)
- Connection timeout configuration
- Output size limits
- Performance monitoring via audit logs

### How do I optimize performance?

**Configuration Optimization:**

```yaml
# policy.yml
limits:
  max_seconds: 15           # Shorter timeout for sensitive hosts
  max_output_bytes: 65536   # Tighter output cap
  task_result_ttl: 120      # Reduce async retention window
```

**Docker Optimization:**

```bash
# Increase container resources
docker run -i --rm \
  --memory=1g \
  --cpus=2 \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  -v ~/mcp-ssh/secrets:/app/secrets:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

**Network Optimization:**

```yaml
# servers.yml
hosts:
  - alias: "web1"
    host: "10.0.0.11"
    port: 22
    credentials: "prod-admin"
    tags: ["production", "web"]
```

## Support

### Where can I get help?

**Documentation:**

- This wiki for comprehensive guides
- GitHub README for quick start
- `examples/` directory for ready-to-edit YAML

**Community:**

- GitHub Discussions for questions
- GitHub Issues for bugs or feature requests

**Professional Support:**

- Not offered. This is a community-supported Apache-2.0 project.

### How do I report bugs?

**Bug Report Template:**

```markdown
## Bug Description
Brief description of the bug

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: macOS/Windows/Linux
- Docker version: 24.0+
- mcp-ssh-orchestrator version: 1.0.0

## Additional Context
Any other relevant information
```

**Security Issues:**

- Report security issues privately
- Use GitHub security advisories
- Follow responsible disclosure
- Include detailed reproduction steps

## Next Steps

- **[Troubleshooting](12-Troubleshooting)** - Comprehensive troubleshooting guide
- **[Contributing](13-Contributing)** - How to contribute to the project
- **[CHANGELOG](../CHANGELOG.md)** - Version history and releases
- **[Security Model](05-Security-Model)** - Security architecture details

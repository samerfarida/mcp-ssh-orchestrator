# 12. Troubleshooting

**Purpose:** Comprehensive troubleshooting guide for common issues with MCP SSH Orchestrator deployment, configuration, and operations.

## Overview

This section covers common issues, their symptoms, root causes, and solutions for MCP SSH Orchestrator deployments.

## Common Issues

### Configuration Issues

#### Invalid Configuration Files

**Symptoms:**

- Container fails to start
- Error: "Configuration validation failed"
- MCP server not responding

**Root Causes:**

- Malformed YAML syntax
- Missing required fields
- Invalid field values
- File permissions issues

**Solutions:**
```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config/servers.yml'))"

# Check file permissions
ls -la config/
# Should show: -rw-r--r-- 1 user user

# Validate configuration
docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0 \
  python -c "
from mcp_ssh.config import Config
config = Config('/app/config')
print('Config valid:', config.validate())
"
```

#### Missing SSH Keys

**Symptoms:**

- SSH connection failures
- Error: "No such file or directory: '/app/keys/id_ed25519'"
- Authentication failures

**Root Causes:**

- SSH keys not mounted
- Incorrect key paths
- Wrong file permissions

**Solutions:**
```bash
# Check key files exist
ls -la ~/mcp-ssh/keys/

# Set correct permissions
chmod 0400 ~/mcp-ssh/keys/id_ed25519
chmod 0444 ~/mcp-ssh/keys/id_ed25519.pub

# Verify key format
ssh-keygen -l -f ~/mcp-ssh/keys/id_ed25519

# Test SSH connectivity
ssh -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11
```

#### Policy Configuration Errors

**Symptoms:**

- All commands denied
- Error: "Policy evaluation failed"
- Unexpected command blocking

**Root Causes:**

- Invalid policy syntax
- Conflicting rules
- Missing policy sections

**Solutions:**
```bash
# Validate policy syntax
python -c "
import yaml
with open('config/policy.yml') as f:
    policy = yaml.safe_load(f)
print('Policy valid:', 'rules' in policy)
"

# Test policy rules
docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0 \
  python -c "
from mcp_ssh.policy import Policy
policy = Policy('/app/config/policy.yml')
result = policy.evaluate('web1', 'uptime', ['production'])
print('Policy result:', result)
"
```

### Network Issues

#### SSH Connection Failures

**Symptoms:**

- "Connection refused" errors
- "Host key verification failed"
- Timeout errors

**Root Causes:**

- Network connectivity issues
- SSH service not running
- Host key verification failures
- Firewall blocking connections

**Solutions:**
```bash
# Test network connectivity
ping 10.0.0.11

# Test SSH port
telnet 10.0.0.11 22

# Check SSH service
ssh -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11 "systemctl status ssh"

# Verify host key
ssh-keyscan 10.0.0.11 >> ~/mcp-ssh/keys/known_hosts

# Test SSH connection
ssh -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11 "uptime"
```

#### Host Key Verification Issues

**Symptoms:**

- "Host key verification failed"
- "Unknown host" errors
- Policy violations for host key checks

**Root Causes:**

- Missing host keys in known_hosts
- Changed host keys
- Host key verification disabled

**Solutions:**
```bash
# Add host key to known_hosts
ssh-keyscan 10.0.0.11 >> ~/mcp-ssh/keys/known_hosts

# Verify host key
ssh-keygen -l -f ~/mcp-ssh/keys/known_hosts

# Security: Host key verification is always enforced (CWE-295)
# Populate known_hosts file instead:
# In policy.yml:
require_known_host: true  # Always enforced for security (CWE-295)

# Populate known_hosts:
ssh-keyscan -H <hostname> >> /app/keys/known_hosts
```

### Container Issues

#### Container Won't Start

**Symptoms:**

- Container exits immediately
- "Permission denied" errors
- Resource limit exceeded

**Root Causes:**

- Insufficient resources
- Permission issues
- Configuration errors
- Missing dependencies

**Solutions:**
```bash
# Check container logs
docker logs $(docker ps -q --filter "ancestor=ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0")

# Test container health
docker run --rm ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0 python -c "import mcp_ssh; print('OK')"

# Check resource usage
docker stats

# Increase resource limits
docker run -i --rm \
  --memory=1g \
  --cpus=2 \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0
```

#### Permission Issues

**Symptoms:**

- "Permission denied" errors
- "Read-only file system" errors
- Container runs as root

**Root Causes:**

- Incorrect file permissions
- Container running as root
- Read-only filesystem issues

**Solutions:**
```bash
# Fix file permissions
chmod 0400 ~/mcp-ssh/keys/*
chmod 0444 ~/mcp-ssh/config/*

# Run container as non-root user
docker run -i --rm \
  --user=10001:10001 \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0

# Check container user
docker run --rm ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0 whoami
```

### MCP Client Issues

#### Claude Desktop Integration Problems

**Symptoms:**

- MCP server not appearing in Claude Desktop
- "Connection failed" errors
- Tools not available

**Root Causes:**

- Incorrect configuration
- Container not running
- Network issues
- Version incompatibility

**Solutions:**
```bash
# Test MCP server directly
echo '{"jsonrpc":"2.0","method":"ping","id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0

# Check Claude Desktop configuration
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Restart Claude Desktop
killall "Claude Desktop"
open -a "Claude Desktop"
```

#### Tool Execution Failures

**Symptoms:**

- Tools not responding
- "Tool not found" errors
- Command execution failures

**Root Causes:**

- Tool registration issues
- Policy blocking commands
- SSH connection problems
- Resource limits exceeded

**Solutions:**
```bash
# List available tools
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0

# Test tool execution
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_ping","arguments":{}},"id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0
```

## Debugging Techniques

### Enable Debug Logging

**Development Mode:**
```bash
# Enable debug logging
docker run -i --rm \
  -e MCP_SSH_DEBUG=1 \
  -e LOG_LEVEL=DEBUG \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0
```

**Production Debugging:**
```bash
# Enable verbose logging
docker run -i --rm \
  -e LOG_LEVEL=INFO \
  -e LOG_FORMAT=json \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0
```

### Network Debugging

**SSH Debug Mode:**
```bash
# Enable SSH debug logging
ssh -vvv -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11

# Test SSH connection with debug
docker run -i --rm \
  -e SSH_DEBUG=1 \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0
```

**Network Connectivity Tests:**
```bash
# Test network connectivity
docker run --rm --network=host \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0 \
  python -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = s.connect_ex(('10.0.0.11', 22))
print('SSH port accessible:', result == 0)
s.close()
"
```

### Policy Debugging

**Policy Rule Testing:**
```bash
# Test specific policy rules
docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0 \
  python -c "
from mcp_ssh.policy import Policy
policy = Policy('/app/config/policy.yml')

# Test allow rule
result = policy.evaluate('web1', 'uptime', ['production'])
print('Allow rule result:', result)

# Test deny rule
result = policy.evaluate('web1', 'rm -rf /', ['production'])
print('Deny rule result:', result)
"
```

**Policy Validation:**
```bash
# Validate policy configuration
docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0 \
  python -c "
from mcp_ssh.policy import Policy
policy = Policy('/app/config/policy.yml')
print('Policy valid:', policy.validate())
print('Rules count:', len(policy.rules))
print('Limits:', policy.limits)
"
```

## Performance Issues

### Slow Command Execution

**Symptoms:**

- Commands taking >30 seconds
- Timeout errors
- High resource usage

**Root Causes:**

- Network latency
- Target system performance
- Resource limits
- Policy complexity

**Solutions:**
```bash
# Check command execution time
time ssh -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11 "uptime"

# Monitor resource usage
docker stats

# Increase timeout limits
# In policy.yml:
limits:
  max_seconds: 60
  max_output_bytes: 262144
```

### High Memory Usage

**Symptoms:**

- Container memory limit exceeded
- OOMKilled errors
- Slow performance

**Root Causes:**

- Large command outputs
- Memory leaks
- Insufficient limits
- Multiple concurrent sessions

**Solutions:**
```bash
# Monitor memory usage
docker stats

# Increase memory limits
docker run -i --rm \
  --memory=1g \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0

# Limit output size
# In policy.yml:
limits:
  max_output_bytes: 65536
```

## Security Issues

### Authentication Failures

**Symptoms:**

- "Permission denied" errors
- "Authentication failed" errors
- Policy violations

**Root Causes:**

- Wrong SSH keys
- Incorrect credentials
- Key passphrase issues
- Target system changes

**Solutions:**
```bash
# Verify SSH key
ssh-keygen -l -f ~/mcp-ssh/keys/id_ed25519

# Test SSH connection
ssh -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11

# Check key permissions
ls -la ~/mcp-ssh/keys/

# Verify target system access
ssh -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11 "whoami"
```

### Policy Violations

**Symptoms:**

- Commands denied unexpectedly
- "Policy violation" errors
- Security alerts

**Root Causes:**

- Incorrect policy rules
- Missing permissions
- Tag mismatches
- Command pattern issues

**Solutions:**
```bash
# Check policy rules
cat ~/mcp-ssh/config/policy.yml

# Test policy evaluation
docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0 \
  python -c "
from mcp_ssh.policy import Policy
policy = Policy('/app/config/policy.yml')
result = policy.evaluate('web1', 'uptime', ['production'])
print('Policy result:', result)
"
```

## Recovery Procedures

### Configuration Recovery

**Backup and Restore:**
```bash
# Backup configuration
tar -czf mcp-ssh-config-backup.tar.gz ~/mcp-ssh/config/

# Restore configuration
tar -xzf mcp-ssh-config-backup.tar.gz -C ~/

# Verify restoration
ls -la ~/mcp-ssh/config/
```

### Container Recovery

**Container Restart:**
```bash
# Stop all containers
docker stop $(docker ps -q --filter "ancestor=ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0")

# Remove containers
docker rm $(docker ps -aq --filter "ancestor=ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0")

# Start fresh
docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0
```

### Service Recovery

**Service Restart:**
```bash
# Restart Docker service
sudo systemctl restart docker

# Restart MCP orchestrator
docker-compose down
docker-compose up -d

# Check service status
docker-compose ps
```

## Getting Help

### Log Collection

**Collect Debug Information:**
```bash
#!/bin/bash
# collect-debug-info.sh

DEBUG_DIR="mcp-ssh-debug-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$DEBUG_DIR"

# System information
uname -a > "$DEBUG_DIR/system-info.txt"
docker version >> "$DEBUG_DIR/system-info.txt"

# Configuration files
cp -r ~/mcp-ssh/config "$DEBUG_DIR/"
cp -r ~/mcp-ssh/keys "$DEBUG_DIR/"

# Container logs
docker logs $(docker ps -q --filter "ancestor=ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0") > "$DEBUG_DIR/container-logs.txt"

# Network information
netstat -an > "$DEBUG_DIR/network-info.txt"

# Create debug package
tar -czf "$DEBUG_DIR.tar.gz" "$DEBUG_DIR"
echo "Debug package created: $DEBUG_DIR.tar.gz"
```

### Community Support

**GitHub Issues:**

- Create detailed issue reports
- Include debug information
- Provide reproduction steps
- Attach relevant logs

**Documentation:**

- Check this wiki for solutions
- Review configuration examples
- Consult security best practices

## Next Steps

- **[Observability & Audit](11-Observability-Audit)** - Monitoring and logging setup
- **[Security Model](05-Security-Model)** - Security architecture details
- **[FAQ](14-FAQ)** - Common troubleshooting questions
- **[Contributing](13-Contributing)** - How to contribute fixes and improvements

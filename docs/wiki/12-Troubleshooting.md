# 12. Troubleshooting

**Purpose:** Comprehensive troubleshooting guide for common issues with MCP SSH Orchestrator deployment, configuration, and operations.

## Overview

This section covers common issues, their symptoms, root causes, and solutions for MCP SSH Orchestrator deployments.

## Common Issues

### Configuration Issues

#### Invalid Configuration Files

### Symptoms

- Container fails to start
- Error: "Configuration validation failed"
- MCP server not responding

### Root Causes

- Malformed YAML syntax
- Missing required fields
- Invalid field values
- File permissions issues

### Solutions

# Validate YAML syntax

python -c "import yaml; yaml.safe_load(open('config/servers.yml'))"

# Check file permissions

ls -la config/

# Should show: -rw-r--r-- 1 user user

# Validate configuration

docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest \
  python -c "
from mcp_ssh.config import Config
config = Config('/app/config')
print('Config valid:', config.validate())
"

```bash

#### Missing SSH Keys

### Symptoms:

- SSH connection failures
- Error: "No such file or directory: '/app/keys/id_ed25519'"
- Authentication failures

### Root Causes:

- SSH keys not mounted
- Incorrect key paths
- Wrong file permissions

### Solutions:

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

### Symptoms

- All commands denied
- Error: "Policy evaluation failed"
- Unexpected command blocking

### Root Causes

- Invalid policy syntax
- Conflicting rules
- Missing policy sections

### Solutions

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
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest \
  python -c "
from mcp_ssh.policy import Policy
policy = Policy('/app/config/policy.yml')
result = policy.evaluate('web1', 'uptime', ['production'])
print('Policy result:', result)
"

```bash

### Network Issues

#### SSH Connection Errors

### Overview:

The orchestrator provides specific, actionable error messages for SSH connection failures. Error messages are sanitized for security (no IPs, hostnames, or file paths exposed) while providing enough information to troubleshoot.

### Common Error Messages and Solutions:

### 1. "SSH authentication failed: Invalid credentials"

- **Meaning:** Username, password, or SSH key is incorrect
- **Solutions:**
  - Verify username in `credentials.yml`
  - Check password or key passphrase secret is correct
  - Verify SSH key file is correct and not corrupted
  - Test authentication manually: `ssh -i /path/to/key user@host`

### 2. "SSH host key verification failed: Host key mismatch"

- **Meaning:** Host key in `known_hosts` doesn't match server
- **Solutions:**
  - Remove old host key: `ssh-keygen -R <hostname>`
  - Add new host key: `ssh-keyscan -H <hostname> >> /app/keys/known_hosts`
  - Verify host key: `ssh-keygen -l -f /app/keys/known_hosts`

### 3. "SSH host key not found: Add host to known_hosts"

- **Meaning:** Host is not in `known_hosts` file
- **Solutions:**
  - Add host key: `ssh-keyscan -H <hostname> >> /app/keys/known_hosts`
  - Verify file is mounted correctly in Docker
  - Check file permissions (should be readable)

### 4. "SSH connection timeout: Host did not respond"

- **Meaning:** Host is not reachable or SSH service is not running
- **Solutions:**
  - Test network connectivity: `ping <hostname>`
  - Check SSH service: `systemctl status ssh` (on target host)
  - Verify firewall rules allow SSH (port 22)
  - Check if host is behind VPN or requires special network access

### 5. "SSH connection refused: Port may be closed or firewall blocking"

- **Meaning:** SSH port is closed or blocked by firewall
- **Solutions:**
  - Verify SSH service is running: `systemctl status ssh`
  - Check port is open: `telnet <hostname> 22` or `nc -zv <hostname> 22`
  - Review firewall rules (iptables, firewalld, cloud security groups)
  - Verify port number in `servers.yml` is correct (default: 22)

### 6. "SSH hostname resolution failed: DNS lookup failed"

- **Meaning:** Hostname cannot be resolved to an IP address
- **Solutions:**
  - Test DNS resolution: `nslookup <hostname>` or `dig <hostname>`
  - Use IP address instead of hostname in `servers.yml`
  - Check DNS server configuration
  - Verify hostname is correct (typos, wrong domain)

### 7. "SSH key file not found: Check key path configuration"

- **Meaning:** SSH key file doesn't exist at specified path
- **Solutions:**
  - Verify key path in `credentials.yml` is correct
  - Check key file exists: `ls -la /app/keys/<key_path>`
  - Verify Docker volume mount includes keys directory
  - Use relative path (within `/app/keys`) or absolute path

### 8. "SSH key requires passphrase: Provide key_passphrase_secret"

- **Meaning:** Encrypted SSH key needs passphrase
- **Solutions:**
  - Add `key_passphrase_secret` to credentials entry in `credentials.yml`
  - Create secret file or set environment variable
  - Verify passphrase is correct

### 9. "SSH key permission denied: Check key file permissions (should be 600)"

- **Meaning:** SSH key file has incorrect permissions
- **Solutions:**
  - Fix permissions: `chmod 600 /app/keys/<key_file>`
  - Verify file ownership
  - Check Docker volume mount preserves permissions

### 10. "SSH network unreachable: Cannot reach host"

- **Meaning:** Network route to host doesn't exist
- **Solutions:**
  - Check network connectivity: `ping <hostname>`
  - Verify routing table
  - Check if host is on different network/VPN
  - Review network policy in `policy.yml` (network allowlist)

### 11. "SSH connection failed: Check host, port, and network connectivity"

- **Meaning:** Generic connection failure (fallback error)
- **Solutions:**
  - Check all of the above
  - Review server logs for detailed error (logged to stderr)
  - Verify host is accessible from orchestrator location
  - Test SSH connection manually to isolate issue

### Error Response Format:

When using `ssh_run` or `ssh_run_on_tag`, errors are returned in the response:

{
  "alias": "host1",
  "exit_code": -1,
  "output": "SSH connection refused: Port may be closed or firewall blocking",
  "duration_ms": 5
}
```

For `ssh_run_on_tag`, individual host failures don't stop the operation - each host's result is included in the `results` array:

{
  "tag": "production",
  "results": [
    {
      "alias": "host1",
      "exit_code": 0,
      "output": "command output"
    },
    {
      "alias": "host2",
      "exit_code": -1,
      "output": "SSH connection timeout: Host did not respond"
    }
  ]
}

```

### Command Chaining Errors

### Symptoms:

- Command denied even though individual commands are allowed
- Error: "Policy blocked command in chain: '<command>'"
- Chained commands fail when single commands work

### Root Causes:

- Command chaining operators (`&&`, `||`, `;`, `|`) are detected and each command is validated separately
- One or more commands in the chain are not allowed by policy
- Policy requires all commands in a chain to be individually allowed

**Understanding Command Chaining:**
The policy engine parses chained commands and validates each command individually. All commands in a chain must be allowed for the chain to execute.

### Example Error Response:

{
  "alias": "prod-web-1",
  "command": "uptime && apt list --upgradable",
  "allowed": false,
  "why": "Policy blocked command in chain: 'apt list --upgradable'",
  "denied_command": "apt list --upgradable"
}
```

### Solutions

1. **Identify the Denied Command:**
   - Use `ssh_plan` to check which command in the chain is denied
   - Look for `denied_command` field in the response
   - Check the `why` field for specific denial reason

1. **Fix Policy for Legitimate Chaining:**
   If you need to allow chaining of specific commands, add allow rules for each command:

   rules:
     - action: "allow"
       aliases: ["*"]
       tags: []
       commands:
         - "uptime*"
         - "apt list --upgradable*"  # Add this if you want to allow it

```bash

1. **Split Commands:**
   If chaining is not necessary, execute commands separately:

   # Instead of: uptime && apt list --upgradable

   # Execute separately

   ssh_run(alias="host1", command="uptime")
   ssh_run(alias="host1", command="apt list --upgradable")

   ```

1. **Check Command Substitution:**
   Commands with substitution (`` `cmd` ``, `$(cmd)`) are validated as part of the command:

   # This validates "echo" and the entire "$(apt list --upgradable)" substitution

   echo $(apt list --upgradable)

```

If the substitution contains a denied command, the entire command is blocked.

### Common Scenarios

### Scenario 1: Both Commands Allowed

# Policy allows: uptime*, whoami

uptime && whoami  # ✅ ALLOWED

```

### Scenario 2: One Command Denied

# Policy allows: uptime*

# Policy denies: apt list --upgradable*

uptime && apt list --upgradable  # ❌ DENIED (second command denied)

```

### Scenario 3: Multiple Commands

# Policy allows: uptime*, whoami, hostname*

uptime && whoami && hostname  # ✅ ALLOWED (all allowed)

uptime && apt list --upgradable && whoami  # ❌ DENIED (middle command denied)

```

### Scenario 4: Operators in Quotes

# Operators inside quotes are ignored

echo "hello && world" && whoami  # ✅ ALLOWED

# First command: echo "hello && world" (treated as single command)

# Second command: whoami

```bash

### Debugging Steps

1. Use `ssh_plan` to test the command and see which part is denied
2. Test each command individually to verify they're allowed
3. Check policy rules to ensure all commands in chain have allow rules
4. Review security logs for `command_chain_denied` events
5. Verify command substitution doesn't contain denied commands

### Security Note

Error messages are sanitized to prevent information disclosure:

- No IP addresses in user-facing errors
- No hostnames in user-facing errors
- No file paths in user-facing errors
- Detailed errors are logged to stderr for debugging (with full context)

#### SSH Connection Failures (Legacy Section)

### Symptoms

- "Connection refused" errors
- "Host key verification failed"
- Timeout errors

### Root Causes

- Network connectivity issues
- SSH service not running
- Host key verification failures
- Firewall blocking connections

### Solutions

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

### Symptoms

- "Host key verification failed"
- "Unknown host" errors
- Policy violations for host key checks

### Root Causes

- Missing host keys in known_hosts
- Changed host keys
- Host key verification disabled

### Solutions

# Add host key to known_hosts

ssh-keyscan 10.0.0.11 >> ~/mcp-ssh/keys/known_hosts

# Verify host key

ssh-keygen -l -f ~/mcp-ssh/keys/known_hosts

# Security: Host key verification is always enforced (CWE-295)

# Populate known_hosts file instead

# In policy.yml

require_known_host: true  # Always enforced for security (CWE-295)

# Populate known_hosts

ssh-keyscan -H <hostname> >> /app/keys/known_hosts

```yaml

### Container Issues

#### Container Won't Start

### Symptoms

- Container exits immediately
- "Permission denied" errors
- Resource limit exceeded

### Root Causes

- Insufficient resources
- Permission issues
- Configuration errors
- Missing dependencies

### Solutions

# Check container logs

docker logs $(docker ps -q --filter "ancestor=ghcr.io/samerfarida/mcp-ssh-orchestrator:latest")

# Test container health

docker run --rm ghcr.io/samerfarida/mcp-ssh-orchestrator:latest python -c "import mcp_ssh; print('OK')"

# Check resource usage

docker stats

# Increase resource limits

docker run -i --rm \
  --memory=1g \
  --cpus=2 \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

```

#### Permission Issues

### Symptoms

- "Permission denied" errors
- "Read-only file system" errors
- Container runs as root

### Root Causes

- Incorrect file permissions
- Container running as root
- Read-only filesystem issues

### Solutions

# Fix file permissions

chmod 0400 ~/mcp-ssh/keys/*
chmod 0444 ~/mcp-ssh/config/*

# Run container as non-root user

docker run -i --rm \
  --user=10001:10001 \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

# Check container user

docker run --rm ghcr.io/samerfarida/mcp-ssh-orchestrator:latest whoami

```text

### MCP Client Issues

#### Claude Desktop Integration Problems

### Symptoms

- MCP server not appearing in Claude Desktop
- "Connection failed" errors
- Tools not available

### Root Causes

- Incorrect configuration
- Container not running
- Network issues
- Version incompatibility

### Solutions

# Test MCP server directly

echo '{"jsonrpc":"2.0","method":"ping","id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

# Check Claude Desktop configuration

cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Restart Claude Desktop

killall "Claude Desktop"
open -a "Claude Desktop"

```

#### Tool Execution Failures

### Symptoms

- Tools not responding
- "Tool not found" errors
- Command execution failures

### Root Causes

- Tool registration issues
- Policy blocking commands
- SSH connection problems
- Resource limits exceeded

### Solutions

# List available tools

echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

# Test tool execution

echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_ping","arguments":{}},"id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

```json

## Debugging Techniques

### Enable Debug Logging

### Development Mode

# Enable debug logging

docker run -i --rm \
  -e MCP_SSH_DEBUG=1 \
  -e LOG_LEVEL=DEBUG \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

```

### Production Debugging

# Enable verbose logging

docker run -i --rm \
  -e LOG_LEVEL=INFO \
  -e LOG_FORMAT=json \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

```bash

### Network Debugging

### SSH Debug Mode

# Enable SSH debug logging

ssh -vvv -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11

# Test SSH connection with debug

docker run -i --rm \
  -e SSH_DEBUG=1 \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

```

### Network Connectivity Tests

# Test network connectivity

docker run --rm --network=host \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest \
  python -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = s.connect_ex(('10.0.0.11', 22))
print('SSH port accessible:', result == 0)
s.close()
"

```dockerfile

### Policy Debugging

### Policy Rule Testing

# Test specific policy rules

docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest \
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

### Policy Validation

# Validate policy configuration

docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest \
  python -c "
from mcp_ssh.policy import Policy
policy = Policy('/app/config/policy.yml')
print('Policy valid:', policy.validate())
print('Rules count:', len(policy.rules))
print('Limits:', policy.limits)
"

```yaml

## Performance Issues

### Slow Command Execution

### Symptoms

- Commands taking >30 seconds
- Timeout errors
- High resource usage

### Root Causes

- Network latency
- Target system performance
- Resource limits
- Policy complexity

### Solutions

# Check command execution time

time ssh -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11 "uptime"

# Monitor resource usage

docker stats

# Increase timeout limits

# In policy.yml

limits:
  max_seconds: 60
  max_output_bytes: 262144

```

### High Memory Usage

### Symptoms

- Container memory limit exceeded
- OOMKilled errors
- Slow performance

### Root Causes

- Large command outputs
- Memory leaks
- Insufficient limits
- Multiple concurrent sessions

### Solutions

# Monitor memory usage

docker stats

# Increase memory limits

docker run -i --rm \
  --memory=1g \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

# Limit output size

# In policy.yml

limits:
  max_output_bytes: 65536

```yaml

## Security Issues

### Authentication Failures

### Symptoms

- "Permission denied" errors
- "Authentication failed" errors
- Policy violations

### Root Causes

- Wrong SSH keys
- Incorrect credentials
- Key passphrase issues
- Target system changes

### Solutions

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

### Symptoms

- Commands denied unexpectedly
- "Policy violation" errors
- Security alerts

### Root Causes

- Incorrect policy rules
- Missing permissions
- Tag mismatches
- Command pattern issues

### Solutions

# Check policy rules

cat ~/mcp-ssh/config/policy.yml

# Test policy evaluation

docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest \
  python -c "
from mcp_ssh.policy import Policy
policy = Policy('/app/config/policy.yml')
result = policy.evaluate('web1', 'uptime', ['production'])
print('Policy result:', result)
"

```yaml

## Recovery Procedures

### Configuration Recovery

### Backup and Restore

# Backup configuration

tar -czf mcp-ssh-config-backup.tar.gz ~/mcp-ssh/config/

# Restore configuration

tar -xzf mcp-ssh-config-backup.tar.gz -C ~/

# Verify restoration

ls -la ~/mcp-ssh/config/

```

### Container Recovery

### Container Restart

# Stop all containers

docker stop $(docker ps -q --filter "ancestor=ghcr.io/samerfarida/mcp-ssh-orchestrator:latest")

# Remove containers

docker rm $(docker ps -aq --filter "ancestor=ghcr.io/samerfarida/mcp-ssh-orchestrator:latest")

# Start fresh

docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

```dockerfile

### Service Recovery

### Service Restart

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

### Collect Debug Information

# !/bin/bash

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

docker logs $(docker ps -q --filter "ancestor=ghcr.io/samerfarida/mcp-ssh-orchestrator:latest") > "$DEBUG_DIR/container-logs.txt"

# Network information

netstat -an > "$DEBUG_DIR/network-info.txt"

# Create debug package

tar -czf "$DEBUG_DIR.tar.gz" "$DEBUG_DIR"
echo "Debug package created: $DEBUG_DIR.tar.gz"

```text

### Community Support

### GitHub Issues

- Create detailed issue reports
- Include debug information
- Provide reproduction steps
- Attach relevant logs

### Documentation

- Check this wiki for solutions
- Review configuration examples
- Consult security best practices

## Next Steps

- **[Observability & Audit](11-Observability-Audit)** - Monitoring and logging setup
- **[Security Model](05-Security-Model)** - Security architecture details
- **[FAQ](14-FAQ)** - Common troubleshooting questions
- **[Contributing](13-Contributing)** - How to contribute fixes and improvements

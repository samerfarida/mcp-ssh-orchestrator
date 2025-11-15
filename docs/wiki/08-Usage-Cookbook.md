# 8. Usage Cookbook

**Purpose:** Practical examples and patterns for using mcp-ssh-orchestrator in different environments and scenarios.

## Overview

This cookbook provides **real-world examples** and **common patterns** for using mcp-ssh-orchestrator effectively. Each example includes configuration, commands, and expected results.

## Environment Configurations

### Development Environment

**Use Case:** Safe, permissive access for development and testing.

**servers.yml:**
```yaml
hosts:
  - alias: "dev-web-1"
    host: "192.168.1.10"
    port: 22
    credentials: "dev_admin"
    tags: ["development", "web", "linux"]
    description: "Development web server"

  - alias: "dev-db-1"
    host: "192.168.1.20"
    port: 22
    credentials: "dev_admin"
    tags: ["development", "database", "linux"]
    description: "Development database"
```

**credentials.yml:**
```yaml
entries:
  - name: "dev_admin"
    username: "developer"
    key_path: "dev_key"
    key_passphrase_secret: ""  # No passphrase for dev
    password_secret: ""
```

**policy.yml:**
```yaml
limits:
  max_seconds: 120
  max_output_bytes: 2097152  # 2MB
  require_known_host: true  # Always enforced for security (CWE-295)

network:
  allow_cidrs:
    - "192.168.0.0/16"
    - "10.0.0.0/8"
      require_known_host: true  # Always enforced for security (CWE-295)

rules:
  # Allow all commands in development
  - action: "allow"
    aliases: ["dev-*"]
    tags: ["development"]
    commands: ["*"]
```

**Usage Examples:**
```bash
# Test connectivity
ssh_ping
ssh_list_hosts

# Development operations
ssh_run --alias "dev-web-1" --command "docker ps"
ssh_run --alias "dev-web-1" --command "systemctl restart nginx"
ssh_run --alias "dev-db-1" --command "sudo -u postgres psql -c 'SELECT version()'"

# Bulk operations
ssh_run_on_tag --tag "development" --command "uptime"
```

### Staging Environment

**Use Case:** Moderate security with some operational flexibility.

**servers.yml:**
```yaml
hosts:
  - alias: "staging-web-1"
    host: "10.0.1.10"
    port: 22
    credentials: "staging_admin"
    tags: ["staging", "web", "linux"]
    description: "Staging web server"

  - alias: "staging-db-1"
    host: "10.0.1.20"
    port: 22
    credentials: "staging_admin"
    tags: ["staging", "database", "linux"]
    description: "Staging database"
```

**policy.yml:**
```yaml
limits:
  max_seconds: 90
  max_output_bytes: 1048576  # 1MB
  require_known_host: true  # Always enforced for security (CWE-295)

network:
  allow_cidrs:
    - "10.0.0.0/8"
      require_known_host: true  # Always enforced for security (CWE-295)

rules:
  # Read-only commands for all hosts
  - action: "allow"
    aliases: ["*"]
    tags: []
    commands:
      - "uname*"
      - "uptime*"
      - "df -h*"
      - "ps aux*"
      - "systemctl status *"

  # Staging-specific commands
  - action: "allow"
    aliases: ["staging-*"]
    tags: ["staging"]
    commands:
      - "systemctl restart *"
      - "systemctl stop *"
      - "systemctl start *"
      - "docker ps*"
      - "docker logs *"
      - "kubectl get *"
      - "kubectl describe *"

  # Network diagnostics for staging
  - action: "allow"
    aliases: ["staging-*"]
    tags: ["staging"]
    commands:
      - "ping*"
      - "traceroute*"
      - "ss -tulpn*"
      - "netstat*"
```

**Usage Examples:**
```bash
# Staging operations
ssh_run --alias "staging-web-1" --command "systemctl restart nginx"
ssh_run --alias "staging-web-1" --command "docker ps"
ssh_run --alias "staging-db-1" --command "systemctl status postgresql"

# Testing deployments
ssh_run_on_tag --tag "staging" --command "systemctl restart nginx"
ssh_run_on_tag --tag "staging" --command "docker pull nginx:latest"
```

### Production Environment

**Use Case:** Strict security with minimal allowed operations.

**servers.yml:**
```yaml
hosts:
  - alias: "prod-web-1"
    host: "10.0.0.10"
    port: 22
    credentials: "prod_admin"
    tags: ["production", "web", "linux", "critical"]
    description: "Primary production web server"

  - alias: "prod-web-2"
    host: "10.0.0.11"
    port: 22
    credentials: "prod_admin"
    tags: ["production", "web", "linux", "critical"]
    description: "Secondary production web server"

  - alias: "prod-db-1"
    host: "10.0.0.20"
    port: 22
    credentials: "prod_admin"
    tags: ["production", "database", "linux", "critical"]
    description: "Primary production database"
```

**policy.yml:**
```yaml
limits:
  max_seconds: 30
  max_output_bytes: 131072  # 128KB
  host_key_auto_add: false
  require_known_host: true
  deny_substrings:
    - "rm -rf /"
    - "shutdown*"
    - "reboot*"
    - "systemctl restart*"
    - "systemctl stop*"
    - "systemctl start*"
    - "apt *"
    - "yum *"
    - "docker run*"
    - "kubectl *"

network:
  allow_cidrs:
    - "10.0.0.0/8"
  block_cidrs:
    - "0.0.0.0/0"  # Block all public internet
  require_known_host: true

rules:
  # Minimal read-only commands for production
  - action: "allow"
    aliases: ["prod-*"]
    tags: ["production"]
    commands:
      - "uptime*"
      - "df -h*"
      - "systemctl status *"
      - "journalctl --no-pager -n 20 *"

  # Explicit deny for production
  - action: "deny"
    aliases: ["prod-*"]
    tags: ["production"]
    commands:
      - "systemctl restart*"
      - "systemctl stop*"
      - "systemctl start*"
      - "apt *"
      - "yum *"
      - "docker *"
      - "kubectl *"

overrides:
  aliases:
    prod-db-1:
      max_seconds: 15
      max_output_bytes: 65536
    prod-web-1:
      max_seconds: 20
      max_output_bytes: 131072
```

**Usage Examples:**
```bash
# Production monitoring only
ssh_run --alias "prod-web-1" --command "uptime"
ssh_run --alias "prod-web-1" --command "df -h"
ssh_run --alias "prod-web-1" --command "systemctl status nginx"

# Bulk monitoring
ssh_run_on_tag --tag "production" --command "uptime"
ssh_run_on_tag --tag "web" --command "systemctl status nginx"

# Policy testing (always test first!)
ssh_plan --alias "prod-web-1" --command "systemctl restart nginx"  # Should be denied
```

## Common Usage Patterns

### System Monitoring

**Health Checks:**
```bash
# Basic health check
ssh_ping

# System information
ssh_run --alias "web1" --command "uptime"
ssh_run --alias "web1" --command "df -h"
ssh_run --alias "web1" --command "free -h"

# Service status
ssh_run --alias "web1" --command "systemctl status nginx"
ssh_run --alias "web1" --command "systemctl is-active nginx"
ssh_run --alias "web1" --command "systemctl is-enabled nginx"
```

**Bulk Monitoring:**
```bash
# Check all production hosts
ssh_run_on_tag --tag "production" --command "uptime"
ssh_run_on_tag --tag "production" --command "df -h"

# Check specific service types
ssh_run_on_tag --tag "web" --command "systemctl status nginx"
ssh_run_on_tag --tag "database" --command "systemctl status postgresql"
```

### Service Management

**Service Operations:**
```bash
# Check service status
ssh_run --alias "web1" --command "systemctl status nginx"
ssh_run --alias "web1" --command "systemctl is-active nginx"

# Restart services (if allowed by policy)
ssh_run --alias "web1" --command "systemctl restart nginx"
ssh_run --alias "web1" --command "systemctl reload nginx"

# Enable/disable services
ssh_run --alias "web1" --command "systemctl enable nginx"
ssh_run --alias "web1" --command "systemctl disable nginx"
```

**Bulk Service Operations:**
```bash
# Restart all web servers
ssh_run_on_tag --tag "web" --command "systemctl restart nginx"

# Check all database services
ssh_run_on_tag --tag "database" --command "systemctl status postgresql"
```

### Log Analysis

**Log Inspection:**
```bash
# Recent logs
ssh_run --alias "web1" --command "journalctl --no-pager -n 20 nginx"
ssh_run --alias "web1" --command "tail -n 10 /var/log/nginx/access.log"

# Error logs
ssh_run --alias "web1" --command "journalctl --no-pager -p err nginx"
ssh_run --alias "web1" --command "grep ERROR /var/log/nginx/error.log | tail -5"
```

**Bulk Log Analysis:**
```bash
# Check logs across all web servers
ssh_run_on_tag --tag "web" --command "journalctl --no-pager -n 10 nginx"
ssh_run_on_tag --tag "web" --command "tail -n 5 /var/log/nginx/access.log"
```

### Process Management

**Process Information:**
```bash
# Running processes
ssh_run --alias "web1" --command "ps aux | grep nginx"
ssh_run --alias "web1" --command "ps aux | head -10"

# Process details
ssh_run --alias "web1" --command "top -n 1"
ssh_run --alias "web1" --command "htop -n 1"
```

**Resource Usage:**
```bash
# Memory usage
ssh_run --alias "web1" --command "free -h"
ssh_run --alias "web1" --command "cat /proc/meminfo | head -5"

# CPU usage
ssh_run --alias "web1" --command "top -n 1 | head -5"
ssh_run --alias "web1" --command "cat /proc/loadavg"
```

### Network Diagnostics

**Network Information:**
```bash
# Network interfaces
ssh_run --alias "web1" --command "ip addr show"
ssh_run --alias "web1" --command "ifconfig"

# Network connections
ssh_run --alias "web1" --command "ss -tulpn"
ssh_run --alias "web1" --command "netstat -tulpn"

# Routing information
ssh_run --alias "web1" --command "ip route show"
ssh_run --alias "web1" --command "route -n"
```

**Connectivity Testing:**
```bash
# Ping tests
ssh_run --alias "web1" --command "ping -c 3 8.8.8.8"
ssh_run --alias "web1" --command "ping -c 3 google.com"

# Port connectivity
ssh_run --alias "web1" --command "telnet localhost 80"
ssh_run --alias "web1" --command "nc -zv localhost 80"
```

## Advanced Patterns

### Policy Testing Workflow

**Always test before executing:**
```bash
# 1. Test policy first
ssh_plan --alias "web1" --command "systemctl restart nginx"

# 2. If allowed, execute
ssh_run --alias "web1" --command "systemctl restart nginx"

# 3. Verify result
ssh_run --alias "web1" --command "systemctl status nginx"
```

### Policy Tuning: Privileged Maintenance Window

**Goal:** Allow `DEBIAN_FRONTEND=noninteractive sudo apt-get upgrade -y` on a small set of hosts without loosening global policy.

1. **Edit policy.yml**
   ```yaml
   rules:
     - action: "allow"
       aliases:
         - "docker-prod-manager1"
         - "docker-prod-manager2"
         - "docker-prod-manager3"
       commands:
         - "sudo apt-get update*"
         - "DEBIAN_FRONTEND=noninteractive sudo apt-get upgrade -y*"

   overrides:
     aliases:
       docker-prod-manager1:
         max_seconds: 300
         task_result_ttl: 1800
   ```
   - Remove `sudo ` from the global `deny_substrings` list or override it for these aliases.
   - Copy the override block for each host that needs the longer timeout/output window.

2. **Reload & dry-run**
   ```bash
   ssh_reload_config
   ssh_plan --alias docker-prod-manager1 \
     --command "DEBIAN_FRONTEND=noninteractive sudo apt-get upgrade -y"
   ```

3. **Execute asynchronously**
   ```bash
   ssh_run_async --alias docker-prod-manager1 \
     --command "DEBIAN_FRONTEND=noninteractive sudo apt-get upgrade -y"
   ssh_get_task_status --task-id "<id>"
   ssh_get_task_result --task-id "<id>"
   ```

4. **Roll back overrides if temporary** once the window closes.

### Bulk Operations with Error Handling

**Safe bulk operations:**
```bash
# Check all hosts first
ssh_list_hosts

# Test policy for bulk operation
ssh_plan --alias "prod-web-1" --command "systemctl status nginx"

# Execute on subset if needed
ssh_run_on_tag --tag "web" --command "systemctl status nginx"
```

### Configuration Management

**Reload configuration:**
```bash
# After updating policy.yml
ssh_reload_config

# Verify new configuration
ssh_describe_host --alias "web1"
```

### Command Cancellation

**Long-running commands:**
```bash
# Start long-running command
ssh_run --alias "web1" --command "tail -f /var/log/nginx/access.log"

# Cancel if needed (use task_id from response)
ssh_cancel --task_id "web1:a1b2c3d4:1234567890"
```

## Environment-Specific Examples

### Web Server Management

**Nginx Operations:**
```bash
# Check configuration
ssh_run --alias "web1" --command "nginx -t"
ssh_run --alias "web1" --command "nginx -T"

# Service management
ssh_run --alias "web1" --command "systemctl status nginx"
ssh_run --alias "web1" --command "systemctl restart nginx"

# Log analysis
ssh_run --alias "web1" --command "tail -n 20 /var/log/nginx/access.log"
ssh_run --alias "web1" --command "tail -n 20 /var/log/nginx/error.log"
```

**Apache Operations:**
```bash
# Check configuration
ssh_run --alias "web1" --command "apache2ctl configtest"
ssh_run --alias "web1" --command "apache2ctl -S"

# Service management
ssh_run --alias "web1" --command "systemctl status apache2"
ssh_run --alias "web1" --command "systemctl restart apache2"

# Log analysis
ssh_run --alias "web1" --command "tail -n 20 /var/log/apache2/access.log"
ssh_run --alias "web1" --command "tail -n 20 /var/log/apache2/error.log"
```

### Database Management

**PostgreSQL Operations:**
```bash
# Service status
ssh_run --alias "db1" --command "systemctl status postgresql"
ssh_run --alias "db1" --command "systemctl is-active postgresql"

# Database queries
ssh_run --alias "db1" --command "sudo -u postgres psql -c 'SELECT version()'"
ssh_run --alias "db1" --command "sudo -u postgres psql -c 'SELECT current_database()'"

# Connection info
ssh_run --alias "db1" --command "sudo -u postgres psql -c 'SELECT * FROM pg_stat_activity;'"
```

**MySQL Operations:**
```bash
# Service status
ssh_run --alias "db1" --command "systemctl status mysql"
ssh_run --alias "db1" --command "systemctl is-active mysql"

# Database queries
ssh_run --alias "db1" --command "mysql -e 'SELECT VERSION()'"
ssh_run --alias "db1" --command "mysql -e 'SHOW DATABASES'"

# Connection info
ssh_run --alias "db1" --command "mysql -e 'SHOW PROCESSLIST'"
```

### Container Management

**Docker Operations:**
```bash
# Container status
ssh_run --alias "web1" --command "docker ps"
ssh_run --alias "web1" --command "docker ps -a"

# Container logs
ssh_run --alias "web1" --command "docker logs nginx"
ssh_run --alias "web1" --command "docker logs --tail 20 nginx"

# Container stats
ssh_run --alias "web1" --command "docker stats --no-stream"
```

**Kubernetes Operations:**
```bash
# Pod status
ssh_run --alias "k8s-node-1" --command "kubectl get pods"
ssh_run --alias "k8s-node-1" --command "kubectl get pods -o wide"

# Service status
ssh_run --alias "k8s-node-1" --command "kubectl get services"
ssh_run --alias "k8s-node-1" --command "kubectl get deployments"

# Node information
ssh_run --alias "k8s-node-1" --command "kubectl get nodes"
ssh_run --alias "k8s-node-1" --command "kubectl describe node k8s-node-1"
```

## Troubleshooting Patterns

### Connection Issues

**Test connectivity:**
```bash
# Basic connectivity
ssh_ping
ssh_list_hosts

# Host details
ssh_describe_host --alias "web1"

# Test policy
ssh_plan --alias "web1" --command "uptime"
```

### Policy Issues

**Debug policy decisions:**
```bash
# Test specific commands
ssh_plan --alias "web1" --command "uptime"
ssh_plan --alias "web1" --command "systemctl restart nginx"

# Check policy configuration
ssh_describe_host --alias "web1"
```

### Performance Issues

**Monitor resource usage:**
```bash
# System resources
ssh_run --alias "web1" --command "uptime"
ssh_run --alias "web1" --command "df -h"
ssh_run --alias "web1" --command "free -h"

# Process information
ssh_run --alias "web1" --command "ps aux | head -10"
ssh_run --alias "web1" --command "top -n 1"
```

## Inspector + Manual Validation Checklist

Use this workflow whenever you need to validate a release, exercise new resources, or reproduce bugs:

1. **Build the image**
   ```bash
   scripts/docker-build.sh
   ```
2. **Run MCP Inspector against the container**
   ```bash
   scripts/docker-smoketest.sh
   ```
   The helper script mirrors the bundled examples into a temporary directory, mounts them into Docker, and launches `npx @modelcontextprotocol/inspector docker run ...` so you can drive the stdio server interactively.
3. **Resource tour**
   - Browse `ssh://hosts`, `ssh://host/{alias}`, `ssh://host/{alias}/tags`, and `ssh://host/{alias}/capabilities`
   - Confirm `has_credentials_ref` shows credential presence without revealing names or secrets
4. **Tool smoke tests**
   - `ssh_plan` → `ssh_run` for an allowed path
   - `ssh_plan` → `ssh_run` for a denied path (policy + network)
   - `ssh_run_on_tag` for a populated tag and a tag with zero matches
   - Async lifecycle: `ssh_run_async`, `ssh_get_task_status`, `ssh_get_task_output`, `ssh_get_task_result`, `ssh_cancel`/`ssh_cancel_async_task`
   - `ssh_reload_config` after editing the mounted config dir
   - Confirm that policy/network denials include the `hint` field (and that `ssh_plan` returns `why` + `hint` when blocked) so LLM clients learn to re-run `ssh_plan`, consult the orchestrator prompts, **or escalate with a policy-update discussion** instead of looping on a forbidden command
5. **Context logging + observability**
   - Watch Inspector console for new `ctx.debug` / `ctx.info` events (task creation/completion, cancellation, reload)
   - Tail `docker logs -f <container>` to capture `policy_decision`, `audit`, `progress`, and `trace` entries for success, failure, denied, and cancelled flows
6. **Manual checklist recap**
   - Resource browsing complete
   - Allowed + denied commands verified
   - Tag fan-out path validated
   - Async lifecycle exercised end-to-end
   - Cancellation + reload flows tested
   - Logs reviewed for all paths, including security denials

Capture the commands you ran (or Inspector screenshots) in PR descriptions to show the release has been validated end-to-end.

## Next Steps

- **[Tools Reference](07-Tools-Reference)** - Complete tool documentation
- **[Configuration](06-Configuration)** - Configuration system details
- **[Troubleshooting](12-Troubleshooting)** - Common issues and solutions
- **[Deployment](09-Deployment)** - Production deployment examples

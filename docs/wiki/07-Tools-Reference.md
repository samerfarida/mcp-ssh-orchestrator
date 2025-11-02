# 7. Tools Reference

**Purpose:** Complete documentation of all MCP tools provided by MCP SSH Orchestrator, including parameters, return values, and usage examples.

## Input Validation

All user-controlled parameters are validated before processing:

- **Alias**: Max 100 characters, alphanumeric, dash, underscore, dot only
- **Command**: Max 10,000 characters, no null bytes or control characters (except newline, tab, carriage return)
- **Tag**: Max 50 characters, alphanumeric, dash, underscore, dot only
- **Task ID**: Max 200 characters, alphanumeric, colon, dash, underscore only

Invalid inputs are rejected with clear error messages. Security events are logged for injection attempts.

## Overview

MCP SSH Orchestrator provides **13 MCP tools** that enable secure SSH command execution, host management, and policy testing. All tools follow the MCP specification and return structured JSON responses.

## Tool Categories

### Health & Discovery Tools
- `ssh_ping` - Health check
- `ssh_list_hosts` - List configured hosts
- `ssh_describe_host` - Get host details

### Synchronous Execution Tools
- `ssh_run` - Execute command on single host (blocks until complete)
- `ssh_run_on_tag` - Execute command on multiple hosts (blocks until all complete)
- `ssh_cancel` - Cancel running command

### Asynchronous Execution Tools
- `ssh_run_async` - Start command execution asynchronously (returns immediately)
- `ssh_get_task_status` - Get current status of async task
- `ssh_get_task_result` - Get final result of completed task
- `ssh_get_task_output` - Stream recent output from running task
- `ssh_cancel_async_task` - Cancel async task

### Management Tools
- `ssh_plan` - Dry-run command (policy testing)
- `ssh_reload_config` - Reload configuration

## Tool Reference

### ssh_ping

**Purpose:** Health check to verify mcp-ssh-orchestrator is running and responsive.

**Parameters:** None

**Request:**
```json
{
  "name": "ssh_ping",
  "arguments": {}
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "mcp-ssh-orchestrator is running",
  "timestamp": 1729512345.67,
  "version": "0.1.0"
}
```

**Use Cases:**

- Verify MCP server is running
- Test connectivity to mcp-ssh-orchestrator
- Health monitoring and alerting

**Example:**
```bash
# Test via Claude Desktop
ssh_ping
```

---

### ssh_list_hosts

**Purpose:** List all configured hosts from servers.yml.

**Parameters:** None

**Request:**
```json
{
  "name": "ssh_list_hosts",
  "arguments": {}
}
```

**Response:**
```json
[
  "web1",
  "web2", 
  "db1",
  "monitor1"
]
```

**Use Cases:**

- Discover available hosts
- Verify host configuration
- Build dynamic host lists

**Example:**
```bash
# List all configured hosts
ssh_list_hosts
```

---

### ssh_describe_host

**Purpose:** Get detailed information about a specific host.

**Parameters:**
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `alias` | string | Yes | Host alias to describe | `"web1"` |

**Request:**
```json
{
  "name": "ssh_describe_host",
  "arguments": {
    "alias": "web1"
  }
}
```

**Response:**
```json
{
  "alias": "web1",
  "host": "10.0.0.11",
  "port": 22,
  "credentials": "prod_admin",
  "tags": ["production", "web", "linux"],
  "description": "Primary web server",
  "policy_limits": {
    "max_seconds": 30,
    "max_output_bytes": 524288,
    "require_known_host": true
  }
}
```

**Use Cases:**

- Get host connection details
- Verify host configuration
- Check policy limits for specific host

**Example:**
```bash
# Get details for web1
ssh_describe_host --alias "web1"
```

---

### ssh_plan

**Purpose:** Dry-run a command to test policy rules without executing.

**Parameters:**
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `alias` | string | Yes | Target host alias | `"web1"` |
| `command` | string | Yes | Command to test | `"uptime"` |

**Request:**
```json
{
  "name": "ssh_plan",
  "arguments": {
    "alias": "web1",
    "command": "uptime"
  }
}
```

**Response:**
```json
{
  "alias": "web1",
  "command": "uptime",
  "policy_decision": "allow",
  "rule_matched": "prod-readonly",
  "network_check": "passed",
  "execution_limits": {
    "max_seconds": 30,
    "max_output_bytes": 524288
  },
  "would_execute": true
}
```

**Use Cases:**

- Test policy rules before execution
- Debug policy configuration
- Validate command authorization
- Learn about policy behavior

**Example:**
```bash
# Test if command would be allowed
ssh_plan --alias "web1" --command "uptime"
ssh_plan --alias "prod-web-1" --command "systemctl restart nginx"
```

---

### ssh_run

**Purpose:** Execute a command on a single host.

**Parameters:**
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `alias` | string | Yes | Target host alias | `"web1"` |
| `command` | string | Yes | Command to execute | `"uptime"` |

**Request:**
```json
{
  "name": "ssh_run",
  "arguments": {
    "alias": "web1",
    "command": "uptime"
  }
}
```

**Response:**
```json
{
  "task_id": "web1:a1b2c3d4:1234567890",
  "alias": "web1",
  "command": "uptime",
  "exit_code": 0,
  "duration_ms": 123,
  "cancelled": false,
  "timeout": false,
  "target_ip": "10.0.0.11",
  "output": " 14:30:45 up 42 days,  3:14,  1 user,  load average: 0.15, 0.08, 0.05",
  "error": "",
  "policy_decision": "allow",
  "rule_matched": "prod-readonly"
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Unique task identifier |
| `alias` | string | Target host alias |
| `command` | string | Executed command |
| `exit_code` | integer | Command exit status (0 = success) |
| `duration_ms` | integer | Execution time in milliseconds |
| `cancelled` | boolean | Whether command was cancelled |
| `timeout` | boolean | Whether command timed out |
| `target_ip` | string | Actual IP address connected to |
| `output` | string | Command stdout output |
| `error` | string | Command stderr output |
| `policy_decision` | string | Policy decision (allow/deny) |
| `rule_matched` | string | Policy rule that matched |

**Use Cases:**

- Execute single commands on hosts
- Run system diagnostics
- Perform maintenance tasks
- Test host connectivity

**Example:**
```bash
# Execute uptime command
ssh_run --alias "web1" --command "uptime"

# Check disk usage
ssh_run --alias "web1" --command "df -h"

# Check service status
ssh_run --alias "web1" --command "systemctl status nginx"
```

---

### ssh_run_on_tag

**Purpose:** Execute a command on all hosts with a specific tag.

**Parameters:**
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `tag` | string | Yes | Tag to match hosts | `"production"` |
| `command` | string | Yes | Command to execute | `"uptime"` |

**Request:**
```json
{
  "name": "ssh_run_on_tag",
  "arguments": {
    "tag": "production",
    "command": "uptime"
  }
}
```

**Response:**
```json
{
  "tag": "production",
  "command": "uptime",
  "hosts_matched": ["prod-web-1", "prod-web-2", "prod-db-1"],
  "results": [
    {
      "task_id": "prod-web-1:a1b2c3d4:1234567890",
      "alias": "prod-web-1",
      "exit_code": 0,
      "duration_ms": 123,
      "output": " 14:30:45 up 42 days,  3:14,  1 user,  load average: 0.15, 0.08, 0.05"
    },
    {
      "task_id": "prod-web-2:a1b2c3d4:1234567891",
      "alias": "prod-web-2", 
      "exit_code": 0,
      "duration_ms": 145,
      "output": " 14:30:45 up 41 days,  2:45,  2 users,  load average: 0.25, 0.12, 0.08"
    },
    {
      "task_id": "prod-db-1:a1b2c3d4:1234567892",
      "alias": "prod-db-1",
      "exit_code": 0,
      "duration_ms": 98,
      "output": " 14:30:45 up 43 days,  1:23,  0 users,  load average: 0.05, 0.03, 0.02"
    }
  ],
  "summary": {
    "total_hosts": 3,
    "successful": 3,
    "failed": 0,
    "cancelled": 0,
    "timeout": 0
  }
}
```

**Use Cases:**

- Bulk operations across host groups
- Environment-wide maintenance
- Tag-based host management
- Parallel command execution

**Example:**
```bash
# Check uptime on all production hosts
ssh_run_on_tag --tag "production" --command "uptime"

# Check disk usage on all web servers
ssh_run_on_tag --tag "web" --command "df -h"

# Check service status on all database servers
ssh_run_on_tag --tag "database" --command "systemctl status postgresql"
```

---

### ssh_cancel

**Purpose:** Cancel a running command using its task ID.

**Parameters:**
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `task_id` | string | Yes | Task ID to cancel | `"web1:a1b2c3d4:1234567890"` |

**Request:**
```json
{
  "name": "ssh_cancel",
  "arguments": {
    "task_id": "web1:a1b2c3d4:1234567890"
  }
}
```

**Response:**
```json
{
  "task_id": "web1:a1b2c3d4:1234567890",
  "cancelled": true,
  "message": "Command cancelled successfully"
}
```

**Use Cases:**

- Stop long-running commands
- Cancel stuck processes
- Emergency command termination
- Resource management

**Example:**
```bash
# Cancel a running command
ssh_cancel --task_id "web1:a1b2c3d4:1234567890"
```

---

### ssh_reload_config

**Purpose:** Reload configuration files without restarting the MCP server.

**Parameters:** None

**Request:**
```json
{
  "name": "ssh_reload_config",
  "arguments": {}
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Configuration reloaded successfully",
  "files_reloaded": [
    "servers.yml",
    "credentials.yml", 
    "policy.yml"
  ],
  "timestamp": 1729512345.67
}
```

**Use Cases:**

- Update configuration without restart
- Apply policy changes
- Add new hosts dynamically
- Update credentials

**Example:**
```bash
# Reload configuration
ssh_reload_config
```

---

### ssh_run_async

**Purpose:** Start SSH command execution asynchronously. Returns immediately with a task ID for polling results.

**Parameters:**
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `alias` | string | Yes | Target host alias | `"web1"` |
| `command` | string | Yes | Command to execute | `"long-running-script.sh"` |

**Request:**
```json
{
  "name": "ssh_run_async",
  "arguments": {
    "alias": "web1",
    "command": "long-running-script.sh"
  }
}
```

**Response:**
```json
{
  "task_id": "async:web1:abc123def456",
  "status": "pending",
  "keepAlive": 300,
  "pollFrequency": 5,
  "alias": "web1",
  "command": "long-running-script.sh",
  "hash": "abc123def456"
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Unique async task identifier |
| `status` | string | Initial status (always "pending") |
| `keepAlive` | integer | Result retention time in seconds |
| `pollFrequency` | integer | Recommended polling interval in seconds |
| `alias` | string | Target host alias |
| `command` | string | Command being executed |
| `hash` | string | SHA256 hash of the command |

**Use Cases:**

- Long-running commands (minutes to hours)
- Background execution
- Non-blocking operations
- Progress monitoring

**Example:**
```bash
# Start long-running backup
ssh_run_async --alias "backup-server" --command "tar -czf /backup/full.tar.gz /data"

# Start deployment script
ssh_run_async --alias "prod-web" --command "./deploy.sh"
```

---

### ssh_get_task_status

**Purpose:** Get current status and progress of an async task without waiting for completion.

**Parameters:**
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `task_id` | string | Yes | Async task ID | `"async:web1:abc123"` |

**Request:**
```json
{
  "name": "ssh_get_task_status",
  "arguments": {
    "task_id": "async:web1:abc123def456"
  }
}
```

**Response:**
```json
{
  "task_id": "async:web1:abc123def456",
  "status": "running",
  "progress": {
    "percentage": 45,
    "elapsed_ms": 45000,
    "bytes_read": 2048000
  },
  "alias": "web1",
  "command": "long-running-script.sh"
}
```

**Status Values:**

- `pending` - Task not yet started
- `running` - Task in progress
- `completed` - Task finished successfully
- `failed` - Task failed with error
- `cancelled` - Task was cancelled
- `timeout` - Task exceeded time limit
- `not_found` - Task ID doesn't exist

**Use Cases:**

- Monitor long-running operations
- Check task progress percentage
- Verify task is still running
- Track execution time

**Example:**
```bash
# Check status
ssh_get_task_status --task_id "async:web1:abc123def456"

# Monitor every 5 seconds
watch -n 5 ssh_get_task_status --task_id "async:web1:abc123def456"
```

---

### ssh_get_task_result

**Purpose:** Get final result of a completed async task (success or failure).

**Parameters:**
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `task_id` | string | Yes | Async task ID | `"async:web1:abc123"` |

**Request:**
```json
{
  "name": "ssh_get_task_result",
  "arguments": {
    "task_id": "async:web1:abc123def456"
  }
}
```

**Response:**
```json
{
  "task_id": "async:web1:abc123def456",
  "status": "completed",
  "result": {
    "exit_code": 0,
    "duration_ms": 125000,
    "bytes_out": 4096000,
    "bytes_err": 0,
    "output": "Backup completed successfully...",
    "error": ""
  },
  "alias": "web1",
  "command": "long-running-script.sh"
}
```

**Result Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `exit_code` | integer | Command exit status (0 = success) |
| `duration_ms` | integer | Total execution time |
| `bytes_out` | integer | Bytes of stdout captured |
| `bytes_err` | integer | Bytes of stderr captured |
| `output` | string | Complete stdout output |
| `error` | string | Complete stderr output |

**Use Cases:**

- Retrieve final output of completed tasks
- Check exit codes
- Analyze execution results
- Handle task outcomes

**Example:**
```bash
# Get final result
ssh_get_task_result --task_id "async:web1:abc123def456"

# Check if successful
if ssh_get_task_result --task_id "async:web1:abc123def456" | grep '"exit_code": 0'; then
  echo "Task succeeded"
fi
```

---

### ssh_get_task_output

**Purpose:** Stream recent output lines from a running or completed task.

**Parameters:**
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `task_id` | string | Yes | Async task ID | `"async:web1:abc123"` |
| `max_lines` | integer | No | Maximum lines to return (default: 50) | `100` |

**Request:**
```json
{
  "name": "ssh_get_task_output",
  "arguments": {
    "task_id": "async:web1:abc123def456",
    "max_lines": 50
  }
}
```

**Response:**
```json
{
  "task_id": "async:web1:abc123def456",
  "status": "running",
  "output_lines": [
    "Starting backup...",
    "Processing directory /data/subdir1...",
    "Processing directory /data/subdir2...",
    "Current progress: 45%"
  ],
  "total_lines_available": 100
}
```

**Use Cases:**

- Stream output from long-running tasks
- Monitor progress in real-time
- Debug running commands
- Check recent activity

**Example:**
```bash
# Get last 50 lines of output
ssh_get_task_output --task_id "async:web1:abc123def456"

# Get last 100 lines
ssh_get_task_output --task_id "async:web1:abc123def456" --max_lines 100

# Stream in real-time
while true; do
  ssh_get_task_output --task_id "async:web1:abc123def456"
  sleep 5
done
```

---

### ssh_cancel_async_task

**Purpose:** Cancel a running async task.

**Parameters:**
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `task_id` | string | Yes | Async task ID to cancel | `"async:web1:abc123"` |

**Request:**
```json
{
  "name": "ssh_cancel_async_task",
  "arguments": {
    "task_id": "async:web1:abc123def456"
  }
}
```

**Response:**
```json
{
  "task_id": "async:web1:abc123def456",
  "cancelled": true,
  "message": "Cancellation signaled for async task"
}
```

**Use Cases:**

- Stop long-running commands
- Abort stuck processes
- Emergency termination
- Resource management

**Example:**
```bash
# Cancel async task
ssh_cancel_async_task --task_id "async:web1:abc123def456"
```

## Tool Usage Patterns

### Health Monitoring

```bash
# Check system health
ssh_ping

# List all hosts
ssh_list_hosts

# Check specific host details
ssh_describe_host --alias "web1"
```

### Policy Testing

```bash
# Test policy before execution
ssh_plan --alias "web1" --command "uptime"
ssh_plan --alias "prod-web-1" --command "systemctl restart nginx"

# Test network policies
ssh_plan --alias "web1" --command "ping 8.8.8.8"
```

### Single Host Operations

```bash
# System information
ssh_run --alias "web1" --command "uptime"
ssh_run --alias "web1" --command "df -h"
ssh_run --alias "web1" --command "free -h"

# Service management
ssh_run --alias "web1" --command "systemctl status nginx"
ssh_run --alias "web1" --command "systemctl is-active nginx"

# Process information
ssh_run --alias "web1" --command "ps aux | grep nginx"
ssh_run --alias "web1" --command "top -n 1"
```

### Bulk Operations

```bash
# Environment-wide checks
ssh_run_on_tag --tag "production" --command "uptime"
ssh_run_on_tag --tag "production" --command "df -h"

# Service-specific operations
ssh_run_on_tag --tag "web" --command "systemctl status nginx"
ssh_run_on_tag --tag "database" --command "systemctl status postgresql"

# Infrastructure checks
ssh_run_on_tag --tag "monitoring" --command "systemctl status prometheus"
```

### Command Management

```bash
# Start long-running command (synchronous)
ssh_run --alias "web1" --command "tail -f /var/log/nginx/access.log"

# Cancel if needed
ssh_cancel --task_id "web1:a1b2c3d4:1234567890"

# Reload configuration
ssh_reload_config
```

### Async Task Management

```bash
# Start async backup
TASK_ID=$(ssh_run_async --alias "backup-server" --command "tar -czf /backup/full.tar.gz /data")

# Monitor progress
ssh_get_task_status --task_id "$TASK_ID"

# Stream output in real-time
ssh_get_task_output --task_id "$TASK_ID" --max_lines 100

# Get final result when complete
ssh_get_task_result --task_id "$TASK_ID"

# Cancel if needed
ssh_cancel_async_task --task_id "$TASK_ID"
```

### Long-Running Operations

```bash
# Start deployment asynchronously
TASK_ID=$(ssh_run_async --alias "prod-web" --command "./deploy.sh")

# Poll until complete
while true; do
  STATUS=$(ssh_get_task_status --task_id "$TASK_ID" | jq -r '.status')
  if [ "$STATUS" == "completed" ]; then
    ssh_get_task_result --task_id "$TASK_ID"
    break
  elif [ "$STATUS" == "failed" ]; then
    echo "Task failed"
    ssh_get_task_result --task_id "$TASK_ID"
    break
  fi
  sleep 5
done
```

## Error Handling

### Common Error Responses

**Policy Denied:**
```json
{
  "error": "Policy denied",
  "alias": "web1",
  "command": "rm -rf /",
  "policy_decision": "deny",
  "reason": "Command contains blocked substring: rm -rf /"
}
```

**Host Not Found:**
```json
{
  "error": "Host not found",
  "alias": "nonexistent",
  "available_hosts": ["web1", "web2", "db1"]
}
```

**Network Blocked:**
```json
{
  "error": "Network access denied",
  "alias": "web1",
  "target_ip": "8.8.8.8",
  "reason": "IP not in allowlist"
}
```

**SSH Connection Failed:**
```json
{
  "error": "SSH connection failed",
  "alias": "web1",
  "target_ip": "10.0.0.11",
  "reason": "Connection refused",
  "exit_code": 255
}
```

**Command Timeout:**
```json
{
  "task_id": "web1:a1b2c3d4:1234567890",
  "alias": "web1",
  "command": "sleep 120",
  "exit_code": 124,
  "timeout": true,
  "duration_ms": 60000
}
```

## Security Considerations

### Policy Enforcement

All tools respect policy configuration:
- **ssh_run**, **ssh_run_on_tag**, and **ssh_run_async** check policy before execution
- **ssh_plan** shows policy decision without executing
- **ssh_cancel** and **ssh_cancel_async_task** respect cancellation policies
- **ssh_reload_config** validates new configuration

### Audit Logging

All tool usage is logged:
- **JSON audit logs** to stderr
- **Complete operation trail** for compliance
- **Security-relevant metadata** in every log entry
- **Immutable log format** for integrity

### Network Security

All tools enforce network policies:
- **IP allowlists** prevent unauthorized connections
- **Host key verification** prevents MITM attacks
- **DNS resolution** verification before connection
- **Network segmentation** via CIDR controls

## Next Steps

- **[Usage Cookbook](08-Usage-Cookbook)** - Practical tool usage examples
- **[Configuration](06-Configuration)** - Tool configuration and policies
- **[Troubleshooting](12-Troubleshooting)** - Common tool issues and solutions
- **[Deployment](09-Deployment)** - Production tool deployment

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

**Structured Output:** All tools return structured Python dicts (not JSON strings). FastMCP automatically:

- Generates JSON schemas for clients
- Validates tool outputs
- Wraps responses in MCP tool response format

This provides better type safety, schema validation, and improved client experience compared to manual JSON string encoding.

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

## MCP Resources

FastMCP also exposes read-only resources so MCP clients can inspect your fleet without invoking tools.

### `ssh://hosts`

- **Purpose:** Sanitized inventory with `alias`, `host`, `port`, `tags`, `description`, and `has_credentials_ref`
- **Response:**

```json
{
  "count": 4,
  "hosts": [
    {"alias": "prod-web-1", "host": "10.0.0.11", "port": 22, "tags": ["production","web"], "description": "Primary public web front-end", "has_credentials_ref": true}
  ]
}
```

### `ssh://host/{alias}`

- **Purpose:** Detailed metadata for a single alias, reusing `_validate_alias()` for safety
- **Behavior:** Returns `{ "error": "<reason>" }` for invalid inputs or missing hosts

### `ssh://host/{alias}/tags`

- **Purpose:** Lightweight tag list for planning tag-based executions
- **Response:** `{ "alias": "prod-web-1", "tags": ["production","web","critical-service"] }`

### `ssh://host/{alias}/capabilities`

- **Purpose:** High-level summary of policy-derived limits, network controls, and sample command allowances
- **Fields:** `limits`, `policy_probes`, `network`, `features`
- **Example snippet:**

```json
{
  "alias": "prod-web-1",
  "limits": {
    "max_seconds": 60,
    "max_output_bytes": 1048576,
    "require_known_host": true,
    "host_key_auto_add": false,
    "deny_patterns_enabled": true
  },
  "policy_probes": [
    {"probe": "basic_diagnostics", "command": "uptime", "allowed": true},
    {"probe": "docker_status", "command": "docker ps", "allowed": false}
  ],
  "network": {
    "require_known_host": true,
    "allowlist_enabled": true,
    "blocklist_enabled": true
  },
  "features": {
    "supports_async": true,
    "supports_cancellation": true
  }
}
```

Resources show up in MCP Inspector, Cursor, Claude Desktop, and any MCP-compatible client under the **Resources** tab so LLMs can reason about topology before calling tools.

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
  "status": "pong"
}
```

**Note:** Tools now return structured JSON objects. FastMCP automatically generates schemas and validates outputs.

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
{
  "hosts": [
    "web1",
    "web2",
    "db1",
    "monitor1"
  ]
}
```

**Note:** Returns a structured object with a `hosts` array. FastMCP generates the schema automatically.

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
  "tags": ["production", "web"],
  "description": "Primary web server"
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
  "hash": "4c2d8a8f7b1e",
  "allowed": true,
  "limits": {
    "max_seconds": 60,
    "max_output_bytes": 1048576,
    "host_key_auto_add": false,
    "require_known_host": true
  }
}
```

> When `allowed` is `false`, the response also includes `why` and `hint` fields so MCP clients know to call `ssh_plan` again or consult the SSH Orchestrator prompts before retrying. No sensitive policy details are exposed.

**Use Cases:**

- Test policy rules before execution
- Inspect effective execution limits
- Debug policy configuration
- Validate command authorization

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
  "task_id": "web1:4c2d8a8f7b1e:1700000000000",
  "alias": "web1",
  "hash": "4c2d8a8f7b1e",
  "exit_code": 0,
  "duration_ms": 1234,
  "cancelled": false,
  "timeout": false,
  "target_ip": "10.0.0.11",
  "output": "14:30:45 up 42 days,  3:14,  1 user,  load average: 0.15, 0.08, 0.05"
}
```

> Policy or network denials return structured JSON with a `hint` field that reminds the caller to use `ssh_plan` or review the orchestrator prompts for next steps.

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Unique task identifier (`alias:hash:timestamp`) |
| `alias` | string | Target host alias |
| `hash` | string | Short SHA256 hash of the command |
| `exit_code` | integer | Command exit status (0 = success, -1 = connection/execution error) |
| `duration_ms` | integer | Execution time in milliseconds |
| `cancelled` | boolean | Whether command was cancelled |
| `timeout` | boolean | Whether command hit the time limit |
| `target_ip` | string | Actual IP address connected to |
| `output` | string | Combined stdout/stderr output (truncated to limit), or error message if `exit_code` is -1 |

**Error Handling:**

If SSH connection fails, the response includes:

- `exit_code: -1` indicating connection/execution failure
- `output`: Specific, sanitized error message (e.g., "SSH connection refused: Port may be closed or firewall blocking")
- `target_ip: ""` (empty, as connection was not established)
- `duration_ms: 0` or small value (connection failed quickly)

**Error Message Examples:**

- `"SSH authentication failed: Invalid credentials"`
- `"SSH connection timeout: Host did not respond"`
- `"SSH connection refused: Port may be closed or firewall blocking"`
- `"SSH hostname resolution failed: DNS lookup failed"`
- `"SSH key file not found: Check key path configuration"`

All error messages are sanitized for security (no IPs, hostnames, or file paths exposed). See [Troubleshooting Guide](../12-Troubleshooting.md#ssh-connection-errors) for detailed solutions.

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
  "results": [
    {
      "alias": "prod-web-1",
      "task_id": "prod-web-1:4c2d8a8f7b1e:1700000000000",
      "hash": "4c2d8a8f7b1e",
      "exit_code": 0,
      "duration_ms": 1100,
      "cancelled": false,
      "timeout": false,
      "target_ip": "10.0.0.11",
      "output": "uptime output..."
    },
    {
      "alias": "prod-db-1",
      "hash": "4c2d8a8f7b1e",
      "denied": true,
      "reason": "policy"
    }
  ]
}
```

**Notes:**

- Entries include `task_id` when a command was executed. Denied hosts omit `task_id` and include `denied`/`reason`.
- Policy or network denials include `hint` text that points MCP clients back to `ssh_plan` or the orchestrator prompts for next steps.
- No summary object is returned; aggregate stats can be derived from the `results` array.

**Per-Host Error Handling:**

Individual host failures are handled gracefully - one host failure does not stop execution on other hosts. Each host's result is included in the `results` array:

- **Successful hosts:** `exit_code: 0`, `output` contains command output
- **Failed hosts:** `exit_code: -1`, `output` contains specific error message
- **Denied hosts:** `denied: true`, `reason` explains why (policy/network)

**Example Response with Mixed Success/Failure:**

```json
{
  "tag": "production",
  "results": [
    {
      "alias": "prod-web-1",
      "task_id": "prod-web-1:4c2d8a8f7b1e:1700000000000",
      "hash": "4c2d8a8f7b1e",
      "exit_code": 0,
      "duration_ms": 1100,
      "cancelled": false,
      "timeout": false,
      "target_ip": "10.0.0.11",
      "output": "uptime output..."
    },
    {
      "alias": "prod-web-2",
      "task_id": "prod-web-2:4c2d8a8f7b1e:1700000000001",
      "hash": "4c2d8a8f7b1e",
      "exit_code": -1,
      "duration_ms": 5,
      "cancelled": false,
      "timeout": false,
      "target_ip": "",
      "output": "SSH connection timeout: Host did not respond"
    },
    {
      "alias": "prod-db-1",
      "hash": "4c2d8a8f7b1e",
      "denied": true,
      "reason": "policy"
    }
  ]
}
```

**Error Messages:**

Failed hosts return specific, actionable error messages in the `output` field:

- `"SSH connection refused: Port may be closed or firewall blocking"`
- `"SSH connection timeout: Host did not respond"`
- `"SSH authentication failed: Invalid credentials"`
- `"SSH hostname resolution failed: DNS lookup failed"`

All error messages are sanitized for security. See [Troubleshooting Guide](../12-Troubleshooting.md#ssh-connection-errors) for detailed solutions.

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

```text
Cancellation signaled for task_id: web1:4c2d8a8f7b1e:1700000000000
```

**Errors:**

- `Task not found: <task_id>` — the ID is unknown or already completed.

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

```text
Configuration reloaded.
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
  "task_id": "web1:4c2d8a8f7b1e:1700000000000",
  "status": "pending",
  "keepAlive": 300,
  "pollFrequency": 5,
  "alias": "web1",
  "command": "long-running-script.sh",
  "hash": "4c2d8a8f7b1e"
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
  "task_id": "web1:4c2d8a8f7b1e:1700000000000",
  "status": "running",
  "keepAlive": 300,
  "pollFrequency": 5,
  "progress_percent": 42,
  "elapsed_ms": 18000,
  "bytes_read": 8192,
  "output_lines_available": 24
}
```

**Response Fields:**

| Field | Description |
|-------|-------------|
| `task_id` | Async task identifier |
| `status` | `pending`, `running`, `completed`, `failed`, or `cancelled` |
| `keepAlive` | Seconds the result will be retained (approximate) |
| `pollFrequency` | Suggested polling interval in seconds |
| `progress_percent` | Progress estimate based on elapsed time vs `max_seconds` |
| `elapsed_ms` | Milliseconds since task started |
| `bytes_read` | Bytes collected from stdout/stderr so far |
| `output_lines_available` | Number of buffered output lines retrievable via `ssh_get_task_output` |

**Errors:**

- `Error: Task not found: <task_id>` — unknown or expired ID.

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
  "task_id": "web1:4c2d8a8f7b1e:1700000000000",
  "status": "completed",
  "exit_code": 0,
  "duration_ms": 42000,
  "output": "backup complete",
  "cancelled": false,
  "timeout": false,
  "target_ip": "10.0.0.11",
  "max_seconds": 3600
}
```

**Errors:**

- `Error: Task not found or expired: <task_id>` — result exceeded TTL or never existed.

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
  "task_id": "web1:4c2d8a8f7b1e:1700000000000",
  "output_lines": [
    "[2025-11-09 14:30:41] backup chunk 12/42",
    "[2025-11-09 14:30:42] backup chunk 13/42"
  ],
  "total_lines": 384,
  "has_more": true
}
```

**Response Fields:**

| Field | Description |
|-------|-------------|
| `task_id` | Async task identifier |
| `output_lines` | Most recent lines from stdout/stderr (bounded by `max_lines`) |
| `total_lines` | Total buffered lines available |
| `has_more` | `true` if additional lines can be retrieved |

**Errors:**

- `Error: Task not found or no output available: <task_id>` — ID invalid or no buffered output.

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
| `task_id` | string | Yes | Async task ID to cancel | "web1:4c2d8a8f7b1e:1700000000000" |

**Request:**

```json
{
  "name": "ssh_cancel_async_task",
  "arguments": {
    "task_id": "web1:4c2d8a8f7b1e:1700000000000"
  }
}
```

**Response:**

```text
Cancellation signaled for async task: web1:4c2d8a8f7b1e:1700000000000
```

**Errors:**

- `Task not found or not cancellable: <task_id>` — task already finished or unknown.

**Use Cases:**

- Stop long-running commands
- Abort stuck processes
- Emergency termination
- Resource management

**Example:**

```bash
# Cancel async task
ssh_cancel_async_task --task_id "web1:4c2d8a8f7b1e:1700000000000"
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

## Prompts

MCP SSH Orchestrator provides **6 prompts** that guide LLM behavior when interacting with the orchestrator. Prompts are reusable templates that help LLMs understand how to safely use the tools, handle denials, and suggest configuration changes.

**Available Prompts:**

1. **ssh_orchestrator_usage** - General usage guidance for SSH orchestrator tools
   - Explains available tools and rules for safe usage
   - Guides workflow patterns and best practices

2. **ssh_policy_denied_guidance** - How to handle policy denials
   - Guides LLM on responding to policy denials
   - Explains how to ask about policy changes and propose YAML snippets

3. **ssh_network_denied_guidance** - How to handle network policy denials
   - Guides LLM on responding to network policy denials
   - Explains how to ask about IP/CIDR allowlists and propose network changes

4. **ssh_missing_host_guidance** - How to handle missing host aliases
   - Guides LLM on handling missing host aliases
   - Explains how to propose YAML entries for servers.yml

5. **ssh_missing_credentials_guidance** - How to handle missing/incomplete credentials
   - Guides LLM on handling missing credentials
   - Explains how to propose YAML entries for credentials.yml

6. **ssh_config_change_workflow** - Global rules for config change suggestions
   - Global workflow rules for suggesting config changes
   - Explains how to handle all three YAML files (servers.yml, credentials.yml, policy.yml)

**Using Prompts:**

Prompts are exposed via the MCP protocol and can be retrieved using `prompts/list` and `prompts/get` operations. MCP clients (Claude Desktop, Cursor, etc.) can use these prompts to guide LLM behavior.

**Example:**

```bash
# List all available prompts
prompts/list

# Get a specific prompt
prompts/get --name ssh_orchestrator_usage
```

**Note:** Prompts are client-controlled templates. The server does not invoke them automatically - they are used by MCP clients to guide LLM behavior.

## Error Handling

### Common Error Responses

- **Policy denied:** Returns structured JSON with `status: "denied"` and `reason: "policy"` — command matches a deny rule or substring.
- **Host not found:** `Error: Host alias not found: <alias>` — configuration missing the requested host.
- **Invalid alias/tag/command:** `Error: <reason>` — input validation failed (length, characters, null bytes, etc.).
- **Network blocked:** Returns structured JSON with `status: "denied"` and `reason: "network"` — DNS resolution failed allowlist checks or post-connect IP blocked.
- **SSH connection issues:** `Run error: <sanitized message>` — authentication, host key, or connection failures. Detailed context is logged to stderr for auditing.

**Structured JSON Denial Responses:**

Policy and network denials now return structured JSON for better LLM understanding:

```json
{
  "status": "denied",
  "reason": "policy",
  "alias": "web1",
  "hash": "a1b2c3d4",
  "command": "rm -rf /"
}
```

```json
{
  "status": "denied",
  "reason": "network",
  "alias": "web1",
  "hostname": "10.0.0.1",
  "detail": "No resolved IPs allowed by policy.network"
}
```

This structured format makes it easier for LLMs to parse and respond appropriately using the provided prompts.

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

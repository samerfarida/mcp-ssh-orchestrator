# 11. Observability & Audit

**Purpose:** Comprehensive guide for monitoring, logging, and auditing MCP SSH Orchestrator operations for security and compliance.

## Overview

MCP SSH Orchestrator provides observability through structured JSON logging to stderr. All audit logs are written to stderr while MCP protocol responses use stdout, providing clean separation for log aggregation and analysis.

## Logging Architecture

### Log Output Destination

### Log Separation

- **stderr**: All audit, policy decision, and progress logs (structured JSON)
- **stdout**: MCP protocol responses (JSON-RPC 2.0)

This separation allows Docker to capture audit logs separately from MCP responses.

### MCP Context Logging (Client-Facing)

In addition to stderr JSON logs, sync tools now publish lightweight status messages through the MCP `Context` object whenever the client supports it (Cursor, Claude Desktop, MCP Inspector, etc.). Highlights:

- `ssh_run`, `ssh_run_on_tag`, `ssh_reload_config`, `ssh_cancel`, `ssh_get_*`, and `ssh_cancel_async_task` report `ctx.debug` / `ctx.info` messages for task creation, completion, cancellation, and errors.
- Logging is non-blocking: `_ctx_log()` detects the active event loop and schedules `ctx.*` calls via `loop.create_task(...)`. If no loop/context is available the server simply skips emission (avoiding RuntimeErrors).
- Payloads are sanitized JSON (alias, task_id, command hash, exit_code) — never raw commands or secrets.
- View these messages directly in MCP Inspector (Console tab) or any client that surfaces MCP context events. They complement the canonical stderr logs without replacing them.

Use context logs for quick human feedback inside LLM tooling, while shipping structured JSON from stderr into your SIEM/observability stack.

### Audit Log Types

MCP SSH Orchestrator emits five types of structured JSON logs to stderr:

- 1. **Policy Decision Log** - Before every command execution
- 1. **Audit Log** - After command execution completes
- 1. **Progress Log** - During long-running commands (every 0.5s)
- 1. **Security Audit Log** - Security-relevant events (path traversal, invalid access, etc.)
- 1. **Error/Trace Log** - On exceptions or function completion

### 1. Policy Decision Log

**When:** Emitted before command execution to record policy evaluation.

### Example

{
  "type": "policy_decision",
  "ts": 1761489054.1433952,
    "alias": "web1",
  "hash": "7063dece7ccc",
  "allowed": true
}

```bash

### Fields:

- `type`: Always `"policy_decision"`
- `ts`: Unix timestamp (seconds since epoch)
- `alias`: Host alias from servers.yml
- `hash`: SHA256 hash of the command
- `allowed`: Boolean indicating policy decision

### Denied Command Example:

{
  "type": "policy_decision",
  "ts": 1761489054.1433952,
    "alias": "web1",
  "hash": "5c7923bd67b0",
  "allowed": false
}
```

### 2. Audit Log

**When:** Emitted after command execution (success or failure).

### Example

{
  "type": "audit",
  "ts": 1761489054.143448,
    "alias": "web1",
  "hash": "7063dece7ccc",
  "exit_code": 0,
  "duration_ms": 150,
  "bytes_out": 25,
  "bytes_err": 0,
  "cancelled": false,
  "timeout": false,
  "target_ip": "10.0.0.11"
}

```bash

### Fields:

- `type`: Always `"audit"`
- `ts`: Unix timestamp (seconds since epoch)
- `alias`: Host alias from servers.yml
- `hash`: SHA256 hash of the command
- `exit_code`: Process exit code (0-255)
- `duration_ms`: Execution time in milliseconds
- `bytes_out`: Bytes of stdout output captured
- `bytes_err`: Bytes of stderr output captured
- `cancelled`: Boolean - was task cancelled?
- `timeout`: Boolean - did task hit timeout limit?
- `target_ip`: Actual IP address of SSH server

### 4. Security Audit Log

**When:** Emitted when security-relevant events are detected (path traversal attempts, invalid file access, oversized files, rate limit violations, etc.).

**Purpose:** Comprehensive audit trail for security monitoring and incident response.

### Example:

{
  "level": "error",
  "kind": "security_audit",
  "type": "security_event",
  "event_type": "path_traversal_attempt",
  "ts": 1762112167.394149,
  "timestamp": "2025-11-02T14:36:07-0500",
  "attempted_path": "../etc/passwd",
  "resolved_path": "/app/secrets/../etc/passwd",
  "reason": "path_outside_allowed_directory",
  "base_dir": "/app/secrets"
}
```

### Fields

- `level`: Always `"error"` for security events
- `kind`: Always `"security_audit"`
- `type`: Always `"security_event"`
- `event_type`: Type of security event (see Event Types below)
- `ts`: Unix timestamp (seconds since epoch, float)
- `timestamp`: ISO 8601 formatted timestamp (human-readable)
- `attempted_path`: Original path/input that triggered the security event (optional)
- `resolved_path`: Resolved/absolute path after normalization (optional)
- `reason`: Human-readable reason for the security event (optional)
- `additional_data`: Event-specific context (field names, sizes, limits, etc.) (optional)

### Security Event Types

1. **`path_traversal_attempt`**: Path traversal detected in secret names or key paths
   - Includes: `attempted_path`, `resolved_path`, `reason`, `base_dir`
   - Example reasons: `"path_outside_allowed_directory"`, `"contains_traversal_pattern"`, `"absolute_path_rejected"`

1. **`file_validation_failed`**: File path validation failure
   - Includes: `attempted_path`, `resolved_path`, `reason`
   - Example reasons: `"path_is_directory"`, `"path_is_symlink"`, `"path_not_regular_file"`, `"path_outside_allowed_directory"`

1. **`file_size_limit_exceeded`**: YAML file exceeds size limit
   - Includes: `attempted_path`, `resolved_path`, `file_size`, `max_size`

1. **`input_length_limit_exceeded`**: Input string exceeds length limit
   - Includes: `attempted_path`, `field`, `length`, `max_length`
   - Example fields: `"secret_name"`, `"key_path"`

1. **`invalid_secret_name`**: Secret name contains invalid characters
   - Includes: `attempted_path`, `reason`

1. **`dns_rate_limit_exceeded`**: DNS resolution rate limit exceeded
   - Includes: `hostname`, `max_per_second`

1. **`command_bypass_attempt`**: Command denial bypass attempt detected
   - Includes: `original_command`, `normalized_command`, `blocked_pattern`

### Log Collection Example

# Filter security audit events

docker logs -f mcp-ssh-orchestrator 2>&1 | \
  jq -r 'select(.kind == "security_audit") | @json'

# Alert on path traversal attempts

docker logs -f mcp-ssh-orchestrator 2>&1 | \
  jq -r 'select(.event_type == "path_traversal_attempt") | "ALERT: \(.timestamp) - \(.reason) - \(.attempted_path)"'

```text

### Security Monitoring:

- Alert on any `path_traversal_attempt` events
- Monitor `file_validation_failed` for patterns
- Track `input_length_limit_exceeded` for potential DoS attempts
- Review `command_bypass_attempt` for policy evasion

### 3. Progress Log

**When:** Emitted every 0.5 seconds during command execution (while reading output).

### Example:

{
  "type": "progress",
  "ts": 1761489054.143455,
  "task_id": "task_abc123",
  "phase": "running",
  "bytes_read": 1024,
  "elapsed_ms": 500
}
```

### Fields

- `type`: Always `"progress"`
- `ts`: Unix timestamp
- `task_id`: Unique task identifier
- `phase`: Execution phase:
  - `"connecting"`: Establishing SSH connection
  - `"connected"`: SSH connection established
  - `"running"`: Command executing (logged every 0.5s)
- `bytes_read`: Total bytes read (stdout + stderr)
- `elapsed_ms`: Elapsed time in milliseconds

### Complete Progress Sequence

{"type": "progress", "ts": 1761489054.200, "task_id": "task_123", "phase": "connecting", "bytes_read": 0, "elapsed_ms": 50}
{"type": "progress", "ts": 1761489054.450, "task_id": "task_123", "phase": "connected", "bytes_read": 0, "elapsed_ms": 250}
{"type": "progress", "ts": 1761489054.700, "task_id": "task_123", "phase": "running", "bytes_read": 0, "elapsed_ms": 500}
{"type": "progress", "ts": 1761489055.000, "task_id": "task_123", "phase": "running", "bytes_read": 512, "elapsed_ms": 800}

```json

### 4. Error/Trace Logs

**When:** Exceptions occur or operations complete (trace).

### Error Example:

{
  "level": "error",
  "msg": "run_exception",
  "error": "Connection failed"
}
```

### Trace Example

{
  "type": "trace",
  "op": "run_done",
  "elapsed_ms": 123
}

```text

### Fields:

- `level`: "error" | "warn"
- `msg`: Error message identifier
- `error`: Error details
- `type`: "trace"
- `op`: Operation name
- `elapsed_ms`: Elapsed time (milliseconds)

## Capturing and Analyzing Logs

### Docker Logs

All logs are written to stderr by the Docker container and can be captured using standard Docker logging.

### Basic Commands:

# View all logs (stdout + stderr mixed)
docker logs mcp-ssh-container

# Follow logs in real-time
docker logs -f mcp-ssh-container

# View only last 100 lines
docker logs --tail 100 mcp-ssh-container

# Extract only JSON audit logs
docker logs mcp-ssh-container 2>&1 | grep '^{' | jq '.'
```

### Docker Compose

# Follow logs

docker-compose logs -f mcp-ssh

# View specific service

docker-compose logs mcp-ssh

```bash

### Log Parsing and Analysis

### Extract Specific Log Types:

# Extract only policy decision logs
docker logs mcp-ssh-container 2>&1 | grep '{"type":"policy_decision"' | jq '.'

# Extract only audit logs
docker logs mcp-ssh-container 2>&1 | grep '{"type":"audit"' | jq '.'

# Extract only progress logs
docker logs mcp-ssh-container 2>&1 | grep '{"type":"progress"' | jq '.'
```

### Count Policy Violations

# Count denied commands

docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "policy_decision" and .allowed == false)' | \
  jq -r '.alias' | sort | uniq -c

# Count policy violations per host

docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "policy_decision" and .allowed == false) | .alias' | \
  sort | uniq -c

```bash

### Analyze Execution Metrics:

# Calculate average execution time
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit") | .duration_ms' | \
  awk '{sum+=$1; count++} END {print "Average: " sum/count "ms"}'

# Find slowest commands
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit") | [.duration_ms, .alias]' | \
  sort -rn | head -10

# Count commands per host
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit") | .alias' | \
  sort | uniq -c
```

### Security Analysis

# List all target IPs accessed

docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit") | .target_ip' | \
  sort | uniq

# Find timeout occurrences

docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit" and .timeout == true)'

# Find cancelled tasks

docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit" and .cancelled == true)'

```bash

### Complete Audit Trail for a Host:

# Show all operations for a specific host
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.alias == "Proxmox Prod 01")'
```

## Log Format Details

### Timestamp Format

All timestamps use Unix epoch time (seconds since January 1, 1970) as floating-point values with microsecond precision:

{
  "ts": 1761489054.143455
}

```text

Convert to readable format:

date -r 1761489054.143455
```

### Command Hashing

Commands are hashed using SHA256 before logging for privacy and consistency:

echo -n "hostname" | sha256sum

# Output: 7063dece7ccc

```json

### JSON Lines Format

Each log entry is a complete JSON object on a single line. This format:

- Is easy to parse with tools like `jq`
- Can be streamed efficiently
- Works well with log aggregators (ELK, Splunk, etc.)
- Maintains structural integrity

### Example of multi-line output:

{"type": "policy_decision", "ts": 1761489054.1433952, "alias": "web1", "hash": "abc123", "allowed": true}
{"type": "progress", "ts": 1761489054.200, "task_id": "task_123", "phase": "connecting", "bytes_read": 0, "elapsed_ms": 50}
{"type": "audit", "ts": 1761489054.650, "alias": "web1", "hash": "abc123", "exit_code": 0, "duration_ms": 150, "bytes_out": 25, "bytes_err": 0, "cancelled": false, "timeout": false, "target_ip": "10.0.0.11"}
```

## Security Reporting for Compliance

*Note: This tool provides audit logs and security features that can assist with compliance reporting. Actual certification and controls beyond logging are the responsibility of the deploying organization.*

### Access Control Reporting

# Total commands executed

docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit") | length'

# Allowed vs denied command ratio

docker logs mcp-ssh-container 2>&1 | \
  jq -r 'select(.type == "policy_decision") | .allowed' | \
  awk 'BEGIN{allow=0;deny=0} {if($1=="true") allow++; else deny++} END {print "Allowed:", allow, "Denied:", deny}'

```bash

### Audit Trail Reporting

# Complete audit trail with timestamps
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit") | {
    timestamp: (.ts | todate),
    alias,
    exit_code,
    duration_ms,
    target_ip
  }'

# Failed command executions
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit" and .exit_code != 0)'
```

### Network Security Reporting

# List all target IPs accessed

docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit") | .target_ip' | \
  sort | uniq -c

# Network policy violations (IP not allowed)

docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit" and .target_ip != null and .exit_code == 0) | .target_ip'

```dockerfile

## Best Practices

### Log Retention

### Docker Log Drivers:

Use Docker's built-in log drivers for retention:

docker run --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  mcp-ssh-orchestrator:latest
```

### docker-compose.yml

services:
  mcp-ssh:
    image: ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

```dockerfile

### Log Aggregation

Forward logs to external systems:

# Forward to a syslog server
docker run --log-driver syslog \
  --log-opt syslog-address=udp://logserver:514 \
  mcp-ssh-orchestrator:latest

# Forward to journald
docker run --log-driver journald \
  mcp-ssh-orchestrator:latest
```

### Real Example Sequence

Here's what gets logged for a simple `hostname` command on a Proxmox host:

{"type": "policy_decision", "ts": 1761489054.1433952, "alias": "Proxmox Prod 01", "hash": "abc123", "allowed": true}
{"type": "progress", "ts": 1761489054.2000000, "task_id": "task_xyz", "phase": "connecting", "bytes_read": 0, "elapsed_ms": 50}
{"type": "progress", "ts": 1761489054.4500000, "task_id": "task_xyz", "phase": "connected", "bytes_read": 0, "elapsed_ms": 250}
{"type": "progress", "ts": 1761489054.7000000, "task_id": "task_xyz", "phase": "running", "bytes_read": 0, "elapsed_ms": 500}
{"type": "audit", "ts": 1761489054.6500000, "alias": "Proxmox Prod 01", "hash": "abc123", "exit_code": 0, "duration_ms": 650, "bytes_out": 25, "bytes_err": 0, "cancelled": false, "timeout": false, "target_ip": "10.0.0.50"}
{"type": "trace", "op": "run_done", "elapsed_ms": 700}

```bash

This sequence shows:

1. **Policy decision** (command allowed)
2. **Progress logs** during connection and execution
3. **Final audit log** with execution results
4. **Trace log** marking completion

## Important Notes

1. **All logs go to stderr** - This is intentional to separate audit logs from MCP protocol responses
2. **JSON Lines format** - Each log is a single JSON object on one line
3. **Timestamps are Unix floats** - `ts` field is seconds since epoch with microsecond precision
4. **Command hashes** - Commands are hashed (SHA256) for privacy and consistency
5. **Progress logs emitted every 0.5 seconds** during long-running commands
6. **No sensitive data** - Command output goes to stdout for LLM, not in audit logs
7. **Logs are append-only** - Written to stderr stream for audit integrity

## Security Implications

- Audit logs contain **host aliases** and **command hashes** (not full commands)
- IP addresses are logged for network compliance and tracking
- No sensitive command output is in audit logs (output goes to stdout for the LLM)
- Logs are append-only (written to stderr stream)
- Commands are SHA256-hashed for privacy and consistency
- Can assist with compliance reporting by providing structured audit logs

## Next Steps

- **[Security Model](05-Security-Model)** - Understanding the security architecture
- **[Configuration](06-Configuration)** - Setting up hosts, credentials, and policies
- **[Deployment](09-Deployment)** - Production deployment with logging
- **[FAQ](14-FAQ)** - Common observability questions

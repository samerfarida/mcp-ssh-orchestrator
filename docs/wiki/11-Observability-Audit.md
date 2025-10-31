# 11. Observability & Audit

**Purpose:** Comprehensive guide for monitoring, logging, and auditing MCP SSH Orchestrator operations for security and compliance.

## Overview

MCP SSH Orchestrator provides observability through structured JSON logging to stderr. All audit logs are written to stderr while MCP protocol responses use stdout, providing clean separation for log aggregation and analysis.

## Logging Architecture

### Log Output Destination

**Log Separation:**

- **stderr**: All audit, policy decision, and progress logs (structured JSON)
- **stdout**: MCP protocol responses (JSON-RPC 2.0)

This separation allows Docker to capture audit logs separately from MCP responses.

### Audit Log Types

MCP SSH Orchestrator emits four types of structured JSON logs to stderr:

- 1. **Policy Decision Log** - Before every command execution
- 2. **Audit Log** - After command execution completes  
- 3. **Progress Log** - During long-running commands (every 0.5s)
- 4. **Error/Trace Log** - On exceptions or function completion

### 1. Policy Decision Log

**When:** Emitted before command execution to record policy evaluation.

**Example:**
```json
{
  "type": "policy_decision",
  "ts": 1761489054.1433952,
    "alias": "web1",
  "hash": "7063dece7ccc",
  "allowed": true
}
```

**Fields:**

- `type`: Always `"policy_decision"`
- `ts`: Unix timestamp (seconds since epoch)
- `alias`: Host alias from servers.yml
- `hash`: SHA256 hash of the command
- `allowed`: Boolean indicating policy decision

**Denied Command Example:**
```json
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

**Example:**
```json
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
```

**Fields:**

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

### 3. Progress Log

**When:** Emitted every 0.5 seconds during command execution (while reading output).

**Example:**
```json
{
  "type": "progress",
  "ts": 1761489054.143455,
  "task_id": "task_abc123",
  "phase": "running",
  "bytes_read": 1024,
  "elapsed_ms": 500
}
```

**Fields:**

- `type`: Always `"progress"`
- `ts`: Unix timestamp
- `task_id`: Unique task identifier
- `phase`: Execution phase:
  - `"connecting"`: Establishing SSH connection
  - `"connected"`: SSH connection established
  - `"running"`: Command executing (logged every 0.5s)
- `bytes_read`: Total bytes read (stdout + stderr)
- `elapsed_ms`: Elapsed time in milliseconds

**Complete Progress Sequence:**
```json
{"type": "progress", "ts": 1761489054.200, "task_id": "task_123", "phase": "connecting", "bytes_read": 0, "elapsed_ms": 50}
{"type": "progress", "ts": 1761489054.450, "task_id": "task_123", "phase": "connected", "bytes_read": 0, "elapsed_ms": 250}
{"type": "progress", "ts": 1761489054.700, "task_id": "task_123", "phase": "running", "bytes_read": 0, "elapsed_ms": 500}
{"type": "progress", "ts": 1761489055.000, "task_id": "task_123", "phase": "running", "bytes_read": 512, "elapsed_ms": 800}
```

### 4. Error/Trace Logs

**When:** Exceptions occur or operations complete (trace).

**Error Example:**
```json
{
  "level": "error",
  "msg": "run_exception",
  "error": "Connection failed"
}
```

**Trace Example:**
```json
{
  "type": "trace",
  "op": "run_done",
  "elapsed_ms": 123
}
```

**Fields:**

- `level`: "error" | "warn"
- `msg`: Error message identifier
- `error`: Error details
- `type`: "trace"
- `op`: Operation name
- `elapsed_ms`: Elapsed time (milliseconds)

## Capturing and Analyzing Logs

### Docker Logs

All logs are written to stderr by the Docker container and can be captured using standard Docker logging.

**Basic Commands:**

```bash
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

```bash
# Follow logs
docker-compose logs -f mcp-ssh

# View specific service
docker-compose logs mcp-ssh
```

### Log Parsing and Analysis

**Extract Specific Log Types:**

```bash
# Extract only policy decision logs
docker logs mcp-ssh-container 2>&1 | grep '{"type":"policy_decision"' | jq '.'

# Extract only audit logs
docker logs mcp-ssh-container 2>&1 | grep '{"type":"audit"' | jq '.'

# Extract only progress logs
docker logs mcp-ssh-container 2>&1 | grep '{"type":"progress"' | jq '.'
```

**Count Policy Violations:**

```bash
# Count denied commands
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "policy_decision" and .allowed == false)' | \
  jq -r '.alias' | sort | uniq -c

# Count policy violations per host
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "policy_decision" and .allowed == false) | .alias' | \
  sort | uniq -c
```

**Analyze Execution Metrics:**

```bash
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

**Security Analysis:**

```bash
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
```

**Complete Audit Trail for a Host:**

```bash
# Show all operations for a specific host
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.alias == "Proxmox Prod 01")'
```

## Log Format Details

### Timestamp Format

All timestamps use Unix epoch time (seconds since January 1, 1970) as floating-point values with microsecond precision:

```json
{
  "ts": 1761489054.143455
}
```

Convert to readable format:
```bash
date -r 1761489054.143455
```

### Command Hashing

Commands are hashed using SHA256 before logging for privacy and consistency:

```bash
echo -n "hostname" | sha256sum
# Output: 7063dece7ccc...
```

### JSON Lines Format

Each log entry is a complete JSON object on a single line. This format:
- Is easy to parse with tools like `jq`
- Can be streamed efficiently
- Works well with log aggregators (ELK, Splunk, etc.)
- Maintains structural integrity

**Example of multi-line output:**
```json
{"type": "policy_decision", "ts": 1761489054.1433952, "alias": "web1", "hash": "abc123", "allowed": true}
{"type": "progress", "ts": 1761489054.200, "task_id": "task_123", "phase": "connecting", "bytes_read": 0, "elapsed_ms": 50}
{"type": "audit", "ts": 1761489054.650, "alias": "web1", "hash": "abc123", "exit_code": 0, "duration_ms": 150, "bytes_out": 25, "bytes_err": 0, "cancelled": false, "timeout": false, "target_ip": "10.0.0.11"}
```

## Security Reporting for Compliance

*Note: This tool provides audit logs and security features that can assist with compliance reporting. Actual certification and controls beyond logging are the responsibility of the deploying organization.*

### Access Control Reporting

```bash
# Total commands executed
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit") | length'

# Allowed vs denied command ratio
docker logs mcp-ssh-container 2>&1 | \
  jq -r 'select(.type == "policy_decision") | .allowed' | \
  awk 'BEGIN{allow=0;deny=0} {if($1=="true") allow++; else deny++} END {print "Allowed:", allow, "Denied:", deny}'
```

### Audit Trail Reporting

```bash
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

```bash
# List all target IPs accessed
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit") | .target_ip' | \
  sort | uniq -c

# Network policy violations (IP not allowed)
docker logs mcp-ssh-container 2>&1 | \
  jq 'select(.type == "audit" and .target_ip != null and .exit_code == 0) | .target_ip'
```

## Best Practices

### Log Retention

**Docker Log Drivers:**

Use Docker's built-in log drivers for retention:

```bash
docker run --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  mcp-ssh-orchestrator:latest
```

**docker-compose.yml:**
```yaml
services:
  mcp-ssh:
    image: ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Log Aggregation

Forward logs to external systems:

```bash
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

```json
{"type": "policy_decision", "ts": 1761489054.1433952, "alias": "Proxmox Prod 01", "hash": "abc123", "allowed": true}
{"type": "progress", "ts": 1761489054.2000000, "task_id": "task_xyz", "phase": "connecting", "bytes_read": 0, "elapsed_ms": 50}
{"type": "progress", "ts": 1761489054.4500000, "task_id": "task_xyz", "phase": "connected", "bytes_read": 0, "elapsed_ms": 250}
{"type": "progress", "ts": 1761489054.7000000, "task_id": "task_xyz", "phase": "running", "bytes_read": 0, "elapsed_ms": 500}
{"type": "audit", "ts": 1761489054.6500000, "alias": "Proxmox Prod 01", "hash": "abc123", "exit_code": 0, "duration_ms": 650, "bytes_out": 25, "bytes_err": 0, "cancelled": false, "timeout": false, "target_ip": "10.0.0.50"}
{"type": "trace", "op": "run_done", "elapsed_ms": 700}
```

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

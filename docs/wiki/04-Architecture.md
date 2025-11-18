# 4. Architecture

**Purpose:** Explain the system design, component relationships, and data flow of mcp-ssh-orchestrator.

## System Overview

mcp-ssh-orchestrator is a **stateless, policy-driven SSH command executor** designed as a Model Context Protocol (MCP) server. It provides secure, auditable access to SSH infrastructure through a standardized interface.

## High-Level Architecture

```mermaid
graph TB
    subgraph "AI Client Environment"
        LLM[LLM/AI Agent]
        MCP_CLIENT[MCP Client]
    end

    subgraph "Transport Layer"
        STDIO[stdio Transport]
    end

    subgraph "mcp-ssh-orchestrator Container"
        MCP_SERVER[MCP Server]
        POLICY_ENGINE[Policy Engine]
        SSH_CLIENT[SSH Client]
        AUDIT_LOGGER[Audit Logger]
    end

    subgraph "Configuration Layer"
        SERVERS_CONFIG[servers.yml]
        CREDS_CONFIG[credentials.yml]
        POLICY_CONFIG[policy.yml]
        SSH_KEYS[SSH Keys]
    end

    subgraph "Target Infrastructure"
        WEB_SERVERS[Web Servers]
        DB_SERVERS[Database Servers]
        MON_SERVERS[Monitoring Servers]
    end

    LLM --> MCP_CLIENT
    MCP_CLIENT --> STDIO
    STDIO --> MCP_SERVER

    MCP_SERVER --> POLICY_ENGINE
    POLICY_ENGINE --> SSH_CLIENT
    SSH_CLIENT --> WEB_SERVERS
    SSH_CLIENT --> DB_SERVERS
    SSH_CLIENT --> MON_SERVERS

    MCP_SERVER --> AUDIT_LOGGER

    POLICY_ENGINE --> SERVERS_CONFIG
    POLICY_ENGINE --> CREDS_CONFIG
    POLICY_ENGINE --> POLICY_CONFIG
    SSH_CLIENT --> SSH_KEYS
```

## Component Architecture

### Core Components

```mermaid
graph TB
    subgraph "mcp_ssh Package"
        MCP_SERVER[mcp_server.py]
        CONFIG[config.py]
        POLICY[policy.py]
        SSH_CLIENT[ssh_client.py]
        UTILITIES[tools/utilities.py]
    end

    subgraph "Configuration Files"
        SERVERS[servers.yml]
        CREDS[credentials.yml]
        POLICY_FILE[policy.yml]
    end

    subgraph "External Dependencies"
        PARAMIKO[paramiko - SSH]
        YAML[yaml - Config]
        JSON[json - Logging]
    end

    MCP_SERVER --> CONFIG
    MCP_SERVER --> POLICY
    MCP_SERVER --> SSH_CLIENT
    MCP_SERVER --> UTILITIES

    CONFIG --> SERVERS
    CONFIG --> CREDS
    POLICY --> POLICY_FILE

    SSH_CLIENT --> PARAMIKO
    CONFIG --> YAML
    UTILITIES --> JSON
```

## Data Flow Architecture

### Command Execution Flow

```mermaid
sequenceDiagram
    participant LLM as LLM Client
    participant MCP as MCP Server
    participant POLICY as Policy Engine
    participant SSH as SSH Client
    participant TARGET as Target Host
    participant AUDIT as Audit Logger

    LLM->>MCP: {"name": "ssh_run", "arguments": {"alias": "web1", "command": "uptime"}}

    MCP->>POLICY: Validate request
    POLICY->>POLICY: Check policy rules
    POLICY->>POLICY: Verify network access
    POLICY->>POLICY: Check command patterns

    alt Policy allows
        POLICY-->>MCP: Allow
        MCP->>SSH: Execute command
        SSH->>TARGET: SSH connection
        TARGET-->>SSH: Command output
        SSH-->>MCP: Result
        MCP->>AUDIT: Log operation
        MCP-->>LLM: Success response
    else Policy denies
        POLICY-->>MCP: Deny
        MCP->>AUDIT: Log denial
        MCP-->>LLM: Error response
    end
```

### Policy Evaluation Flow

```mermaid
flowchart TD
    START[Command Request] --> DENY_CHECK{Check deny_substrings}

    DENY_CHECK -->|Contains blocked| DENY[Deny Request]
    DENY_CHECK -->|Safe| NETWORK_CHECK{Check network access}

    NETWORK_CHECK -->|IP blocked| DENY
    NETWORK_CHECK -->|IP allowed| RULE_CHECK{Check policy rules}

    RULE_CHECK -->|No matching rule| DENY
    RULE_CHECK -->|Rule found| ACTION_CHECK{Check rule action}

    ACTION_CHECK -->|deny| DENY
    ACTION_CHECK -->|allow| LIMIT_CHECK{Check execution limits}

    LIMIT_CHECK -->|Within limits| ALLOW[Allow Request]
    LIMIT_CHECK -->|Exceeds limits| DENY

    DENY --> AUDIT_LOG[Log Denial]
    ALLOW --> AUDIT_LOG2[Log Allowance]

    AUDIT_LOG --> END[End]
    AUDIT_LOG2 --> END
```

## Component Details

### 1. MCP Server (`mcp_server.py`)

**Purpose:** Main entry point and MCP protocol implementation.

**Responsibilities:**

- Handle MCP protocol communication
- Route tool calls to appropriate handlers
- Manage request/response lifecycle
- Coordinate with other components

**Key Functions:**

```python
@mcp.tool()
def ssh_run(alias: str = "", command: str = "") -> str:
    """Execute a command on a host."""

@mcp.tool()
def ssh_plan(alias: str = "", command: str = "") -> str:
    """Dry-run a command (shows policy decision)."""
```

### 2. Configuration Manager (`config.py`)

**Purpose:** Load and validate configuration files.

**Responsibilities:**

- Parse YAML configuration files
- Validate configuration syntax
- Provide configuration to other components
- Handle configuration reloading

**Configuration Sources:**

- `servers.yml` - Host inventory
- `credentials.yml` - SSH authentication
- `policy.yml` - Security policies

### 3. Policy Engine (`policy.py`)

**Purpose:** Enforce security policies and access controls.

**Responsibilities:**

- Evaluate policy rules
- Check network access controls
- Validate command patterns
- Apply execution limits
- Generate policy decisions

**Policy Components:**

- **Rule Engine:** Pattern matching with glob support
- **Network Controls:** IP allowlists/blocklists
- **Execution Limits:** Timeouts, output size caps
- **Override System:** Per-host and per-tag customization

### 4. SSH Client (`ssh_client.py`)

**Purpose:** Execute SSH commands on target hosts.

**Responsibilities:**

- Establish SSH connections
- Execute commands remotely
- Handle SSH authentication
- Manage connection lifecycle
- Stream command output

**Security Features:**

- Host key verification
- Connection timeout management
- Output size limiting
- Graceful error handling

### 5. Audit Logger (`tools/utilities.py`)

**Purpose:** Generate comprehensive audit logs.

**Responsibilities:**

- Log all operations to stderr
- Generate structured JSON logs
- Include security-relevant metadata
- Support compliance requirements

**Log Format:**

```json
{
  "type": "audit",
  "ts": 1729512345.67,
  "alias": "prod-web-1",
  "hash": "a1b2c3d4e5f6",
  "exit_code": 0,
  "duration_ms": 123,
  "target_ip": "10.0.0.11"
}
```

## Deployment Architecture

### Container Architecture

```mermaid
graph TB
    subgraph "Docker Container"
        subgraph "Application Layer"
            MCP_SERVER[MCP Server Process]
        end

        subgraph "Configuration Layer"
            CONFIG_DIR["/app/config"]
            KEYS_DIR["/app/keys"]
            SECRETS_DIR["/app/secrets"]
        end

        subgraph "System Layer"
            NON_ROOT[Non-root User<br/>UID 10001]
            RESOURCE_LIMITS[CPU/Memory Limits]
        end
    end

    subgraph "Host System"
        VOLUMES[Volume Mounts]
        NETWORK[Network Access]
    end

    VOLUMES --> CONFIG_DIR
    VOLUMES --> KEYS_DIR
    VOLUMES --> SECRETS_DIR

    NETWORK --> MCP_SERVER
```

### Multi-Environment Architecture

```mermaid
graph TB
    subgraph "Development Environment"
        DEV_CLIENT[Claude Desktop]
        DEV_CONTAINER[mcp-ssh-orchestrator]
        DEV_HOSTS[Dev Servers]
    end

    subgraph "Staging Environment"
        STG_CLIENT[Claude Desktop]
        STG_CONTAINER[mcp-ssh-orchestrator]
        STG_HOSTS[Staging Servers]
    end

    subgraph "Production Environment"
        PROD_CLIENT[Claude Desktop]
        PROD_CONTAINER[mcp-ssh-orchestrator]
        PROD_HOSTS[Production Servers]
    end

    DEV_CLIENT --> DEV_CONTAINER
    DEV_CONTAINER --> DEV_HOSTS

    STG_CLIENT --> STG_CONTAINER
    STG_CONTAINER --> STG_HOSTS

    PROD_CLIENT --> PROD_CONTAINER
    PROD_CONTAINER --> PROD_HOSTS
```

## Security Architecture

### Defense-in-Depth Layers

```mermaid
graph TB
    subgraph "Layer 1: Transport Security"
        STDIO_SEC[stdio Transport]
        CONTAINER_SEC[Container Isolation]
    end

    subgraph "Layer 2: Network Security"
        IP_ALLOW[IP Allowlists]
        HOST_KEY[Host Key Verification]
        DNS_VERIFY[DNS Resolution]
    end

    subgraph "Layer 3: Policy Security"
        DENY_DEFAULT[Deny-by-Default]
        PATTERN_MATCH[Pattern Matching]
        EXEC_LIMITS[Execution Limits]
    end

    subgraph "Layer 4: Application Security"
        NON_ROOT[Non-root Execution]
        RESOURCE_LIMITS[Resource Limits]
        AUDIT_LOG[Audit Logging]
    end

    STDIO_SEC --> IP_ALLOW
    CONTAINER_SEC --> HOST_KEY
    IP_ALLOW --> DENY_DEFAULT
    HOST_KEY --> PATTERN_MATCH
    DENY_DEFAULT --> NON_ROOT
    PATTERN_MATCH --> RESOURCE_LIMITS
    EXEC_LIMITS --> AUDIT_LOG
```

## Resource Management

### Current Architecture

MCP SSH Orchestrator is designed for single-container deployment per MCP client. Each client (Claude Desktop, Cursor, etc.) connects to its own orchestrator instance.

```mermaid
graph TB
    subgraph "MCP Client (Claude Desktop / Cursor)"
        CLIENT[MCP Client]
    end

    subgraph "MCP SSH Orchestrator Instance"
        INSTANCE[mcp-ssh-orchestrator<br/>Container]
        CONFIG[Configuration<br/>servers.yml, policy.yml]
        KEYS[SSH Keys<br/>known_hosts]
    end

    subgraph "Target Infrastructure"
        HOSTS[SSH Hosts<br/>Server Fleet]
    end

    CLIENT --> INSTANCE
    INSTANCE --> CONFIG
    INSTANCE --> KEYS
    INSTANCE --> HOSTS
```

**Design Principles:**

- One container per MCP client
- Stateless design (no shared state between instances)
- Resource limits: 512MB memory, 1 CPU
- No load balancer required (scaling at client level)

## Monitoring Architecture

### Built-in Observability

MCP SSH Orchestrator provides structured JSON logging to stderr for audit and compliance.

```mermaid
graph TB
    subgraph "mcp-ssh-orchestrator"
        AUDIT_LOG[Audit Logger<br/>JSON to stderr]
        POLICY_LOG[Policy Decision Logs]
        PROGRESS_LOG[Progress Logs]
        SSH_PING[ssh_ping Tool]
    end

    subgraph "External Integration Options"
        DOCKER_LOGS[Docker Logs]
        LOG_ROTATION[Log Rotation]
        SIEM[SIEM Integration]
    end

    AUDIT_LOG --> DOCKER_LOGS
    POLICY_LOG --> DOCKER_LOGS
    PROGRESS_LOG --> DOCKER_LOGS
    SSH_PING --> DOCKER_LOGS

    DOCKER_LOGS --> LOG_ROTATION
    DOCKER_LOGS --> SIEM
```

**Built-in Features:**

- **Audit Logger**: Emits structured JSON logs to stderr for all operations
- **Health Check**: `ssh_ping` tool for basic health verification
- **Log Types**: Policy decisions, audit trails, progress updates, error logs

**External Integration:**

- Logs can be captured via Docker logging drivers
- JSON logs can be parsed and forwarded to SIEM tools
- No built-in metrics collection or alerting (use external tools)

See [Observability & Audit](11-Observability-Audit.md) for detailed information on log types and analysis.

## Integration Architecture

### MCP Client Integration

```mermaid
graph TB
    subgraph "Claude Desktop"
        CLAUDE_UI[Claude UI]
        MCP_CLIENT[MCP Client]
    end

    subgraph "Docker Desktop"
        DOCKER_UI[Docker Desktop UI]
        MCP_TOOLKIT[MCP Toolkit]
    end

    subgraph "Custom Applications"
        CUSTOM_APP[Custom App]
        MCP_SDK[MCP SDK]
    end

    subgraph "mcp-ssh-orchestrator"
        MCP_SERVER[MCP Server]
    end

    CLAUDE_UI --> MCP_CLIENT
    DOCKER_UI --> MCP_TOOLKIT
    CUSTOM_APP --> MCP_SDK

    MCP_CLIENT --> MCP_SERVER
    MCP_TOOLKIT --> MCP_SERVER
    MCP_SDK --> MCP_SERVER
```

## Performance Architecture

### Resource Management

MCP SSH Orchestrator is designed as a lightweight, single-container MCP server optimized for efficient command execution.

```mermaid
graph TB
    subgraph "Container Configuration"
        CPU_LIMIT[CPU Limit<br/>1 core recommended]
        MEMORY_LIMIT[Memory Limit<br/>512MB recommended]
        ASYNC[Async Task Support]
    end

    subgraph "Execution Model"
        SYNC[Sync Commands]
        ASYNC_TASKS[Async Background Tasks]
        CANCELLATION[Task Cancellation]
    end

    subgraph "Resource Control"
        TIMEOUT[Command Timeouts]
        OUTPUT_LIMIT[Output Size Limits]
        CONCURRENT[Concurrent Executions]
    end

    CPU_LIMIT --> SYNC
    MEMORY_LIMIT --> ASYNC_TASKS
    ASYNC --> CANCELLATION

    TIMEOUT --> CONCURRENT
    OUTPUT_LIMIT --> CONCURRENT
```

**Configuration:**

- One container per MCP client (no shared state)
- Stateless design (no database or cache)
- Resource limits configurable via Docker
- Single-threaded execution model

**Features:**

- Synchronous and asynchronous command execution
- Task cancellation support
- Output size limiting
- Command timeouts

See [Deployment](09-Deployment.md) for recommended resource configurations.

## Next Steps

- **[Security Model](05-Security-Model)** - Detailed security architecture and controls
- **[Configuration](06-Configuration)** - Configuration system design and usage
- **[Deployment](09-Deployment)** - Production deployment architecture
- **[Observability & Audit](11-Observability-Audit)** - Monitoring and compliance architecture

# 3. Design Goals

**Purpose:** Define the core principles and philosophy that guide mcp-ssh-orchestrator's design decisions, ensuring security, usability, and maintainability.

## Core Philosophy

mcp-ssh-orchestrator is built on the principle that **AI agents should have safe, controlled access to infrastructure** without compromising security or operational integrity. Every design decision prioritizes security while maintaining usability for legitimate operations.

## Primary Design Goals

### 1. Security First

**Principle:** Security is not an afterthought—it's the foundation of every feature.

**Implementation:**

- **Deny-by-default** policy model
- **Defense-in-depth** security architecture
- **Containerized execution** with resource limits
- **Comprehensive audit logging** for all operations
- **Network segmentation** with IP allowlists

**Example:**

```yaml
# Default policy: deny everything
rules: []  # No rules = deny all

# Explicit allow rules only
rules:
  - action: "allow"
    aliases: ["prod-*"]
    commands: ["uptime*", "df -h*"]
```

### 2. Minimal Attack Surface

**Principle:** Reduce the potential for security vulnerabilities by minimizing exposed functionality.

**Implementation:**

- **Single-purpose design** (SSH command execution only)
- **Minimal dependencies** (Python standard library + SSH)
- **No persistent state** (stateless operation)
- **Read-only configuration** (no runtime modifications)
- **Non-root execution** (least privilege)

**Example:**

```dockerfile
# Minimal base image
FROM python:3.13-slim

# Non-root user
RUN useradd -u 10001 -m appuser
USER appuser

# Read-only filesystem
VOLUME ["/app/config:ro", "/app/keys:ro"]
```

### 3. Policy-Driven Control

**Principle:** All access decisions are governed by explicit, auditable policies.

**Implementation:**

- **YAML-based policy configuration**
- **Glob pattern matching** for flexible rules
- **Per-host and per-tag overrides**
- **Policy validation** before execution
- **Dry-run capability** (`ssh_plan`)

**Example:**

```yaml
# Environment-specific policies
rules:
  - action: "allow"
    tags: ["production"]
    commands: ["uptime*", "df -h*"]

  - action: "allow"
    tags: ["development"]
    commands: ["systemctl restart *", "docker ps*"]
```

### 4. Observability & Auditability

**Principle:** Every operation must be observable, auditable, and traceable.

**Implementation:**

- **JSON audit logs** to stderr
- **Structured logging** with timestamps
- **Command hashing** for integrity
- **Exit codes and durations** for monitoring
- **Target IP tracking** for network analysis

**Example:**

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

### 5. Container-Native Design

**Principle:** Designed from the ground up for containerized deployment.

**Implementation:**

- **Docker-first** deployment model
- **Health checks** for monitoring
- **Resource limits** (CPU, memory)
- **Non-root execution** for security
- **Secrets management** via Docker secrets

**Example:**

```yaml
# Docker Compose integration
services:
  mcp-ssh:
    image: ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
    volumes:
      - ./config:/app/config:ro
      - ./keys:/app/keys:ro
    healthcheck:
      test: ["CMD", "python", "-c", "import mcp_ssh"]
      interval: 30s
      timeout: 5s
      retries: 3
```

## Secondary Design Goals

### 6. Developer Experience

**Principle:** Make secure operations easy and intuitive.

**Implementation:**

- **Clear error messages** with actionable guidance
- **Comprehensive documentation** with examples
- **Easy configuration** with sensible defaults
- **Quick start guides** for common scenarios
- **Troubleshooting guides** for common issues

### 7. Operational Simplicity

**Principle:** Reduce operational complexity while maintaining security.

**Implementation:**

- **Single binary** deployment (Docker image)
- **Configuration-driven** behavior
- **No external dependencies** (databases, queues)
- **Graceful error handling** with proper exit codes
- **Hot reload** of configuration (`ssh_reload_config`)

### 8. Security & Audit Ready

**Principle:** Security features that can support compliance and audit requirements.

**Implementation:**

- **OWASP LLM07** mitigation (Insecure Plugin Design)
- **MITRE ATT&CK** aligned logging and monitoring
- **Complete audit trails** for all operations
- **Immutable logs** (append-only)
- **Policy-based access control** for security
- **Dangerous command blocking** for safety

**Note:** Audit logs can be integrated with your existing security tooling and SIEM systems for compliance monitoring.

## Design Constraints

### Security Constraints

1. **No Persistent State**
   - No databases or file storage
   - Configuration loaded at startup
   - Stateless operation for security

2. **No Network Egress**
   - No outbound connections (except SSH)
   - No external API calls
   - No telemetry or analytics

3. **No Code Execution**
   - No dynamic code loading
   - No plugin system
   - No script execution

### Operational Constraints

1. **Single Purpose**
   - SSH command execution only
   - No file transfer (scp/sftp)
   - No interactive sessions

2. **Resource Limits**
   - CPU and memory caps
   - Output size limits
   - Execution timeouts

3. **Network Restrictions**
   - IP allowlists only
   - No DNS resolution bypass
   - No proxy support

## Design Trade-offs

### Security vs. Usability

**Trade-off:** Strict security policies may limit legitimate operations.

**Resolution:**

- Provide comprehensive policy examples
- Enable dry-run testing (`ssh_plan`)
- Support per-environment policies
- Clear documentation of restrictions

### Performance vs. Security

**Trade-off:** Security checks add latency to command execution.

**Resolution:**

- Policy evaluation is fast (in-memory)
- SSH connection reuse where possible
- Minimal overhead logging
- Configurable timeouts

### Flexibility vs. Simplicity

**Trade-off:** More configuration options increase complexity.

**Resolution:**

- Sensible defaults for common scenarios
- Progressive disclosure of advanced features
- Clear examples for different use cases
- Validation of configuration syntax

## Implementation Principles

### 1. Fail Secure

**Principle:** When in doubt, deny access.

**Implementation:**

- Default policy is deny-all
- Invalid configurations fail closed
- Network errors prevent execution
- Timeouts terminate operations

### 2. Explicit Configuration

**Principle:** Nothing happens by accident.

**Implementation:**

- No implicit permissions
- Explicit allow rules required
- Clear policy documentation
- Validation of all inputs

### 3. Minimal Dependencies

**Principle:** Fewer dependencies = fewer vulnerabilities.

**Implementation:**

- Python standard library only
- SSH via paramiko (minimal)
- No external HTTP libraries
- No database dependencies

### 4. Immutable Configuration

**Principle:** Configuration changes require restart or explicit reload.

**Implementation:**

- No runtime configuration changes
- `ssh_reload_config` for updates
- Validation before reload
- Clear error messages for invalid configs

## Quality Attributes

### Security Attributes

- **Confidentiality:** Encrypted SSH transport, no credential storage
- **Integrity:** Command hashing and audit trails
- **Availability:** Health checks, graceful degradation, resource limits

### Operational Attributes

- **Reliability:** Graceful error handling, proper exit codes, timeout management
- **Maintainability:** Clear code structure, comprehensive tests, documentation
- **Scalability:** Stateless design, resource limits, efficient resource usage

### Usability Attributes

- **Learnability:** Clear documentation, examples, quick start guides
- **Efficiency:** Fast policy evaluation, connection reuse, minimal overhead
- **Satisfaction:** Clear error messages, helpful troubleshooting, responsive design

## Evolution Strategy

### Backward Compatibility

**Principle:** Maintain compatibility across minor versions.

**Implementation:**

- Semantic versioning (SemVer)
- Deprecation warnings for old features
- Migration guides for breaking changes
- Configuration validation with helpful errors

### Forward Compatibility

**Principle:** Keep the server adaptable to MCP protocol evolution without promising unbuilt features.

**Implementation:**

- MCP specification compliance
- Extensible policy engine
- Plugin-ready architecture (not yet implemented; tracked separately)
- API versioning support

## Success Metrics

### Security Objectives

- **Policy enforcement** for all operations
- **Audit coverage** for all command executions
- **Zero privileged escalation** in design
- **Network controls** enforced via IP allowlists

### Performance Goals

- **Fast policy evaluation** (< 10ms typical)
- **Efficient SSH connections** with minimal overhead
- **Resource-efficient** single container deployment
- **Responsive execution** with configurable timeouts

### Project Metrics

- **Documentation completeness** with examples for all features
- **Code quality** through testing and linting
- **Community engagement** through clear issue management
- **Feature stability** with backward compatibility

## Next Steps

- **[Architecture](04-Architecture)** - How these goals are implemented in the system design
- **[Security Model](05-Security-Model)** - Defense-in-depth security architecture
- **[Configuration](06-Configuration)** - Policy-driven configuration system
- **[Contributing](13-Contributing)** - How to contribute while maintaining these principles

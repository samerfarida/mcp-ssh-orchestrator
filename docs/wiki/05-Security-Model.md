# 5. Security Model

**Purpose:** Explain the defense-in-depth security architecture that protects against MCP security risks and ensures safe SSH command execution.

## Security Philosophy

mcp-ssh-orchestrator implements a **defense-in-depth security model** inspired by [Docker's MCP security best practices](https://www.docker.com/blog/mcp-security-explained/). Every layer provides independent security controls, ensuring that a failure in one layer doesn't compromise the entire system.

## Defense-in-Depth Architecture

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

```bash

### Policy-as-Code Enforcement Chain

1. **Declarative inputs** — `config/servers.yml`, `config/credentials.yml`, and `config/policy.yml` are parsed at startup and hashed for audit context.
2. **Policy engine** — the evaluator (`policy.py`) checks every `ssh_*` tool invocation against those YAML rules (deny-by-default, glob pattern allowlists, limit overrides).
3. **Execution + audit** — once allowed, the orchestrator records the originating rule, alias, and hashes in the JSON audit log, preserving a provable link back to the code-reviewed configuration.

This chain makes “policy-as-code” tangible: whatever is merged into Git is exactly what gatekeeps AI-issued commands.

## Layer 1: Transport Security

### stdio Transport Security

**Purpose:** Secure communication between MCP client and server.

### Implementation:

- **Process isolation** via stdio transport
- **No network exposure** of MCP server
- **Structured JSON-RPC** communication
- **Type-safe interfaces** for all tools

### Security Benefits:

- No network attack surface
- Process-level isolation
- Structured data prevents injection
- Type validation ensures integrity

### Example:

{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "ssh_run",
    "arguments": {
      "alias": "web1",
      "command": "uptime"
    }
  },
  "id": 1
}
```

### Container Isolation

**Purpose:** Isolate the MCP server from the host system.

### Implementation

- **Non-root execution** (UID 10001)
- **Read-only mounts** for config and keys (recommended at runtime)
- **Resource limits** (CPU, memory) via container runtime
- **Minimal base image** (python:3.13-slim)

### Security Benefits

- Prevents host privilege escalation
- Limits resource consumption
- Reduces attack surface
- Immutable runtime environment

### Example

# Non-root user

RUN useradd -u 10001 -m appuser
USER appuser

# Read-only mounts (applied by runtime via -v :ro)

VOLUME ["/app/config", "/app/keys"]

# Resource limits

CMD ["python", "-m", "mcp_ssh.mcp_server", "stdio"]

```bash

## Layer 2: Network Security

### IP Allowlists

**Purpose:** Restrict SSH connections to authorized networks only.

### Implementation:

- **CIDR-based allowlists** for network ranges
- **Specific IP allowlists** for individual hosts
- **IP blocklists** for dangerous addresses
- **DNS resolution verification** before connection

### Security Benefits:

- Prevents connections to unauthorized hosts
- Blocks access to public internet
- Mitigates DNS poisoning attacks
- Enforces network segmentation

### Example:

network:
  # Allow only private networks
  allow_cidrs:
    - "10.0.0.0/8"
    - "192.168.0.0/16"
    - "172.16.0.0/12"

  # Block dangerous IPs
  block_ips:
    - "0.0.0.0"
    - "255.255.255.255"
    - "169.254.0.0/16"  # Link-local
```

### Host Key Verification

**Purpose:** Prevent man-in-the-middle attacks on SSH connections.

### Implementation

- **known_hosts verification** before connection
- **Host key fingerprinting** for identity verification
- **Strict host checking** in production
- **Auto-add option** for development only

### Security Benefits

- Prevents MITM attacks
- Ensures host identity verification
- Detects host key changes
- Maintains connection integrity

### Example

limits:
  require_known_host: true  # Production default

network:
  require_known_host: true   # Override for strict checking

```text

### DNS Rate Limiting

**Purpose:** Prevent DNS-based DoS attacks and reduce load from repeated resolutions.

### Implementation:

- **Rate limiting**: Maximum 10 DNS resolutions per second per hostname
- **Result caching**: 60-second TTL cache for DNS results
- **Timeout protection**: 5-second timeout for DNS resolution
- **Per-hostname tracking**: Separate rate limits for different hostnames

### Security Benefits:

- Prevents DNS-based DoS attacks
- Reduces load on DNS infrastructure
- Protects against slow DNS server responses
- Caches results to minimize repeated lookups

### Example:

# Rate limiting prevents excessive resolutions:
# - First 10 resolutions/second: allowed
# - 11th resolution in same second: blocked (returns empty list)
# - After 1 second: limit resets

# Caching prevents repeated lookups:
# - First resolution: queries DNS server
# - Subsequent resolutions (within 60s): returns cached result
```

## Layer 3: Policy Security

Everything in this layer is sourced from `config/policy.yml`, letting you review/merge command rules, deny substrings, and execution limits the same way you handle infrastructure-as-code.

### Deny-by-Default Model

**Purpose:** Ensure no unauthorized commands can execute.

### Implementation

- **Empty rules list** = deny all
- **Explicit allow rules** required for access
- **Rule precedence** with deny rules taking priority
- **Pattern matching** with glob support

### Security Benefits

- Prevents accidental access
- Requires explicit authorization
- Reduces attack surface
- Enables least-privilege access

### Example

rules:

# Explicit allow rules only

- action: "allow"
    aliases: ["prod-*"]
    commands: ["uptime*", "df -h*"]

# All other commands denied by default

```text

### Pattern Matching Security

**Purpose:** Provide flexible yet secure command filtering.

### Implementation:

- **Glob pattern matching** for commands
- **Substring blocking** for dangerous commands
- **Alias and tag matching** for host targeting
- **Case-sensitive matching** for precision

### Security Benefits:

- Flexible command authorization
- Blocks dangerous command patterns
- Enables environment-specific policies
- Prevents command injection

### Example:

limits:
  deny_substrings:
    - "rm -rf /"
    - "shutdown*"
    - "reboot*"
    - "ssh "  # Prevent lateral movement

rules:
  - action: "allow"
    commands:
      - "systemctl status *"  # Safe status commands
      - "uptime*"            # System information
      - "df -h*"             # Disk usage
```

### Execution Limits

**Purpose:** Prevent resource exhaustion and runaway processes.

### Implementation

- **Command timeouts** (max_seconds)
- **Output size limits** (max_output_bytes)
- **Per-host overrides** for specific limits
- **Per-tag overrides** for environment limits

### Security Benefits

- Prevents resource exhaustion
- Limits data exfiltration
- Enables DoS protection
- Supports compliance requirements

### Example

limits:
  max_seconds: 60
  max_output_bytes: 1048576

overrides:
  aliases:
    prod-db-1:
      max_seconds: 20           # Stricter for production DB
      max_output_bytes: 131072  # Smaller output limit

```text

## Layer 4: Application Security

### Non-Root Execution

**Purpose:** Limit damage if the application is compromised.

### Implementation:

- **UID 10001** for application user
- **No sudo privileges** or escalation
- **Limited filesystem access** via volumes
- **No system modification** capabilities

### Security Benefits:

- Prevents privilege escalation
- Limits system access
- Reduces attack impact
- Enables container security

### Resource Limits

**Purpose:** Prevent resource exhaustion attacks.

### Implementation:

- **CPU limits** via container constraints
- **Memory limits** via container constraints
- **File descriptor limits** via ulimits
- **Process limits** via container policies

### Security Benefits:

- Prevents DoS attacks
- Ensures fair resource usage
- Enables monitoring
- Supports multi-tenancy

### Audit Logging

**Purpose:** Provide comprehensive audit trail for compliance and security.

### Implementation:

- **JSON structured logs** to stderr
- **Complete operation trail** for all commands
- **Security-relevant metadata** in every log entry
- **Immutable log format** for integrity

### Security Benefits:

- Enables incident response
- Supports compliance audits
- Provides forensic evidence
- Enables security monitoring

### Example:

{
  "type": "policy_decision",
  "ts": 1729512345.12,
  "alias": "prod-web-1",
  "hash": "a1b2c3d4e5f6",
  "allowed": true
}
{
  "type": "audit",
  "ts": 1729512345.67,
  "alias": "prod-web-1",
  "hash": "a1b2c3d4e5f6",
  "exit_code": 0,
  "duration_ms": 123,
  "bytes_out": 45,
  "bytes_err": 0,
  "cancelled": false,
  "timeout": false,
  "target_ip": "10.0.0.11"
}
```

## Security Controls Matrix

| **Threat** | **Layer 1** | **Layer 2** | **Layer 3** | **Layer 4** |
|------------|-------------|-------------|-------------|-------------|
| **Command Injection** | stdio isolation | Network filtering | Pattern matching | Resource limits |
| **Privilege Escalation** | Container isolation | Host verification | Policy enforcement | Non-root execution |
| **Data Exfiltration** | Process isolation | IP allowlists | Output limits | Audit logging |
| **Resource Exhaustion** | Container limits | Connection limits | Execution limits | Resource monitoring |
| **Lateral Movement** | Transport security | Network segmentation | Command blocking | Access logging |
| **MITM Attacks** | stdio transport | Host key verification | Policy validation | Audit trail |

## Policy Engine Security

### Rule Evaluation Security

**Purpose:** Ensure policy decisions are secure and auditable.

### Implementation

- **Deterministic evaluation** order
- **Rule precedence** with deny rules first
- **Pattern validation** before matching
- **Decision logging** for audit

### Security Benefits

- Predictable policy behavior
- Secure default decisions
- Auditable policy evaluation
- Prevents policy bypass

### Override System Security

**Purpose:** Allow granular control while maintaining security.

### Implementation

- **Per-host overrides** for specific limits
- **Per-tag overrides** for environment limits
- **Override precedence** (alias > tag > global)
- **Override validation** before application

### Security Benefits

- Granular security control
- Environment-specific policies
- Maintains security boundaries
- Enables compliance requirements

## Security Framework Alignment

### OWASP LLM Top 10

### LLM07: Insecure Plugin Design

- Policy-based command validation prevents unauthorized execution
- Input sanitization and dangerous command blocking
- Access control for AI plugin operations

### LLM08: Excessive Agency

- Role-based restrictions via host tags
- Deny-by-default security model
- Command pattern matching limits autonomous actions

### LLM01: Prompt Injection Mitigation

- SSH command validation prevents injection attacks
- Network egress controls block unauthorized connections
- DNS verification prevents DNS rebinding attacks

### MITRE ATT&CK Alignment

### T1071: Application Layer Protocol

- SSH protocol monitoring and control
- Command and response logging

### T1071.004: DNS

- DNS resolution verification
- DNS rate limiting prevents DoS attacks
- DNS result caching reduces infrastructure load
- Prevents DNS-based attack vectors

### T1659: Content Injection

- Policy-based command filtering
- Dangerous command substring blocking

### Security Features Supporting Compliance

### Features that can assist with reporting and controls

- **Access Control:** Policy-based command authorization
- **Audit Trail:** JSON audit logs to stderr (no command content)
- **Encryption:** SSH transport encryption (Ed25519/RSA keys)
- **Secrets Management:** Docker secrets or environment variables
- **Network Segmentation:** IP allowlists enforce boundaries
- **Role-Based Access:** Tag-based permission management

*Note: Compliance remains the responsibility of the deploying organization. This project offers logs and controls that can assist with reporting but does not provide certifications.*

## Supply Chain & Integrity Controls

- **GPG release signatures**: All archives attached to GitHub Releases include detached `.asc` files signed by `openpgp4fpr:6775BF3F439A2A8A198DE10D4FC5342A979BD358`. Import the key and verify every artifact before unpacking:

  gpg --receive-keys 4FC5342A979BD358
  gpg --verify mcp-ssh-orchestrator-v1.0.0.tar.gz.asc mcp-ssh-orchestrator-v1.0.0.tar.gz

```bash

- **Cosign-signed container images**: The GitHub Actions release workflow signs `ghcr.io/samerfarida/mcp-ssh-orchestrator` with Sigstore keyless certificates (`release.yml`). Validate the signature and provenance in CI/CD before promotion:

  COSIGN_EXPERIMENTAL=1 cosign verify \
    --certificate-identity-regexp "<https://github.com/samerfarida/mcp-ssh-orchestrator/.github/workflows/release.yml@>.*" \
    --certificate-oidc-issuer <https://token.actions.githubusercontent.com> \
    ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

  ```

  Digests, signatures, and attestations are published alongside each tag in the GitHub Packages feed, enabling immutable deployment pins.

- **OpenSSF Scorecard**: Automated Scorecard runs track branch protections, dependency update hygiene, CI hardening, and token hygiene. Monitor the live score at `https://api.scorecard.dev/projects/github.com/samerfarida/mcp-ssh-orchestrator` and treat regressions as release blockers.

## Security Monitoring

### Real-Time Monitoring

### Metrics Tracked

- **Policy violations** (denied commands)
- **Execution failures** (timeouts, errors)
- **Resource usage** (CPU, memory, connections)
- **Network access** (unauthorized IPs)

### Alerting

- **Repeated policy violations** from same source
- **Unexpected target IPs** in connections
- **Resource exhaustion** warnings
- **High-privilege commands** execution

### Incident Response

### Detection

- **Audit log analysis** for suspicious patterns
- **Policy violation correlation** across hosts
- **Resource usage anomalies** detection
- **Network access violations** monitoring

### Response

- **Immediate policy updates** for new threats
- **Host isolation** for compromised systems
- **Credential rotation** for exposed keys
- **Forensic analysis** using audit logs

## Security Best Practices

### Configuration Security

1. **Use deny-by-default policies**
2. **Enable host key verification**
3. **Configure IP allowlists**
4. **Set appropriate timeouts and limits**
5. **Use strong SSH keys (Ed25519/RSA 4096)**

### Operational Security

1. **Monitor audit logs continuously**
2. **Rotate SSH keys quarterly**
3. **Review policy rules monthly**
4. **Test policy changes with dry-run**
5. **Maintain incident response procedures**

### Development Security

1. **Containerize all deployments**
2. **Use non-root execution**
3. **Implement resource limits**
4. **Enable comprehensive logging**
5. **Follow secure coding practices**

## Next Steps

- **[Configuration](06-Configuration)** - How to implement these security controls
- **[Troubleshooting](12-Troubleshooting)** - Security incident response procedures
- **[Observability & Audit](11-Observability-Audit)** - Monitoring and compliance implementation
- **[Deployment](09-Deployment)** - Secure production deployment practices

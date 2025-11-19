# Security Guide

This document provides security guidance for deploying and operating mcp-ssh-orchestrator in production environments.

## Threat Model

### Assets

- **SSH Private Keys**: Used for authentication to target hosts
- **Credentials**: Passwords, passphrases, and other secrets
- **Target Hosts**: SSH servers under management
- **Command History**: Audit logs of executed commands
- **Configuration**: Policy rules and host inventory

### Threats

1. **Unauthorized Command Execution**: Attacker gains ability to run arbitrary commands
2. **Credential Theft**: SSH keys or passwords are exposed
3. **Lateral Movement**: Attacker pivots from compromised host to others
4. **Data Exfiltration**: Sensitive output is leaked
5. **Denial of Service**: Resource exhaustion or service disruption
6. **Policy Bypass**: Circumventing allow/deny rules

### Mitigations

All threats are addressed through defense-in-depth controls documented below.

## Authentication & Credentials

### Path Traversal Protection

**Security Enhancement:** All credential and key path resolution includes path traversal protection to prevent unauthorized file access.

#### Secret Path Protection

Secret names and paths are validated to prevent directory traversal attacks:

1. **Secret Name Validation**: Only alphanumeric characters, dashes, and underscores are allowed

   ```yaml
   # Valid secret names

   password_secret: "prod_password"
   password_secret: "key-passphrase-2024"
   password_secret: "admin_password_1"

   # Invalid (will be rejected)

   password_secret: "../etc/passwd"     # Path traversal
   password_secret: "/absolute/path"    # Absolute path
   password_secret: "secret.name"       # Special characters
   ```

1. **Path Normalization**: All paths are normalized and validated to stay within `/app/secrets`

   - Relative paths are resolved relative to secrets directory
   - Absolute paths are rejected for secrets
   - Paths containing `../` or `..\\` are blocked

1. **Security Event Logging**: Path traversal attempts are logged for monitoring:

   ```json
   {
     "level": "error",
     "kind": "security_event",
     "type": "path_traversal_attempt",
     "secret_name": "../etc/passwd",
     "reason": "path_outside_allowed_directory"
   }
   ```

#### SSH Key Path Protection

SSH key paths include similar protections:

1. **Traversal Pattern Detection**: Paths containing `..` patterns are rejected

   ```yaml
   # Valid key paths

   key_path: "id_ed25519"
   key_path: "prod_key"
   key_path: "/app/keys/id_ed25519"  # Absolute within keys_dir

   # Invalid (will be rejected)

   key_path: "../outside_key"        # Path traversal
   key_path: "/etc/passwd"           # Outside keys_dir
   key_path: "key/../../etc/passwd"   # Encoded traversal
   ```

1. **Absolute Path Validation**: Absolute paths must be within the configured `keys_dir`

   - Paths outside `/app/keys` (or custom keys_dir) are rejected
   - Prevents accessing keys from other locations

1. **Security Event Logging**: All path traversal attempts are logged with full context

**Effect**: Prevents reading files outside intended directories, blocking common path traversal attack vectors.

#### File Type Validation

All resolved paths are validated to ensure they are regular files:

1. **Directory Rejection**: Paths pointing to directories are rejected

   ```yaml
   # Invalid (will be rejected)

   password_secret: "subdirectory"  # Points to a directory, not a file
   ```

1. **Symlink Rejection**: Symbolic links are rejected for security

   ```yaml
   # Invalid (will be rejected)

   password_secret: "symlink_secret"  # Points to a symlink, not a regular file
   ```

   **Why reject symlinks?** Symlinks can be manipulated to point outside the allowed directory or to sensitive files, creating security risks.

1. **Regular File Requirement**: Only regular files within the allowed directory are accepted
   - Non-existent files are allowed for SSH keys (validated when used)
   - Secrets must exist as regular files (immediate read required)
   - All paths must stay within their designated directories

1. **Security Event Logging**: File validation failures are logged:

   ```json
   {
     "level": "error",
     "kind": "security_event",
     "type": "file_validation_failed",
     "file_path": "/app/secrets/subdirectory",
     "reason": "path_is_directory"
   }
   ```

**Effect**: Prevents accessing directories or symlinks that could lead to security vulnerabilities or unauthorized access.

#### YAML File Size Limits

All YAML configuration files are validated for size before loading to prevent resource exhaustion attacks:

1. **Size Limit**: Maximum file size of 10MB per YAML file
   - Applies to: `servers.yml`, `credentials.yml`, `policy.yml`
   - Prevents resource exhaustion via oversized configuration files
   - Files exceeding limit are rejected with security event logging

1. **Size Validation**: File size is checked using `os.path.getsize()` before parsing
   - Prevents loading files into memory if they exceed the limit
   - Returns empty dictionary on size limit violation
   - No YAML parsing performed if file is too large

1. **Security Event Logging**: Size limit violations are logged:

   ```json
   {
     "level": "error",
     "kind": "security_event",
     "type": "file_size_limit_exceeded",
     "path": "/app/config/servers.yml",
     "file_size": 10485761,
     "max_size": 10485760,
     "reason": "yaml_file_too_large"
   }
   ```

1. **Normal Operation**: Files at or below the 10MB limit load normally
   - 10MB is sufficient for typical configuration files
   - Large configuration files (multiple thousands of hosts) are supported
   - Prevents abuse while allowing legitimate use cases

**Effect**: Prevents resource exhaustion attacks via oversized YAML files that could consume excessive memory or processing time.

#### Input Validation for User-Controlled Parameters

All user-controlled parameters are validated before processing to prevent injection attacks and resource exhaustion:

1. **Alias Validation**:
   - Length limit: 100 characters
   - Allowed characters: alphanumeric, dash (`-`), underscore (`_`), dot (`.`)
   - Rejects empty values
   - Applied to: `ssh_describe_host`, `ssh_plan`, `ssh_run`, `ssh_run_async`

1. **Command Validation**:
   - Length limit: 10,000 characters
   - Rejects null bytes (`\x00`) - common injection vector
   - Rejects control characters (except newline `\n`, tab `\t`, carriage return `\r`)
   - Allows legitimate multi-line commands
   - Applied to: `ssh_plan`, `ssh_run`, `ssh_run_on_tag`, `ssh_run_async`

1. **Tag Validation**:
   - Length limit: 50 characters
   - Allowed characters: alphanumeric, dash (`-`), underscore (`_`), dot (`.`)
   - Rejects empty values
   - Applied to: `ssh_run_on_tag`

1. **Task ID Validation**:
   - Length limit: 200 characters
   - Allowed characters: alphanumeric, colon (`:`), dash (`-`), underscore (`_`)
   - Format validation: expected pattern `alias:hash:timestamp`
   - Applied to: `ssh_cancel`, `ssh_get_task_status`, `ssh_get_task_result`, `ssh_get_task_output`, `ssh_cancel_async_task`

1. **Security Event Logging**: Invalid input attempts are logged:

   ```json
   {
     "level": "error",
     "msg": "security_event",
     "type": "null_byte_injection_attempt",
     "field": "command"
   }
   ```

**Effect**: Prevents injection attacks (null bytes, control characters) and resource exhaustion (length limits) via malformed user inputs.

#### Input Length Limits for Configuration Parameters

String parameters in configuration files have length limits to prevent resource exhaustion:

1. **Secret Names** (`credentials.yml`):
   - Maximum length: 100 characters
   - Validated in `_resolve_secret()` function
   - Rejects names exceeding limit with security event logging

1. **SSH Key Paths** (`credentials.yml`):
   - Maximum length: 500 characters
   - Validated in `_resolve_key_path()` function
   - Rejects paths exceeding limit with security event logging

1. **MCP Tool Parameters** (from PR6):
   - **Alias**: Maximum 100 characters
   - **Command**: Maximum 10,000 characters
   - **Tag**: Maximum 50 characters
   - **Task ID**: Maximum 200 characters

1. **Length Validation Order**: Length validation occurs before other validations (character validation, path traversal checks) to prevent processing of oversized inputs.

1. **Security Event Logging**: Length limit violations are logged:

   ```json
   {
     "level": "error",
     "kind": "security_event",
     "type": "input_length_limit_exceeded",
     "field": "secret_name",
     "length": 150,
     "max_length": 100,
     "reason": "secret_name_too_long"
   }
   ```

**Effect**: Prevents resource exhaustion attacks via oversized string inputs in configuration files and user-controlled parameters.

#### DNS Rate Limiting

DNS resolution is rate-limited and cached to prevent DNS-based DoS attacks:

1. **Rate Limiting**:
   - Maximum 10 DNS resolutions per second per hostname
   - Per-hostname rate limiting (different hostnames have separate limits)
   - Time-window based (sliding 1-second window)
   - Exceeding limit returns empty list (no IPs resolved)

1. **Result Caching**:
   - DNS results cached for 60 seconds (TTL)
   - Cached results returned immediately without DNS lookup
   - Reduces load on DNS servers
   - Caches both successful and failed resolutions (prevents repeated lookups for invalid hostnames)

1. **Timeout Protection**:
   - DNS resolution timeout: 5 seconds
   - Prevents hanging on slow or unresponsive DNS servers
   - Failed resolutions return empty list

1. **Rate Limit Logging**: Rate limit violations are logged:

1. **Thread Safety**: Rate limiter and cache are thread-safe for concurrent access.

**Effect**: Prevents DNS-based DoS attacks by limiting resolution frequency and caching results, reducing load on DNS infrastructure.

#### Command Denial Bypass Prevention

Command denial logic has been enhanced to prevent bypass attempts via obfuscation:

1. **Command Normalization**:
   - Removes single and double quotes from commands
   - Removes escaped characters (e.g., `\` becomes space)
   - Normalizes whitespace (collapses multiple spaces/tabs to single space)
   - Applied before checking against `deny_substrings` list

1. **Dual Checking**:
   - Checks original command string (maintains existing behavior)
   - Checks normalized command string (catches obfuscated bypass attempts)
   - Both checks must pass for command to be allowed

1. **Token-Based Matching**:
   - Splits normalized command into tokens
   - Checks for exact token matches against deny patterns
   - Prevents partial bypasses (e.g., `rm -rf /var` vs `rm -rf /`)

1. **Bypass Attempt Detection**: Commands that would bypass original checking but are caught by normalization are logged:

   ```json
   {
     "level": "error",
     "msg": "security_event",
     "type": "command_bypass_attempt",
     "alias": "web1",
     "original_command": "'rm -rf /'",
     "normalized_command": "rm -rf /",
     "blocked_pattern": "rm -rf /"
   }
   ```

1. **Supported Bypass Techniques Prevented**:
   - Quote obfuscation: `'rm -rf /'`, `"rm -rf /"`
   - Escaped characters: `rm\ -rf\ /`
   - Whitespace variations: `rm    -rf    /`, `rm\t-rf\t/`
   - Mixed techniques: `echo "rm\\ -rf\\ /"`

1. **Limitations**:
   - Perfect prevention would require full command parsing
   - Complex obfuscation (base64 encoding, variable substitution) may still bypass
   - Focus is on common bypass techniques, not all possible obfuscation methods

**Effect**: Significantly reduces risk of command denial bypasses through common obfuscation techniques (quotes, escaping, whitespace).

#### Command Chaining Protection

**Security Enhancement:** Command chaining operators are parsed and validated individually to prevent policy bypass.

**Vulnerability Addressed:**
Previously, commands like `uptime && apt list --upgradable` could bypass policy if `uptime` was allowed, even though `apt list --upgradable` was denied. This occurred because the policy engine matched the entire command string against patterns, and `"uptime*"` matched any string starting with "uptime".

### Implementation

1. **Command Chain Parsing**: Commands containing chaining operators (`&&`, `||`, `;`, `|`) are parsed into individual commands
2. **Individual Validation**: Each command in the chain is validated separately against policy rules
3. **Strict Enforcement**: All commands in a chain must be allowed; if any command is denied, the entire chain is blocked
4. **Order Independence**: Validation is order-independent (e.g., `cmd1 && cmd2` and `cmd2 && cmd1` are validated the same way)

### Supported Operators

- `&&` - Logical AND
- `||` - Logical OR
- `;` - Sequential execution
- `|` - Pipe operator

### Command Substitution Handling

- Backtick substitution: `` `command` ``
- Dollar-paren substitution: `$(command)`
- Substitutions are preserved within commands and validated as part of the command

**Security Logging:**
Command chain parsing and denials are logged for security audit:

```json
{
  "level": "info",
  "msg": "security_event",
  "type": "command_chain_parsed",
  "alias": "prod-web-1",
  "original_command": "uptime && apt list --upgradable",
  "parsed_commands": ["uptime", "apt list --upgradable"],
  "command_count": 2
}
```

```json
{
  "level": "warn",
  "msg": "security_event",
  "type": "command_chain_denied",
  "alias": "prod-web-1",
  "original_command": "uptime && apt list --upgradable",
  "denied_command": "apt list --upgradable",
  "parsed_commands": ["uptime", "apt list --upgradable"],
  "denied_index": 1
}
```

### Examples

```bash
# Policy allows: uptime*, whoami
# Policy denies: apt list --upgradable*

# ✅ ALLOWED: Both commands are allowed
uptime && whoami

# ❌ DENIED: Second command is denied (previously would have been allowed)
uptime && apt list --upgradable

# ❌ DENIED: First command is denied
apt list --upgradable && uptime

# ✅ ALLOWED: All commands are allowed
uptime && whoami && hostname

# ❌ DENIED: Middle command is denied
uptime && apt list --upgradable && whoami
```

### Testing Coverage

- Unit tests for command parsing (all operators, edge cases)
- Policy validation tests (all chaining scenarios)
- Integration tests (ssh_plan, ssh_run, ssh_run_on_tag)
- Security tests (all previously exploitable bypass scenarios verified blocked)
- Backward compatibility tests (simple commands unchanged)

**Effect**: Prevents policy bypass via command chaining, ensuring that denied commands cannot be executed by chaining them with allowed commands.

### SSH Key Management

### Best Practices

1. **Use Ed25519 Keys**: Prefer `ed25519` over RSA for modern security

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/mcp_orchestrator -C "mcp-ssh-orchestrator"
   ```

1. **Key Permissions**: Set private keys to read-only for owner

   ```bash
   chmod 0400 /path/to/keys/id_ed25519
   ```

Additional best practices:

1. **Separate Keys**: Use dedicated keys for the orchestrator (not your personal keys)
2. **Key Rotation**: Rotate keys periodically (quarterly recommended)
3. **Passphrase Protection**: Use passphrases for private keys

   ```yaml
   # credentials.yml
   entries:
     - name: prod_admin
       username: ubuntu
       key_path: id_ed25519
       key_passphrase_secret: prod_key_passphrase
   ```

### Password Authentication

**Avoid password authentication when possible.** If required:

1. **Use Secrets**: Never hardcode passwords in YAML

   ```yaml
   # credentials.yml
   entries:
     - name: legacy_system
       username: admin
       password_secret: legacy_password  # Resolved from secret
   ```

1. **Secret Resolution Order**:
   - Direct environment variable (Docker MCP Gateway): `<SECRET_NAME>` (uppercase, matches `env:` field in server.yml)
   - Prefixed environment variable (standalone/backward compatibility): `MCP_SSH_SECRET_<NAME>` (uppercase)
   - `.env` file: `/app/secrets/.env` (consolidated secrets file with `KEY=value` format)
   - Docker secret file: `/app/secrets/<name>`

Additional requirements:

1. **Strong Passwords**: Minimum 16 characters, high entropy
2. **Limited Scope**: Use password auth only for hosts that don't support keys

### Secrets Storage

### Docker Secrets (Recommended for Production)

```bash
# Create secret
echo "my-passphrase" | docker secret create ssh_key_passphrase -

# Use in Docker Compose
services:
  mcp-ssh:
    secrets:
      - ssh_key_passphrase
secrets:
  ssh_key_passphrase:
    external: true
   ```

### Environment Variables (Development Only)

```bash
docker run -i --rm \
  -e MCP_SSH_SECRET_ADMIN_PASSWORD="dev-password" \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

### File-Based Secrets (Simple Deployments)

```bash
# Create secrets directory
mkdir -p ~/mcp-ssh/secrets
chmod 0700 ~/mcp-ssh/secrets

# Add secret
echo "passphrase" > ~/mcp-ssh/secrets/key_passphrase
chmod 0400 ~/mcp-ssh/secrets/key_passphrase
```

### Package & Image Verification

1. **GitHub Release Assets**
   - Every tarball/zip produced by the release workflow is signed with the maintainer GPG key (`openpgp4fpr:6775BF3F439A2A8A198DE10D4FC5342A979BD358`).
   - Import the public key once, then verify each artifact:

     ```bash
     gpg --receive-keys 4FC5342A979BD358
     gpg --verify mcp-ssh-orchestrator-v1.0.0.tar.gz.asc mcp-ssh-orchestrator-v1.0.0.tar.gz
     ```

1. **Container Images (GHCR)**
   - The `ghcr.io/samerfarida/mcp-ssh-orchestrator` images are keylessly signed with Sigstore cosign in `.github/workflows/release.yml`.
   - Verify signatures (and optional attestations) before promoting an image between environments:

     ```bash
     COSIGN_EXPERIMENTAL=1 cosign verify \
       --certificate-identity-regexp "https://github.com/samerfarida/mcp-ssh-orchestrator/.github/workflows/release.yml@.*" \
       --certificate-oidc-issuer https://token.actions.githubusercontent.com \
       ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
     ```

   - Published digests and signature bundles are available for every tag in the GitHub Packages feed so you can pin exact builds.

1. **OpenSSF Scorecard**
   - The repository maintains a public Scorecard run covering branch protections, dependency update hygiene, build hardening, and other supply-chain controls. Monitor the score at `https://api.scorecard.dev/projects/github.com/samerfarida/mcp-ssh-orchestrator`.

## Network Security

### Host Key Verification

**Security Requirement (CWE-295)**: Host key verification is **always enforced** for security. The system always uses `RejectPolicy()` to prevent MITM attacks. Unsafe policies (`AutoAddPolicy`, `AcceptPolicy`) are never used.

### Configuration

```yaml
# policy.yml
limits:
  require_known_host: true   # Always enforced (default)
  host_key_auto_add: false   # Deprecated: ignored for security

network:
  require_known_host: true   # Always enforced (default)
```

**Note**: `host_key_auto_add: true` and `require_known_host: false` are deprecated and ignored. Deprecation warnings are logged when these unsafe configurations are detected.

### Populate known_hosts

```bash
# Scan host keys
ssh-keyscan -H 10.0.0.11 >> ~/mcp-ssh/keys/known_hosts
ssh-keyscan -H 10.0.0.21 >> ~/mcp-ssh/keys/known_hosts

# Or copy from existing
cp ~/.ssh/known_hosts ~/mcp-ssh/keys/
```

**Effect**: Prevents MITM attacks by verifying host identity before connection. All SSH connections require a known_hosts entry.

**Migration**: If you have existing configurations using `host_key_auto_add: true` or `require_known_host: false`, you must:

1. Populate your `known_hosts` file using `ssh-keyscan`
2. Remove unsafe configuration options
3. Ensure `require_known_host: true` is set (default)

### IP Allowlisting

### Restrict SSH targets to known networks

```yaml
# policy.yml
network:
  # Allow only RFC1918 private networks
  allow_cidrs:
    - "10.0.0.0/8"
    - "172.16.0.0/12"
    - "192.168.0.0/16"

  # Block specific IPs
  block_ips:
    - "10.10.10.10"
```

### Two-Stage Verification

1. **Pre-Connect**: DNS resolution must match allowlist
2. **Post-Connect**: Actual peer IP must match allowlist

**Effect**: Prevents connections to unexpected IPs, mitigates DNS poisoning.

### Egress Controls

### Block lateral movement tools by default

```yaml
# policy.yml
limits:
  deny_substrings:
    - "ssh "
    - "scp "
    - "rsync -e ssh"
    - "curl "
    - "wget "
    - "nc "
    - "nmap "
```

**Effect**: Prevents compromised hosts from initiating outbound connections.

## Policy Enforcement

### Deny-by-Default

### Start with no access, add only what's needed

```yaml
# policy.yml
rules:
  # Allow safe read-only commands
  - action: "allow"
    aliases: ["*"]
    tags: []
    commands:
      - "uname*"
      - "uptime*"
      - "df -h*"

  # All other commands denied by default
```

### Glob Pattern Safety

### Use specific patterns to avoid overly broad matches

```yaml
# BAD: Too permissive
commands:
  - "*"

# GOOD: Specific commands
commands:
  - "systemctl status nginx"
  - "systemctl restart nginx"
```

### Environment Separation

### Use tags to separate production from non-production

```yaml
# Policy for production
rules:
  - action: "allow"
    aliases: []
    tags: ["production"]
    commands:
      - "uptime*"
      - "df -h*"

  - action: "deny"
    aliases: []
    tags: ["production"]
    commands:
      - "systemctl restart*"  # Denied on prod

# Policy for staging (more permissive)
rules:
  - action: "allow"
    aliases: []
    tags: ["staging"]
    commands:
      - "systemctl restart*"  # Allowed on staging
```

### Per-Host Overrides

### Apply stricter limits to sensitive hosts

```yaml
# policy.yml
overrides:
  aliases:
    prod-db-1:
      max_seconds: 20           # Shorter timeout
      max_output_bytes: 262144  # Smaller output cap
      require_known_host: true  # Strict host key check
```

## Execution Limits

### Timeout Enforcement

### Prevent runaway commands

```yaml
# policy.yml
limits:
  max_seconds: 60  # Global default

overrides:
  tags:
    production:
      max_seconds: 30  # Stricter for prod

    longrun:
      max_seconds: 300  # Exception for maintenance
```

### Output Size Caps

### Prevent memory exhaustion

```yaml
# policy.yml
limits:
  max_output_bytes: 1048576  # 1 MiB default

overrides:
  aliases:
    log-server:
      max_output_bytes: 10485760  # 10 MiB for log hosts
```

### Deny Dangerous Substrings

### Block destructive commands

```yaml
# policy.yml
limits:
  deny_substrings:
    - "rm -rf /"
    - ":(){ :|:& };:"  # Fork bomb
    - "mkfs "
    - "dd if=/dev/zero"
    - "shutdown"
    - "reboot"
    - "userdel"
    - "passwd"
```

## Container Security

### Non-Root Execution

Container runs as UID 10001 (non-root):

```dockerfile
RUN useradd -u 10001 -m appuser
USER appuser
```

**Effect**: Limits damage if container is compromised.

### Read-Only Mounts

### Mount configuration and keys as read-only

```bash
docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

**Effect**: Prevents accidental or malicious modification of config/keys.

### Minimal Base Image

Uses `python:3.13-slim`:

- Smaller attack surface
- Fewer packages to patch
- Reduced image size

### Health Checks

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import mcp_ssh" || exit 1
```

**Effect**: Early detection of container failures.

## Audit & Monitoring

### Security Audit Logging

Security-relevant events are logged to stderr in structured JSON format via `_log_security_event()`:

### Security Audit Log Format

```json
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

### Event Types Logged

- `path_traversal_attempt`: Path traversal detected in secret/key resolution
- `file_validation_failed`: Directory/symlink/non-file paths rejected
- `file_size_limit_exceeded`: Oversized YAML files rejected
- `input_length_limit_exceeded`: Oversized string inputs rejected
- `invalid_secret_name`: Invalid characters in secret names
- `dns_rate_limit_exceeded`: DNS resolution rate limit violations
- `command_bypass_attempt`: Command denial bypass attempts detected

### Audit Log Fields

- `ts`: Unix timestamp (float)
- `timestamp`: ISO 8601 formatted timestamp (string)
- `attempted_path`: Original input that triggered the event
- `resolved_path`: Resolved/absolute path (if applicable)
- `reason`: Human-readable reason for the security event
- `additional_data`: Event-specific context (sizes, limits, patterns, etc.)

**Security Monitoring:**
All security audit events are written to stderr for log aggregation and SIEM integration.

### Command Execution Audit Logging

All operations logged to stderr as JSON:

```json
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

### Fields

- `type`: Event type (audit, policy_decision, progress)
- `ts`: Unix timestamp
- `alias`: Target host
- `hash`: Command hash (first 16 chars of SHA256)
- `exit_code`: Command exit status
- `duration_ms`: Execution time
- `bytes_out/bytes_err`: Output size
- `cancelled/timeout`: Termination reason
- `target_ip`: Actual peer IP connected

### Log Collection

### Docker Compose with logging driver

```yaml
services:
  mcp-ssh:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Forward to SIEM

```bash
docker logs -f mcp-ssh-orchestrator 2>&1 | \
  jq -r 'select(.type == "audit") | @json' | \
  curl -X POST https://siem.example.com/ingest -d @-
```

### Monitoring Recommendations

### Alert on

- Policy denials (especially repeated)
- Timeouts
- Non-zero exit codes on critical hosts
- Unexpected target IPs
- High-privilege commands (sudo, systemctl)

### Metrics to track

- Commands per hour
- Success rate by host
- Average duration
- Policy violation rate

## Incident Response

### Compromised Key

1. **Immediately revoke** the key on all target hosts:

   ```bash
   # Remove from authorized_keys on each host
   ssh user@host "sed -i '/mcp-orchestrator/d' ~/.ssh/authorized_keys"
   ```

1. **Rotate keys**:

   ```bash
   # Generate new key
   ssh-keygen -t ed25519 -f new_key

   # Deploy to hosts
   for host in $(cat hosts.txt); do
     ssh-copy-id -i new_key.pub user@$host
   done
   ```

1. **Update configuration**:

   ```yaml
   # credentials.yml
   entries:
     - name: prod_admin
       key_path: new_key  # Updated
   ```

1. **Review audit logs** for unauthorized usage

### Policy Bypass Detected

1. **Stop the orchestrator** immediately
2. **Review policy rules** for gaps
3. **Check audit logs** for pattern
4. **Patch policy**:

   ```yaml
   # Add deny rule for bypass technique
   limits:
     deny_substrings:
       - "<bypass pattern>"
   ```

5. **Reload config**: `ssh_reload_config`

### Unauthorized Access

1. **Check who accessed**:

   ```bash
   # Audit log analysis
   jq -r 'select(.alias == "compromised-host") | [.ts, .hash, .target_ip] | @tsv' < audit.log
   ```

2. **Identify command hashes** executed
3. **Correlate with target host logs**
4. **Contain affected hosts**
5. **Rotate credentials**

## Security Framework Alignment

### OWASP LLM Top 10 Coverage

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

- **T1071**: Application Layer Protocol (SSH monitoring)
- **T1071.004**: DNS (DNS resolution verification)
- **T1659**: Content Injection (policy-based command filtering)

### Security Features Supporting Compliance

This tool provides structured logging, policy enforcement, and network safeguards that can support your internal governance and audit requirements. Formal regulatory compliance remains the responsibility of the deploying organization.

## Security Checklist

### Before Production Deployment

- [ ] Use Ed25519 or RSA 4096-bit keys
- [ ] Set private key permissions to 0400
- [ ] Enable `require_known_host: true`
- [ ] Populate known_hosts file
- [ ] Configure IP allowlists (allow_cidrs)
- [ ] Enable deny_substrings for dangerous commands
- [ ] Use deny-by-default policy model
- [ ] Mount config and keys as read-only (:ro)
- [ ] Use Docker secrets or env vars (not hardcoded passwords)
- [ ] Set up audit log collection
- [ ] Configure alerting on policy violations
- [ ] Document incident response procedures
- [ ] Test policy with `ssh_plan` before `ssh_run`
- [ ] Separate production from non-production (tags)
- [ ] Set appropriate timeouts and output limits
- [ ] Review and minimize container privileges
- [ ] Enable Docker health checks
- [ ] Use specific command patterns (avoid overly broad globs)
- [ ] Rotate keys quarterly
- [ ] Keep Docker image updated

## Reporting Security Issues

### Do not open public issues for security vulnerabilities

Email: `samer.farida@yahoo.com` or use [GitHub Security Advisories](https://github.com/samerfarida/mcp-ssh-orchestrator/security/advisories/new)

Include:

- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

We aim to respond within 48 hours and patch critical issues within 7 days.

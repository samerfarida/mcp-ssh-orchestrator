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
   # ✅ Valid secret names
   password_secret: "prod_password"
   password_secret: "key-passphrase-2024"
   password_secret: "admin_password_1"
   
   # ❌ Invalid (will be rejected)
   password_secret: "../etc/passwd"     # Path traversal
   password_secret: "/absolute/path"    # Absolute path
   password_secret: "secret.name"       # Special characters
   ```

2. **Path Normalization**: All paths are normalized and validated to stay within `/app/secrets`
   - Relative paths are resolved relative to secrets directory
   - Absolute paths are rejected for secrets
   - Paths containing `../` or `..\\` are blocked

3. **Security Event Logging**: Path traversal attempts are logged for monitoring:
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
   # ✅ Valid key paths
   key_path: "id_ed25519"
   key_path: "prod_key"
   key_path: "/app/keys/id_ed25519"  # Absolute within keys_dir
   
   # ❌ Invalid (will be rejected)
   key_path: "../outside_key"        # Path traversal
   key_path: "/etc/passwd"           # Outside keys_dir
   key_path: "key/../../etc/passwd"   # Encoded traversal
   ```

2. **Absolute Path Validation**: Absolute paths must be within the configured `keys_dir`
   - Paths outside `/app/keys` (or custom keys_dir) are rejected
   - Prevents accessing keys from other locations

3. **Security Event Logging**: All path traversal attempts are logged with full context

**Effect**: Prevents reading files outside intended directories, blocking common path traversal attack vectors.

#### File Type Validation

All resolved paths are validated to ensure they are regular files:

1. **Directory Rejection**: Paths pointing to directories are rejected
   ```yaml
   # ❌ Invalid (will be rejected)
   password_secret: "subdirectory"  # Points to a directory, not a file
   ```

2. **Symlink Rejection**: Symbolic links are rejected for security
   ```yaml
   # ❌ Invalid (will be rejected)
   password_secret: "symlink_secret"  # Points to a symlink, not a regular file
   ```
   **Why reject symlinks?** Symlinks can be manipulated to point outside the allowed directory or to sensitive files, creating security risks.

3. **Regular File Requirement**: Only regular files within the allowed directory are accepted
   - Non-existent files are allowed for SSH keys (validated when used)
   - Secrets must exist as regular files (immediate read required)
   - All paths must stay within their designated directories

4. **Security Event Logging**: File validation failures are logged:
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

2. **Size Validation**: File size is checked using `os.path.getsize()` before parsing
   - Prevents loading files into memory if they exceed the limit
   - Returns empty dictionary on size limit violation
   - No YAML parsing performed if file is too large

3. **Security Event Logging**: Size limit violations are logged:
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

4. **Normal Operation**: Files at or below the 10MB limit load normally
   - 10MB is sufficient for typical configuration files
   - Large configuration files (multiple thousands of hosts) are supported
   - Prevents abuse while allowing legitimate use cases

**Effect**: Prevents resource exhaustion attacks via oversized YAML files that could consume excessive memory or processing time.

### SSH Key Management

**Best Practices:**

1. **Use Ed25519 Keys**: Prefer `ed25519` over RSA for modern security
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/mcp_orchestrator -C "mcp-ssh-orchestrator"
   ```

2. **Key Permissions**: Set private keys to read-only for owner
   ```bash
   chmod 0400 /path/to/keys/id_ed25519
   ```

3. **Separate Keys**: Use dedicated keys for the orchestrator (not your personal keys)

4. **Key Rotation**: Rotate keys periodically (quarterly recommended)

5. **Passphrase Protection**: Use passphrases for private keys
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

2. **Secret Resolution Order**:
   - Environment variable: `MCP_SSH_SECRET_<NAME>` (uppercase)
   - Docker secret file: `/app/secrets/<name>`

3. **Strong Passwords**: Minimum 16 characters, high entropy

4. **Limited Scope**: Use password auth only for hosts that don't support keys

### Secrets Storage

**Docker Secrets (Recommended for Production):**

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

**Environment Variables (Development Only):**

```bash
docker run -i --rm \
  -e MCP_SSH_SECRET_ADMIN_PASSWORD="dev-password" \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0
```

**File-Based Secrets (Simple Deployments):**

```bash
# Create secrets directory
mkdir -p ~/mcp-ssh/secrets
chmod 0700 ~/mcp-ssh/secrets

# Add secret
echo "passphrase" > ~/mcp-ssh/secrets/key_passphrase
chmod 0400 ~/mcp-ssh/secrets/key_passphrase
```

## Network Security

### Host Key Verification

**Always enable in production:**

```yaml
# policy.yml
limits:
  require_known_host: true

network:
  require_known_host: true  # Overrides limits setting
```

**Populate known_hosts:**

```bash
# Scan host keys
ssh-keyscan -H 10.0.0.11 >> ~/mcp-ssh/keys/known_hosts
ssh-keyscan -H 10.0.0.21 >> ~/mcp-ssh/keys/known_hosts

# Or copy from existing
cp ~/.ssh/known_hosts ~/mcp-ssh/keys/
```

**Effect**: Prevents MITM attacks by verifying host identity before connection.

### IP Allowlisting

**Restrict SSH targets to known networks:**

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

**Two-Stage Verification:**
1. **Pre-Connect**: DNS resolution must match allowlist
2. **Post-Connect**: Actual peer IP must match allowlist

**Effect**: Prevents connections to unexpected IPs, mitigates DNS poisoning.

### Egress Controls

**Block lateral movement tools by default:**

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

**Start with no access, add only what's needed:**

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

**Use specific patterns to avoid overly broad matches:**

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

**Use tags to separate production from non-production:**

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

**Apply stricter limits to sensitive hosts:**

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

**Prevent runaway commands:**

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

**Prevent memory exhaustion:**

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

**Block destructive commands:**

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

**Mount configuration and keys as read-only:**

```bash
docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.1.0
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

### Audit Logging

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

**Fields:**
- `type`: Event type (audit, policy_decision, progress)
- `ts`: Unix timestamp
- `alias`: Target host
- `hash`: Command hash (first 12 chars of SHA256)
- `exit_code`: Command exit status
- `duration_ms`: Execution time
- `bytes_out/bytes_err`: Output size
- `cancelled/timeout`: Termination reason
- `target_ip`: Actual peer IP connected

### Log Collection

**Docker Compose with logging driver:**

```yaml
services:
  mcp-ssh:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Forward to SIEM:**

```bash
docker logs -f mcp-ssh-orchestrator 2>&1 | \
  jq -r 'select(.type == "audit") | @json' | \
  curl -X POST https://siem.example.com/ingest -d @-
```

### Monitoring Recommendations

**Alert on:**
- Policy denials (especially repeated)
- Timeouts
- Non-zero exit codes on critical hosts
- Unexpected target IPs
- High-privilege commands (sudo, systemctl)

**Metrics to track:**
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

2. **Rotate keys**:
   ```bash
   # Generate new key
   ssh-keygen -t ed25519 -f new_key
   
   # Deploy to hosts
   for host in $(cat hosts.txt); do
     ssh-copy-id -i new_key.pub user@$host
   done
   ```

3. **Update configuration**:
   ```yaml
   # credentials.yml
   entries:
     - name: prod_admin
       key_path: new_key  # Updated
   ```

4. **Review audit logs** for unauthorized usage

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

**LLM07: Insecure Plugin Design** ✅
- Policy-based command validation prevents unauthorized execution
- Input sanitization and dangerous command blocking
- Access control for AI plugin operations

**LLM08: Excessive Agency** ✅
- Role-based restrictions via host tags
- Deny-by-default security model
- Command pattern matching limits autonomous actions

**LLM01: Prompt Injection Mitigation**
- SSH command validation prevents injection attacks
- Network egress controls block unauthorized connections
- DNS verification prevents DNS rebinding attacks

### MITRE ATT&CK Alignment

- **T1071**: Application Layer Protocol (SSH monitoring)
- **T1071.004**: DNS (DNS resolution verification)
- **T1659**: Content Injection (policy-based command filtering)

### Security Features Supporting Compliance

This tool provides security controls that can support organizations seeking compliance with frameworks like SOC 2, ISO 27001, PCI-DSS, and HIPAA:

**Access Control & Audit**
- Policy enforcement provides least-privilege access
- JSON logs provide non-repudiation and complete audit trails
- All administrative access logged

**Encryption & Network Security**
- SSH provides transport encryption
- Ed25519/RSA keys for strong cryptography
- IP allowlists enforce network segmentation

**Secrets Management**
- Docker secrets or environment variables (not hardcoded)
- No persistent credential storage

**Note**: Compliance is ultimately the responsibility of the deploying organization. This tool provides security features that can support compliance efforts but is not itself certified to these standards.

## Security Checklist

**Before Production Deployment:**

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

**Do not open public issues for security vulnerabilities.**

Email: security@example.com (replace with your contact)

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

We aim to respond within 48 hours and patch critical issues within 7 days.


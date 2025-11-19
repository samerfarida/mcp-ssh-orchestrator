<div align="center">
  <h1>MCP SSH Orchestrator</h1>
  <img src="assets/logo/logo-v1.png" alt="MCP SSH Orchestrator Logo" width="200" height="200">
  <h1>Zero-Trust SSH Orchestration for AI Assistants</h1>
  <p><strong>Enforce declarative policy-as-code and audited access for Claude Desktop, Cursor, and any MCP-aware client.</strong></p>
  <p>Launch in minutes with Docker + MCP tooling, deny-by-default controls, and hardened SSH key management.</p>
</div>

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-v1.21.1-green.svg)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-success)](https://github.com/samerfarida/mcp-ssh-orchestrator)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/samerfarida/mcp-ssh-orchestrator/badge)](https://scorecard.dev/viewer/?uri=github.com/samerfarida/mcp-ssh-orchestrator)
[![GitHub release](https://img.shields.io/github/v/release/samerfarida/mcp-ssh-orchestrator)](https://github.com/samerfarida/mcp-ssh-orchestrator/releases)
[![GitHub stars](https://img.shields.io/github/stars/samerfarida/mcp-ssh-orchestrator)](https://github.com/samerfarida/mcp-ssh-orchestrator/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/samerfarida/mcp-ssh-orchestrator)](https://github.com/samerfarida/mcp-ssh-orchestrator/network/members)
[![GitHub issues](https://img.shields.io/github/issues/samerfarida/mcp-ssh-orchestrator)](https://github.com/samerfarida/mcp-ssh-orchestrator/issues)
[![GitHub pull-requests](https://img.shields.io/github/issues-pr/samerfarida/mcp-ssh-orchestrator)](https://github.com/samerfarida/mcp-ssh-orchestrator/pulls)
[![GitHub contributors](https://img.shields.io/github/contributors/samerfarida/mcp-ssh-orchestrator)](https://github.com/samerfarida/mcp-ssh-orchestrator/graphs/contributors)
[![GitHub last commit](https://img.shields.io/github/last-commit/samerfarida/mcp-ssh-orchestrator)](https://github.com/samerfarida/mcp-ssh-orchestrator/commits/main)
[![GitHub Actions](https://img.shields.io/github/actions/workflow/status/samerfarida/mcp-ssh-orchestrator/build.yml?branch=main&label=Build)](https://github.com/samerfarida/mcp-ssh-orchestrator/actions)
[![CodeQL Analysis](https://github.com/samerfarida/mcp-ssh-orchestrator/actions/workflows/codeql.yml/badge.svg)](https://github.com/samerfarida/mcp-ssh-orchestrator/actions/workflows/codeql.yml)

---

<div align="center">
  <img src="assets/demo.gif" alt="MCP SSH Orchestrator Demo">
</div>

## What Problem Does This Solve?

**Imagine this:** Your AI assistant (Claude, ChatGPT, etc.) can access your servers, but you're terrified of what it might do. `rm -rf /`? Delete your databases? Change firewall rules?

**Now imagine this:** Your AI has governed, auditable access to your infrastructure. It can check logs, restart services, and manage your fleet, **but only if your security policies allow it.**

That's exactly what MCP SSH Orchestrator provides: **the power of AI-driven server management with deny-by-default access control, IP allowlists, host key verification, and comprehensive audit logging backed by declarative YAML policy-as-code (`config/servers.yml`, `config/credentials.yml`, `config/policy.yml`)**.

## Why This Matters

### Zero-Trust Security Model

- **Deny-by-default**: Nothing runs unless explicitly allowed
- **Network controls**: IP allowlists prevent lateral movement
- **Command whitelisting**: Only approved commands can execute
- **Declarative policy-as-code**: Versioned YAML files define hosts, credentials, and allowed commands
- **Comprehensive audit trails**: Every action is logged in JSON

### Prevents Common Attack Vectors

- **Dangerous commands blocked**: `rm -rf`, `dd`, file deletions
- **Network isolation**: Servers can't access external internet
- **No privilege escalation**: Runs as non-root in containers
- **Resource limits**: CPU and memory caps prevent DOS

### Production-Ready Audit & Security

- **OWASP LLM Top 10 protected**: Mitigates LLM07 (Insecure Plugin Design), LLM08 (Excessive Agency), LLM01 (Prompt Injection)
- **MITRE ATT&CK aligned**: Prevents T1071 (Application Layer Protocol), T1659 (Content Injection)
- **Structured JSON audit logs**: Complete audit trail with timestamps, hashes, and IPs
- **Forensics ready**: Command hashing, IP tracking, detailed metadata
- **Real-time monitoring**: Progress logs for long-running tasks

## Who Is This For?

### Homelab Enthusiasts

- Automate routine server maintenance with AI
- Safely manage Proxmox, TrueNAS, Docker hosts
- Get help troubleshooting without losing SSH security

### Security Engineers

- Audit and control AI access to infrastructure
- Implement zero-trust principles with declarative policy-as-code configs
- Meet compliance requirements with structured logging

### DevOps Teams

- Let AI handle routine tasks: log checks, service restarts, updates
- Manage fleets of servers through conversational interface
- Reduce manual toil while maintaining security standards

### Platform Engineers

- Enable AI-powered infrastructure management
- Provide secure self-service access to developers
- Bridge the gap between AI and infrastructure securely

## Real-World Use Cases

### Scenario 1: Homelab Automation (Homelab Enthusiasts)

**You say:** *"Claude, my Proxmox host is running slow. Can you check disk usage and memory on all my VMs?"*

**What happens:**

- Policy allows `df -h` and `free -m` on Proxmox hosts
- Network check: Private IP allowlist permits access
- Tag-based execution checks all hosts tagged `proxmox`
- Commands execute safely with no destructive operations
- Complete audit trail stored in JSON logs

### Scenario 2: Incident Response (DevOps Teams)

**You say:** *"We're seeing 500 errors. Check nginx logs across all production web servers and show me the last 100 error lines."*

**What happens:**

- Tag-based execution: `tail -n 100 /var/log/nginx/error.log` runs on all `web-prod` servers
- Network isolation enforced: No external API calls or egress allowed
- Real-time progress logs stream via MCP context events
- Structured output aggregates results for quick triage
- Full audit trail with timestamps for post-incident review

### Scenario 3: Fleet-Wide Maintenance (Platform Engineers)

**You say:** *"Update system packages on all staging servers, but show me what would change first before running the upgrade."*

**What happens:**

- Use `ssh_plan` to preview `apt list --upgradable` across `staging` tagged hosts
- Review dry-run output to see pending updates
- Policy validates `apt update && apt upgrade -y` is allowed on staging
- Tag-based execution runs upgrade on all staging servers in parallel
- Audit logs track which servers were updated and when

## Quick Start

### 1. Prepare local configuration (one-time)

```bash
# Optional: bootstrap everything with the compose helper script
# (runs from the repo root or from your target config directory)
./compose/setup.sh enduser

# Or download it separately
curl -fsSLO https://raw.githubusercontent.com/samerfarida/mcp-ssh-orchestrator/main/compose/setup.sh
chmod +x setup.sh
./setup.sh enduser
```

If you prefer to lay things out manually, follow the steps below.

```bash
# Pull the latest release
docker pull ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

# Create directories for config, keys, and secrets
mkdir -p ~/mcp-ssh/{config,keys,secrets}

# Copy example configs to get started quickly
cp examples/example-servers.yml ~/mcp-ssh/config/servers.yml
cp examples/example-credentials.yml ~/mcp-ssh/config/credentials.yml
cp examples/example-policy.yml ~/mcp-ssh/config/policy.yml

# Add your SSH key (replace with your private key file)
cp ~/.ssh/id_ed25519 ~/mcp-ssh/keys/
chmod 0400 ~/mcp-ssh/keys/id_ed25519

# (Optional) Pin trusted hosts and prepare secret files
cp ~/.ssh/known_hosts ~/mcp-ssh/keys/known_hosts

# Option 1: Individual secret files (Docker secrets compatible)
cat > ~/mcp-ssh/secrets/prod_db_password.txt <<'EOF'
CHANGE-ME
EOF
chmod 600 ~/mcp-ssh/secrets/prod_db_password.txt

# Option 2: Consolidated .env file (recommended for easier management)
cat > ~/mcp-ssh/secrets/.env <<'EOF'
# SSH Passwords
prod_db_password=CHANGE-ME
lab_password=CHANGE-ME-TOO

# SSH Key Passphrases
prod_key_passphrase=CHANGE-ME-PASSPHRASE
EOF
chmod 600 ~/mcp-ssh/secrets/.env
# Note: .env file supports KEY=value format, comments, and quoted values
# See docs/wiki/06.2-credentials.yml.md for details
```

### 2. Launch the orchestrator container

```bash
docker run -d --name mcp-ssh-orchestrator \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  -v ~/mcp-ssh/secrets:/app/secrets:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

Restart later with `docker start mcp-ssh-orchestrator`. Prefer disposable containers? Use `docker run -i --rm ...` instead.

### 3. Connect your MCP client

- **Cursor:** Add to `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "mcp-ssh-orchestrator": {
      "command": "docker",
      "args": ["start", "-a", "mcp-ssh-orchestrator"],
      "env": {"PYTHONUNBUFFERED": "1"}
    }
  }
}
```

- **Claude Desktop (macOS):** Update `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ssh-orchestrator": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/config:/app/config:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/keys:/app/keys:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/secrets:/app/secrets:ro",
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:latest"
      ]
    }
  }
}
```

(Windows path: `%APPDATA%\\Claude\\claude_desktop_config.json`.)

More examples (Docker Desktop, multi-environment, SDK usage) live in the [Integrations guide](docs/wiki/10-Integrations.md).

### 4. Test the connection

```bash
# List configured hosts through the MCP server
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_list_hosts","arguments":{}},"id":1}' | \
  docker run -i --rm \
    -v ~/mcp-ssh/config:/app/config:ro \
    -v ~/mcp-ssh/keys:/app/keys:ro \
    -v ~/mcp-ssh/secrets:/app/secrets:ro \
    ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

Cursor/Claude should now show the orchestrator as connected. Jump to the [Usage Cookbook](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/08-Usage-Cookbook) for guided scenarios.

## How Security Works (The Technical Details)

**Policy-as-code workflow:** `config/servers.yml`, `config/credentials.yml`, and `config/policy.yml` are parsed on startup, enforced during every `ssh_*` tool invocation, and mirrored in the structured audit logs so the same declarative files you review in Git gate what your AI can execute.

### Defense-in-Depth Architecture

```mermaid
graph TB
    subgraph "Layer 1: Transport Security"
        L1A[stdio Communication]
        L1B[Container Isolation]
    end
    subgraph "Layer 2: Network Security"
        L2A[IP Allowlists]
        L2B[Host Key Verification]
    end
    subgraph "Layer 3: Policy Security"
        L3A[Deny-by-Default]
        L3B[Pattern Matching]
    end
    subgraph "Layer 4: Application Security"
        L4A[Non-Root Execution]
        L4B[Resource Limits]
    end

    L1A --> L2A
    L1B --> L2B
    L2A --> L3A
    L2B --> L3B
    L3A --> L4A
    L3B --> L4B

    style L1A fill:#e1f5ff
    style L1B fill:#e1f5ff
    style L2A fill:#d4edda
    style L2B fill:#d4edda
    style L3A fill:#fff3cd
    style L3B fill:#fff3cd
    style L4A fill:#f8d7da
    style L4B fill:#f8d7da
```

### What Gets Blocked

```yaml
# Dangerous commands automatically denied
deny_substrings:
# Destructive operations
  - "rm -rf /"
  - ":(){ :|:& };:"
  - "mkfs "
  - "dd if=/dev/zero"
  - "shutdown -h"
  - "reboot"
  - "userdel "
  - "passwd "
# Lateral movement / egress tools
  - "ssh "
  - "scp "
  - "rsync -e ssh"
  - "curl "
  - "wget "
  - "nc "
  - "nmap "
  - "telnet "
  - "kubectl "
  - "aws "
  - "gcloud "
  - "az "

# Network isolation enforced
network:
  - allow: ["10.0.0.0/8"]  # Only private IPs
  - deny: ["0.0.0.0/0"]     # No public internet access

```

### What Gets Allowed (Examples)

```yaml
# Safe, read-only commands
rules:
  - action: "allow"
    aliases:
      - "*"
    tags:
      - "observability"
    commands:
      - "uptime*"
      - "df -h*"
      - "free -m*"

# Log inspection (safe)
  - action: "allow"
    aliases:
      - "*"
    tags:
      - "observability"
    commands:
      - "tail -n 200 /var/log/*"
      - "grep -n */var/log/*"
      - "journalctl --no-pager -n 100 *"

# Service management (controlled)
  - action: "allow"
    aliases:
      - "web-*"
      - "db-*"
    tags:
      - "production"
      - "critical-service"
    commands:
      - "systemctl restart nginx"
      - "systemctl status nginx"
      - "systemctl status postgresql"
```

### Protection Against Real Threats

MCP SSH Orchestrator directly addresses documented vulnerabilities in the MCP ecosystem:

- **CVE-2025-49596**: Localhost-exposed MCP services → Mitigated with stdio-only transport
- **CVE-2025-6514**: Command injection in MCP servers → Mitigated with policy-based validation
- **43% of MCP servers** have command injection flaws → Zero-trust security model

**[Full Security Model Documentation](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/05-Security-Model)** | **[Security Risks Analysis](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/02-Risks)**

## Documentation

### [Complete Documentation Wiki](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki)

| Section | What You'll Learn |
|---------|-------------------|
| **[Quick Start & Examples](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/08-Usage-Cookbook)** | Practical examples and common workflows |
| **[Architecture](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/04-Architecture)** | How it works under the hood |
| **[Security Model](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/05-Security-Model)** | Zero-trust design and controls |
| **[Configuration](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/06-Configuration)** | Setting up hosts, credentials, policies |
| **[Observability & Audit](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/11-Observability-Audit)** | Logging, monitoring, compliance |
| **[Deployment](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/09-Deployment)** | Production setup guide |

## Supply Chain Integrity

**Signed release artifacts**: Every tarball/zip in GitHub Releases ships with a detached GPG signature produced by the maintainer key (`openpgp4fpr:6775BF3F439A2A8A198DE10D4FC5342A979BD358`). Import the key and verify before unpacking:

```bash
gpg --receive-keys 4FC5342A979BD358
gpg --verify mcp-ssh-orchestrator-v1.0.0.tar.gz.asc mcp-ssh-orchestrator-v1.0.0.tar.gz
```

**Cosign-signed container images**: The images under `ghcr.io/samerfarida/mcp-ssh-orchestrator` are signed via Sigstore keyless signing in the release workflow. Verify the signature (and optional attestations) before deploying:

```bash
COSIGN_EXPERIMENTAL=1 cosign verify \
  --certificate-identity-regexp "https://github.com/samerfarida/mcp-ssh-orchestrator/.github/workflows/release.yml@.*" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

Image digests and signatures are published with every tag in GitHub Packages so you can pin exact references when promoting builds between environments ([package feed](https://github.com/samerfarida/mcp-ssh-orchestrator/pkgs/container/mcp-ssh-orchestrator/versions)).

**OpenSSF Scorecard**: The repository maintains an automated Scorecard run to track security posture across dependencies, build settings, branch protections, and more ([scorecard summary](https://api.scorecard.dev/projects/github.com/samerfarida/mcp-ssh-orchestrator)).

## What Can AI Do With This? (MCP Tools)

Your AI assistant gets 13 powerful tools with built-in security:

### Discovery & Planning

- `ssh_list_hosts` - See all available servers
- `ssh_describe_host` - Get host details and tags
- `ssh_plan` - **Test commands before running** (dry-run mode)

### Execution

- `ssh_run` - Execute single command on one server
- `ssh_run_on_tag` - Run command on multiple servers (e.g., all "web" servers)
- `ssh_run_async` - Start long-running tasks in background

### Monitoring & Control

- `ssh_get_task_status` - Check progress of async tasks
- `ssh_get_task_output` - Stream output in real-time
- `ssh_get_task_result` - Get final result when done
- `ssh_cancel` - Stop a running synchronous task safely
- `ssh_cancel_async_task` - Stop a running async task safely

### Management

- `ssh_reload_config` - Update hosts/credentials without restart
- `ssh_ping` - Verify connectivity to a host

### MCP Resources + Context

- `ssh://hosts` – discover sanitized host inventory (alias, tags, description, credential presence)
- `ssh://host/{alias}` – inspect a single host without exposing credentials
- `ssh://host/{alias}/tags` – fetch tag-only view for planning tag executions
- `ssh://host/{alias}/capabilities` – derived policy summary, limits, and sample command allowances per host

**Context-aware logging:** Streams lightweight `ctx.debug` / `ctx.info` events (task start, completion, cancellations) in supported clients for `ssh_run`, `ssh_run_on_tag`, config reloads, and async task polling—all without exposing raw commands or secrets.

**LLM-friendly hints:** Policy/network denials (and `ssh_plan` previews) include helpful hints so assistants automatically retry with `ssh_plan`, consult the orchestrator prompts, **or ask whether a policy/network update is appropriate** instead of looping on blocked commands.

### [Complete Tools Reference with Examples](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/07-Tools-Reference)

## Learn More

### Key Differentiators

- **Production-Ready Security**: OpenSSF Scorecard 7.5+ score
- **Zero-Trust Architecture**: Deny-by-default, allow-by-exception
- **OWASP LLM Top 10 Protected**: Mitigates insecure plugin design, excessive agency, prompt injection
- **MITRE ATT&CK Aligned**: Prevents content injection and unauthorized protocol usage
- **Security-Focused**: Built on security-first principles against real CVEs (CVE-2025-49596, CVE-2025-6514)
- **Easy Integration**: Works with Claude, ChatGPT, and any MCP client
- **Open Source**: Apache 2.0 licensed, community-driven

### What Users Are Saying

> *"Finally, I can let Claude manage my Proxmox cluster without fear!"* - Homelab Admin
>
> *"This is what infrastructure-as-code should have been. Declarative security for AI access."* - Platform Engineer
>
> *"The structured audit logs make incident response so much easier."* - Security Engineer
>

## Contributing

We welcome contributions! See our [Contributing Guide](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/13-Contributing) for:

- Development setup
- Code of conduct
- How to submit PRs
- Architecture decisions

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## Links

- **[GitHub Repository](https://github.com/samerfarida/mcp-ssh-orchestrator)** - Star us on GitHub!
- **[Issue Tracker](https://github.com/samerfarida/mcp-ssh-orchestrator/issues)** - Report bugs or request features
- **[CHANGELOG](CHANGELOG.md)** - Version history and release notes
- **[MCP Specification](https://modelcontextprotocol.io)** - Learn about MCP
- **[Docker MCP Security Guide](https://www.docker.com/blog/mcp-security-explained/)** - Security best practices

---

<div align="center">
  <h3>Ready to give AI secure server access?</h3>
  <p>Start with <a href="https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/08-Usage-Cookbook">our Usage Cookbook</a> →</p>
</div>

# MCP SSH Orchestrator

<div align="center">
  <img src="assets/logo/logo-v1.png" alt="MCP SSH Orchestrator Logo" width="200" height="200">
  <h1>Give AI Secure SSH Access to Your Server Fleet</h1>
  <p><strong>Policy-driven, auditable SSH orchestration for Claude, ChatGPT, and AI assistants</strong></p>
  <p>Let AI manage your infrastructure safely with zero-trust security controls</p>
</div>

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-1.2+-green.svg)](https://modelcontextprotocol.io)
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

**Now imagine this:** Your AI has governed, auditable access to your infrastructure. It can check logs, restart services, and manage your fleet—**but only if your security policies allow it.**

That's exactly what MCP SSH Orchestrator provides: **the power of AI-driven server management with deny-by-default access control, IP allowlists, host key verification, and comprehensive audit logging**.

## Why This Matters

### Zero-Trust Security Model
- **Deny-by-default**: Nothing runs unless explicitly allowed
- **Network controls**: IP allowlists prevent lateral movement
- **Command whitelisting**: Only approved commands can execute
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
- Implement zero-trust principles with policy-as-code
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

### Scenario 1: Homelab Automation
**You say:** *"Claude, my home server is running slow. Can you check the disk usage on my Proxmox host?"*

**What happens:**
- Policy checks: Only `df -h` allowed on that host
- Network check: Proxmox IP is in allowlist
- Command executes safely
- Audit log records the operation

### Scenario 2: Incident Response
**You say:** *"Check nginx logs for errors across all web servers"*

**What happens:**
- Tag-based execution runs `tail -f /var/log/nginx/error.log` on all web servers
- Network-isolated execution (no external access)
- Real-time progress logs show you what's happening
- Complete audit trail for post-incident review

### Scenario 3: Compliance & Auditing
**Your security team needs to know:** *"Who accessed what and when?"*

**What happens:**
- JSON audit logs capture every action with timestamps
- Command hashing preserves privacy while enabling forensics
- IP addresses logged for network compliance
- Easy to parse with `jq` for reporting

## Quick Start

### Using Docker (Recommended)

```bash
# Pull the image
docker pull ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

# Run interactively
docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

**Want to see it in action?** Check out our [Usage Cookbook](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/08-Usage-Cookbook) with real examples!

## How Security Works (The Technical Details)

### Defense-in-Depth Architecture

```
Layer 1: Transport Security    → stdio, container isolation
Layer 2: Network Security      → IP allowlists, host key verification  
Layer 3: Policy Security        → Deny-by-default, pattern matching
Layer 4: Application Security  → Non-root execution, resource limits
```

### What Gets Blocked

```yaml
# Dangerous commands automatically denied
deny_substrings:
  - "rm -rf"
  - "dd if="
  - "mkfs"
  - "fdisk"
  - "> /dev"

# Network isolation enforced
network:
  allow: ["10.0.0.0/8"]  # Only private IPs
  deny: ["0.0.0.0/0"]     # No public internet access
```

### What Gets Allowed (Examples)

```yaml
# Safe, read-only commands
rules:
  - patterns: ["uptime", "df -h", "free -m"]
    action: allow
    
# Log inspection (safe)
  - patterns: ["tail -f", "grep", "journalctl"]
    action: allow
    
# Service management (controlled)
  - patterns: ["systemctl restart"]
    action: allow
    tags: ["web", "db"]  # Only on specific servers
```

### Protection Against Real Threats

MCP SSH Orchestrator directly addresses documented vulnerabilities in the MCP ecosystem:

- **CVE-2025-49596**: Localhost-exposed MCP services → Mitigated with stdio-only transport
- **CVE-2025-6514**: Command injection in MCP servers → Mitigated with policy-based validation
- **43% of MCP servers** have command injection flaws → Zero-trust security model

**[Full Security Model Documentation](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/05-Security-Model)** | **[Security Risks Analysis](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/02-Risks)**

## Documentation

**[Complete Documentation Wiki](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki)**

| Section | What You'll Learn |
|---------|-------------------|
| **[Quick Start & Examples](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/08-Usage-Cookbook)** | Practical examples and common workflows |
| **[Architecture](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/04-Architecture)** | How it works under the hood |
| **[Security Model](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/05-Security-Model)** | Zero-trust design and controls |
| **[Configuration](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/06-Configuration)** | Setting up hosts, credentials, policies |
| **[Observability & Audit](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/11-Observability-Audit)** | Logging, monitoring, compliance |
| **[Deployment](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/09-Deployment)** | Production setup guide |

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
- `ssh_cancel` - Stop a running task safely

### Management
- `ssh_reload_config` - Update hosts/credentials without restart
- `ssh_ping` - Verify connectivity to a host

**[Complete Tools Reference with Examples](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/07-Tools-Reference)**

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

> *"This is what infrastructure-as-code should have been. Declarative security for AI access."* - Platform Engineer

> *"The structured audit logs make incident response so much easier."* - Security Engineer

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
- **[MCP Specification](https://modelcontextprotocol.io)** - Learn about MCP
- **[Docker MCP Security Guide](https://www.docker.com/blog/mcp-security-explained/)** - Security best practices

---

<div align="center">
  <h3>Ready to give AI secure server access?</h3>
  <p>Start with <a href="https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/08-Usage-Cookbook">our Usage Cookbook</a> →</p>
</div>

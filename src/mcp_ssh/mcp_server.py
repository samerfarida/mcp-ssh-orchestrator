import asyncio
import json
import re
import time
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from mcp_ssh.config import Config
from mcp_ssh.policy import Policy
from mcp_ssh.ssh_client import SSHClient
from mcp_ssh.tools.utilities import (
    ASYNC_TASKS,
    TASKS,
    hash_command,
    log_json,
    sanitize_error,
)

# Type alias for tool return values (dict for success, str for errors)
ToolResult = dict[str, Any] | str

mcp = FastMCP()
config = Config()


def _format_task_event(event_type: str, task_id: str, payload: dict) -> str:
    """Return human-readable message for async task events."""
    base = f"task {task_id} {event_type}"
    if payload:
        safe_payload = json.dumps(payload, default=str, separators=(",", ":"))
        return f"{base} {safe_payload}"
    return base


def _build_notification_handler(
    ctx: Context | None,
    loop: asyncio.AbstractEventLoop | None,
) -> Callable[[str, str, dict], None]:
    """Return notification handler that emits MCP-compliant notifications."""
    if ctx is None or loop is None:

        def _log_only(event_type: str, task_id: str, payload: dict) -> None:
            log_json(
                {
                    "level": "info",
                    "msg": "async_task_event",
                    "event_type": event_type,
                    "task_id": task_id,
                    "payload": payload,
                }
            )

        return _log_only

    async def _emit(event_type: str, task_id: str, payload: dict) -> None:
        message = _format_task_event(event_type, task_id, payload)

        if event_type == "progress":
            max_seconds = payload.get("max_seconds")
            elapsed_ms = payload.get("elapsed_ms")
            progress = None
            total = None
            if max_seconds and elapsed_ms is not None:
                total = 100.0
                progress = min(100.0, (elapsed_ms / (max_seconds * 1000)) * 100)
            if progress is not None and total is not None:
                await ctx.report_progress(progress, total, message=message)
            await ctx.debug(message)
        else:
            await ctx.info(message)

    def _handler(event_type: str, task_id: str, payload: dict) -> None:
        async def _invoke() -> None:
            await _emit(event_type, task_id, payload)

        def _schedule() -> None:
            loop.create_task(_invoke())

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            loop.call_soon_threadsafe(_schedule)
        else:
            if running_loop is loop:
                loop.create_task(_invoke())
            else:
                loop.call_soon_threadsafe(_schedule)

    return _handler


def _client_for(alias: str, limits: dict, require_known_host: bool) -> SSHClient:
    """Build SSH client from config and limits."""
    host = config.get_host(alias)
    creds_ref = host.get("credentials", "")
    creds = config.get_credentials(creds_ref) if creds_ref else {}
    known_hosts_path = (config.get_policy() or {}).get("known_hosts_path", "")
    auto_add = bool(limits.get("host_key_auto_add", False))

    # Security: Log deprecation warning if host_key_auto_add is set (CWE-295)
    if auto_add:
        log_json(
            {
                "level": "warn",
                "msg": "deprecation_warning",
                "type": "host_key_policy_deprecated",
                "detail": "host_key_auto_add is deprecated and ignored. Always using RejectPolicy for security.",
                "alias": alias,
                "cwe": "CWE-295",
            }
        )

    # Input validation
    hostname = host.get("host", "").strip()
    if not hostname:
        raise ValueError(f"Host '{alias}' has no hostname configured")

    username = creds.get("username", "").strip()
    if not username:
        if creds_ref:
            raise ValueError(
                f"Host '{alias}' references credentials '{creds_ref}' but no username found"
            )
        else:
            raise ValueError(
                f"Host '{alias}' has no credentials reference and no username configured"
            )

    port = host.get("port", 22)
    try:
        port = int(port)
        if not (1 <= port <= 65535):
            raise ValueError(f"Invalid port {port} for host '{alias}'")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid port '{port}' for host '{alias}'") from e

    # Validate authentication method
    key_path = creds.get("key_path", "").strip()
    password = creds.get("password", "").strip()

    if not key_path and not password:
        raise ValueError(
            f"Host '{alias}' has no authentication method configured (neither key_path nor password)"
        )

    return SSHClient(
        host=hostname,
        username=username,
        port=port,
        key_path=creds.get("key_path", ""),
        password=creds.get("password", ""),
        passphrase=creds.get("passphrase", ""),
        known_hosts_path=known_hosts_path,
        auto_add_host_keys=auto_add,
        require_known_host=require_known_host,
    )


# Input validation constants
MAX_ALIAS_LENGTH = 100
MAX_COMMAND_LENGTH = 10000
MAX_TAG_LENGTH = 50
MAX_TASK_ID_LENGTH = 200


def _validate_alias(alias: str) -> tuple[bool, str]:
    """Validate alias parameter.

    Security: Validates alias format to prevent injection attacks.
    - Length limit: 100 characters
    - Allowed characters: alphanumeric, dash, underscore, dot
    - Cannot be empty

    Args:
        alias: Alias string to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, "")
        If invalid: (False, error_message)
    """
    if not alias or not alias.strip():
        return False, "alias is required"

    alias = alias.strip()

    # Length validation
    if len(alias) > MAX_ALIAS_LENGTH:
        return False, f"alias too long (max {MAX_ALIAS_LENGTH} characters)"

    # Character validation: alphanumeric, dash, underscore, dot only
    if not re.match(r"^[a-zA-Z0-9._-]+$", alias):
        return (
            False,
            "alias contains invalid characters (only alphanumeric, dot, dash, underscore allowed)",
        )

    return True, ""


def _validate_command(command: str) -> tuple[bool, str]:
    """Validate command parameter.

    Security: Validates command format to prevent injection and resource exhaustion.
    - Length limit: 10000 characters
    - Rejects null bytes
    - Rejects control characters (except newline, tab, carriage return)

    Args:
        command: Command string to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, "")
        If invalid: (False, error_message)
    """
    if not command or not command.strip():
        return False, "command is required"

    command = command.strip()

    # Length validation
    if len(command) > MAX_COMMAND_LENGTH:
        return False, f"command too long (max {MAX_COMMAND_LENGTH} characters)"

    # Null byte validation (common injection vector)
    if "\x00" in command:
        log_json(
            {
                "level": "error",
                "msg": "security_event",
                "type": "null_byte_injection_attempt",
                "field": "command",
            }
        )
        return False, "command contains invalid characters (null bytes not allowed)"

    # Control character validation (allow newline, tab, carriage return for legitimate use)
    # Reject other control characters
    for char in command:
        if ord(char) < 32 and char not in ["\n", "\t", "\r"]:
            log_json(
                {
                    "level": "error",
                    "msg": "security_event",
                    "type": "control_character_injection_attempt",
                    "field": "command",
                    "char_code": ord(char),
                }
            )
            return False, "command contains invalid control characters"

    return True, ""


def _validate_tag(tag: str) -> tuple[bool, str]:
    """Validate tag parameter.

    Security: Validates tag format to prevent injection attacks.
    - Length limit: 50 characters
    - Allowed characters: alphanumeric, dash, underscore, dot
    - Cannot be empty

    Args:
        tag: Tag string to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, "")
        If invalid: (False, error_message)
    """
    if not tag or not tag.strip():
        return False, "tag is required"

    tag = tag.strip()

    # Length validation
    if len(tag) > MAX_TAG_LENGTH:
        return False, f"tag too long (max {MAX_TAG_LENGTH} characters)"

    # Character validation: alphanumeric, dash, underscore, dot only
    if not re.match(r"^[a-zA-Z0-9._-]+$", tag):
        return (
            False,
            "tag contains invalid characters (only alphanumeric, dot, dash, underscore allowed)",
        )

    return True, ""


def _validate_task_id(task_id: str) -> tuple[bool, str]:
    """Validate task_id parameter.

    Security: Validates task_id format.
    - Length limit: 200 characters
    - Format validation (expected: alias:hash:timestamp)
    - Cannot be empty

    Args:
        task_id: Task ID string to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, "")
        If invalid: (False, error_message)
    """
    if not task_id or not task_id.strip():
        return False, "task_id is required"

    task_id = task_id.strip()

    # Length validation
    if len(task_id) > MAX_TASK_ID_LENGTH:
        return False, f"task_id too long (max {MAX_TASK_ID_LENGTH} characters)"

    # Format validation: should match pattern alias:hash:timestamp
    # Allow alphanumeric, colon, dash, underscore
    if not re.match(r"^[a-zA-Z0-9:_-]+$", task_id):
        return (
            False,
            "task_id contains invalid characters (only alphanumeric, colon, dash, underscore allowed)",
        )

    return True, ""


def _precheck_network(pol: Policy, hostname: str) -> tuple[bool, str]:
    """Resolve hostname and verify at least one resolved IP is allowed."""
    ips = SSHClient.resolve_ips(hostname)
    if not ips:
        # No resolution: fail closed to be safe.
        return False, "DNS resolution failed"
    for ip in ips:
        if pol.is_ip_allowed(ip):
            return True, ""
    return False, "No resolved IPs allowed by policy.network"


def _sanitize_host_metadata(host: dict) -> dict:
    """Return safe subset of host metadata suitable for resources."""
    sanitized = {
        "alias": str(host.get("alias", "")).strip(),
        "host": str(host.get("host", "")).strip(),
        "port": int(host.get("port", 22) or 22),
        "tags": host.get("tags", []) or [],
        "description": host.get("description", ""),
    }
    # Indicate whether a credentials reference exists without exposing the value
    sanitized["has_credentials_ref"] = bool(str(host.get("credentials", "")).strip())
    return sanitized


def _summarize_limits(limits: dict) -> dict:
    """Summarize execution limits without exposing sensitive deny patterns."""
    summary = {
        "max_seconds": int(limits.get("max_seconds", 60)),
        "max_output_bytes": int(limits.get("max_output_bytes", 1024 * 1024)),
        "require_known_host": True,
        "host_key_auto_add": False,
        "task_result_ttl": int(limits.get("task_result_ttl", 300)),
        "task_progress_interval": int(limits.get("task_progress_interval", 5)),
        "deny_patterns_enabled": bool(limits.get("deny_substrings")),
    }
    return summary


def _probe_policy_capabilities(
    alias: str, tags: list, pol: Policy, probes: list[dict]
) -> list[dict]:
    """Evaluate sample commands to provide high-level capability hints."""
    results = []
    for probe in probes:
        required_tags = probe.get("required_tags") or []
        if required_tags and not any(tag in tags for tag in required_tags):
            continue
        command = probe.get("command", "").strip()
        if not command:
            continue
        results.append(
            {
                "probe": probe.get("id", command),
                "command": command,
                "allowed": bool(pol.is_allowed(alias, tags, command)),
            }
        )
    return results


# Sample probe definitions for capability summaries
_CAPABILITY_PROBES = [
    {"id": "basic_diagnostics", "command": "uptime"},
    {"id": "filesystem_overview", "command": "df -h"},
    {"id": "docker_status", "command": "docker ps", "required_tags": ["docker"]},
]

_POLICY_DENY_HINT = "Hint: Use ssh_plan to inspect allowed commands, review the SSH Orchestrator prompts, or ask if the policy should be updated."
_NETWORK_DENY_HINT = "Hint: Use ssh_plan to review host restrictions, check the SSH Orchestrator prompts, or discuss updating policy/network rules."


def _policy_denied_response(alias: str, command: str, cmd_hash: str) -> dict:
    return {
        "status": "denied",
        "reason": "policy",
        "alias": alias,
        "hash": cmd_hash,
        "command": command,
        "hint": _POLICY_DENY_HINT,
    }


def _network_denied_response(alias: str, hostname: str, detail: str) -> dict:
    return {
        "status": "denied",
        "reason": "network",
        "alias": alias,
        "hostname": hostname,
        "detail": detail,
        "hint": _NETWORK_DENY_HINT,
    }


def _ctx_log(
    ctx: Context | None,
    level: str,
    event: str,
    payload: dict | None = None,
) -> None:
    """Emit lightweight context logs without blocking tool execution."""
    if ctx is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    message_dict = {"event": event}
    if payload:
        message_dict.update(payload)
    message = json.dumps(message_dict, default=str, separators=(",", ":"))

    async def _emit() -> None:
        log_method = getattr(ctx, level, None)
        if not callable(log_method):
            return
        await log_method(message)

    loop.create_task(_emit())


# === PROMPTS ===
@mcp.prompt()
def ssh_orchestrator_usage() -> str:
    """
    Explain how to safely use the SSH orchestration tools.
    This is exposed as a prompt template to MCP clients.
    """
    return """
You are using an SSH Orchestrator that enforces strict security policy.

Available tools:
- ssh_list_hosts: list known hosts and tags
- ssh_describe_host: inspect a single host's configuration
- ssh_plan: dry-run and validate a command against policy
- ssh_run: execute a validated command on a single host
- ssh_run_on_tag: execute on all hosts matching a tag
- ssh_run_async: start long-running jobs, then use:
    - ssh_get_task_status
    - ssh_get_task_output
    - ssh_get_task_result
    - ssh_cancel_async_task

Rules:
1. ALWAYS call ssh_plan before ssh_run / ssh_run_on_tag / ssh_run_async.
2. NEVER attempt to run commands that ssh_plan marks as not allowed.
3. Prefer read-only diagnostics (logs, status) before making changes.
4. Use async flows only for tasks that may legitimately take a long time.

When a user asks you to do something on servers, first restate their goal,
then plan a small, safe sequence of tool calls that respects these rules.
"""


@mcp.prompt()
def ssh_policy_denied_guidance() -> str:
    """
    How the LLM should respond when a command is denied by policy.
    """
    return """
You are using an SSH orchestrator with a strict policy.

When you see that a command is denied by policy (check for JSON response with
status: "denied" and reason: "policy"):

1. DO NOT try to work around the policy.
2. Explain to the user, in plain language, why the command is probably blocked
   (for example: dangerous pattern, not in allowlist, wrong tag, etc.).
3. Ask the user what they want:
   - Do they want to change the policy to allow this *class* of command?
   - Or do they want to adjust the command to fit existing policy?

If the user explicitly wants a policy change:

4. Ask clarifying questions:
   - Which host(s) or tag(s) should this apply to?
   - Should this be permanent or temporary?
5. Propose a minimal, least-privilege YAML snippet for policy.yml that would
   allow this command pattern, using the existing policy structure.

   IMPORTANT - Policy Structure:
   - The policy file uses a `rules:` section (not `allowed_commands:` or `allowed_hashes:`)
   - Each rule has: `action: "allow"`, `aliases: []`, `tags: []`, `commands: []`
   - Command hashes (like "ef72e008f0ca") are internal and NOT user-configurable
   - The config file is `policy.yml` in the config directory (not system paths)

   IMPORTANT - Pattern Matching:
   - The orchestrator uses GLOB patterns (not regex) for command matching.
   - Use `*` for wildcards (e.g., `docker ps*` matches "docker ps", "docker ps -a")
   - Use `?` for single character (e.g., `cat?` matches "cat", "cats" but not "catalog")
   - Do NOT use regex anchors like `^` or `$` (e.g., use `docker node ls*` not `^docker node ls$`)
   - Examples: `docker ps*`, `docker service ls*`, `docker info*`, `systemctl status *`

   Example correct YAML structure:
   ```yaml
   rules:
     - action: "allow"
       aliases: ["docker-prod-*"]  # or ["*"] for all hosts
       tags: ["docker"]  # or [] for all tags
       commands:
         - "docker node ls*"
         - "docker service ls*"
         - "docker info*"
   ```

6. Show ONLY the snippet and clearly label it as a suggestion that a human
   should review and apply manually. Never claim that you applied it yourself.

Always emphasize:
- Policy changes are security-sensitive.
- A human must review and apply any suggested policy changes outside the LLM.
"""


@mcp.prompt()
def ssh_network_denied_guidance() -> str:
    """
    How the LLM should respond when network policy denies a host.
    """
    return """
When a command is denied by network policy (check for JSON response with
status: "denied" and reason: "network"):

1. Tell the user that the orchestrator is blocking connections based on an
   IP/network allowlist, for security.
2. DO NOT suggest bypassing DNS or adding arbitrary IPs.

Ask the user:
- Is this host actually supposed to be reachable by this orchestrator?
- If yes, ask them for:
  - The host's expected IP or CIDR block.
  - Whether this is a prod/non-prod environment.

Then:
- Propose a minimal change to the network allowlist in policy.yml to include
  just that IP or the smallest reasonable CIDR.
- Clearly mark it as a suggestion for a human to review/apply manually.

Never:
- Suggest disabling network checks.
- Suggest broad CIDRs (like 0.0.0.0/0) unless the user explicitly demands it,
  and even then warn strongly about the risk.
"""


@mcp.prompt()
def ssh_missing_host_guidance() -> str:
    """
    What to do when a host alias doesn't exist in servers.yml.
    """
    return """
When the orchestrator reports a missing host alias (for example:
'Host alias not found: <alias>'):

1. Explain that hosts are defined in servers.yml under 'servers.hosts'.
2. Ask the user what this host is:
   - hostname or IP
   - environment (prod, staging, dev)
   - tags it should have
   - which credential entry it should reference (if any)

Then propose a minimal YAML entry like:

servers:
  hosts:
    - alias: <alias>
      host: <hostname_or_ip>
      port: 22
      tags: [<tag1>, <tag2>]
      credentials: <creds_name>

Tell the user:
- 'Add or update this entry in servers.yml, then reload config using the
   ssh_reload_config tool.'
Do NOT claim you modified any files; you only suggest changes.
"""


@mcp.prompt()
def ssh_missing_credentials_guidance() -> str:
    """
    How to handle missing or incomplete credentials entries.
    """
    return """
When a host references credentials that are missing or incomplete, or when
the orchestrator reports that no authentication method is configured:

1. Explain that credentials are defined in credentials.yml under
   'credentials.entries', and secrets may be stored in the secrets dir or env.

2. Ask the user:
   - What username should be used?
   - Will they use an SSH key, a password, or both?
   - If SSH key: the key path (relative within keys dir) and optional passphrase.
   - If password/passphrase should come from a Docker secret or env var.

3. Propose a minimal YAML entry, for example:

credentials:
  entries:
    - name: <creds_name>
      username: <user>
      key_path: <relative_or_absolute_key_path>
      # One of the following:
      password_secret: <secret_name>      # preferred
      # or
      password: <only_if_temporary>

      # Optional:
      key_passphrase_secret: <secret_name>

4. Remind the user:
   - Secret names should be safe, simple identifiers.
   - Secret values live in the secrets directory or environment variables
     (MCP_SSH_SECRET_<NAME>), not inside the YAML file whenever possible.

Tell them to update credentials.yml and then call ssh_reload_config.
"""


@mcp.prompt()
def ssh_config_change_workflow() -> str:
    """
    Global rules for suggesting config changes (servers, credentials, policy).
    """
    return """
You are assisting a user with an SSH orchestrator that reads configuration
from three YAML files:

- servers.yml (host definitions, tags, credentials references)
- credentials.yml (usernames, SSH keys, secrets)
- policy.yml (command and network policy)

Rules:
1. NEVER assume you can directly edit these files.
2. Your job is to:
   - Explain why something failed (missing host, missing creds, policy/network denial).
   - Ask the user whether they want to change config.
   - If yes, propose small, least-privilege YAML snippets they can paste into
     the appropriate file.
   - Remind them to run ssh_reload_config after changing files.

3. For each suggestion:
   - Include ONLY the minimal YAML needed.
   - Clearly label it as a suggestion.
   - Warn about security trade-offs (especially for broad policies or networks).

4. Prefer:
   - password_secret / key_passphrase_secret over inline plaintext passwords.
   - narrow command patterns over broad wildcard allow rules.
   - narrow CIDR ranges over broad ones.

5. IMPORTANT - Policy YAML Structure:
   - Use `rules:` section with `action: "allow"` (NOT `allowed_commands:` or `allowed_hashes:`)
   - Each rule requires: `action`, `aliases`, `tags`, `commands` fields
   - Command hashes are internal tracking only - users configure command patterns, not hashes
   - Config file location: `policy.yml` in the config directory (mounted at `/app/config` in container)

6. IMPORTANT - Pattern Matching:
   - The orchestrator uses GLOB patterns (Python fnmatch), NOT regex.
   - Use `*` for wildcards: `docker ps*` matches "docker ps", "docker ps -a"
   - Use `?` for single character: `cat?` matches "cat", "cats"
   - Do NOT use regex syntax: `^`, `$`, `[0-9]+`, etc. will NOT work
   - Examples of correct glob patterns:
     * `docker ps*` (matches commands starting with "docker ps")
     * `docker service ls*` (matches "docker service ls" and variations)
     * `systemctl status *` (matches systemctl status with any service name)
     * `docker-prod-*` (matches host aliases starting with "docker-prod-")

   Example correct YAML structure:
   ```yaml
   rules:
     - action: "allow"
       aliases: ["docker-prod-*"]
       tags: ["docker"]
       commands:
         - "docker node ls*"
         - "docker service ls*"
   ```

You must always keep the orchestrator's security posture conservative.
"""


# === RESOURCES ===
@mcp.resource(
    "ssh://hosts",
    title="Registered SSH Hosts",
    description="Sanitized inventory of all configured host aliases.",
    mime_type="application/json",
)
def resource_hosts() -> dict:
    """Expose sanitized list of hosts as an MCP resource."""
    try:
        aliases = config.list_hosts()
        hosts: list[dict] = []
        for alias in aliases:
            try:
                host = config.get_host(alias)
            except Exception as inner_exc:  # pragma: no cover - defensive logging
                log_json(
                    {
                        "level": "warn",
                        "msg": "resource_host_lookup_failed",
                        "alias": alias,
                        "error": str(inner_exc),
                    }
                )
                continue
            hosts.append(_sanitize_host_metadata(host))
        return {"count": len(hosts), "hosts": hosts}
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "resource_hosts_error", "error": error_str})
        return {"error": sanitize_error(error_str)}


@mcp.resource(
    "ssh://host/{alias}",
    title="Host Details",
    description="Sanitized configuration for a specific host alias.",
    mime_type="application/json",
)
def resource_host(alias: str = "") -> dict:
    """Expose sanitized host metadata for a specific alias."""
    valid, error_msg = _validate_alias(alias)
    if not valid:
        return {"error": error_msg}

    try:
        host = config.get_host(alias.strip())
        return _sanitize_host_metadata(host)
    except Exception as e:
        error_str = str(e)
        log_json(
            {
                "level": "error",
                "msg": "resource_host_error",
                "alias": alias,
                "error": error_str,
            }
        )
        return {"error": sanitize_error(error_str)}


@mcp.resource(
    "ssh://host/{alias}/tags",
    title="Host Tags",
    description="Tag listing for a host alias.",
    mime_type="application/json",
)
def resource_host_tags(alias: str = "") -> dict:
    """Expose tags for a specific host alias."""
    valid, error_msg = _validate_alias(alias)
    if not valid:
        return {"error": error_msg}
    try:
        tags = config.get_host_tags(alias.strip())
        return {"alias": alias.strip(), "tags": tags}
    except Exception as e:
        error_str = str(e)
        log_json(
            {
                "level": "error",
                "msg": "resource_host_tags_error",
                "alias": alias,
                "error": error_str,
            }
        )
        return {"error": sanitize_error(error_str)}


@mcp.resource(
    "ssh://host/{alias}/capabilities",
    title="Host Capability Summary",
    description="High-level summary of policy-driven execution limits and sample allowances.",
    mime_type="application/json",
)
def resource_host_capabilities(alias: str = "") -> dict:
    """Expose derived execution/network limits without leaking raw policy rules."""
    valid, error_msg = _validate_alias(alias)
    if not valid:
        return {"error": error_msg}

    alias = alias.strip()
    try:
        tags = config.get_host_tags(alias)
        pol = Policy(config.get_policy())
        limits = pol.limits_for(alias, tags)
        policy_probes = _probe_policy_capabilities(alias, tags, pol, _CAPABILITY_PROBES)
        network_cfg = pol.config.get("network", {}) or {}
        summary = {
            "alias": alias,
            "tags": tags,
            "limits": _summarize_limits(limits),
            "policy_probes": policy_probes,
            "network": {
                "require_known_host": True,
                "allowlist_enabled": bool(
                    network_cfg.get("allow_ips") or network_cfg.get("allow_cidrs")
                ),
                "blocklist_enabled": bool(
                    network_cfg.get("block_ips") or network_cfg.get("block_cidrs")
                ),
            },
            "features": {
                "supports_async": True,
                "supports_cancellation": True,
            },
        }
        return summary
    except Exception as e:
        error_str = str(e)
        log_json(
            {
                "level": "error",
                "msg": "resource_host_capabilities_error",
                "alias": alias,
                "error": error_str,
            }
        )
        return {"error": sanitize_error(error_str)}


# === TOOLS ===
@mcp.tool()
def ssh_ping() -> ToolResult:
    """Health check."""
    return {"status": "pong"}


@mcp.tool()
def ssh_list_hosts() -> ToolResult:
    """List configured hosts."""
    try:
        hosts = config.list_hosts()
        return {"hosts": hosts}
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "list_hosts_exception", "error": error_str})
        return f"Error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_describe_host(alias: str = "") -> ToolResult:
    """Return host definition in JSON."""
    try:
        # Input validation
        valid, error_msg = _validate_alias(alias)
        if not valid:
            return f"Error: {error_msg}"

        host = config.get_host(alias)
        return host
    except Exception as e:
        error_str = str(e)
        log_json(
            {"level": "error", "msg": "describe_host_exception", "error": error_str}
        )
        return f"Error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_plan(alias: str = "", command: str = "") -> ToolResult:
    """Show what would be executed and if policy allows."""
    try:
        # Input validation
        valid, error_msg = _validate_alias(alias)
        if not valid:
            return f"Error: {error_msg}"

        valid, error_msg = _validate_command(command)
        if not valid:
            return f"Error: {error_msg}"

        cmd_hash = hash_command(command)
        tags = config.get_host_tags(alias)
        pol = Policy(config.get_policy())
        allowed = pol.is_allowed(alias, tags, command)
        limits = pol.limits_for(alias, tags)
        preview = {
            "alias": alias,
            "command": command,
            "hash": cmd_hash,
            "allowed": allowed,
            "limits": {
                "max_seconds": limits.get("max_seconds", 60),
                "max_output_bytes": limits.get("max_output_bytes", 1024 * 1024),
                "host_key_auto_add": bool(limits.get("host_key_auto_add", False)),
                "require_known_host": bool(limits.get("require_known_host", True)),
            },
        }
        if not allowed:
            # Enhanced error message: identify which command in chain is denied
            denied_cmd = pol.get_denied_command_in_chain(alias, tags, command)
            if denied_cmd and denied_cmd != command:
                # Command chain with denied command
                preview["why"] = f"Policy blocked command in chain: '{denied_cmd}'"
                preview["denied_command"] = denied_cmd
            else:
                # Single command or entire chain denied
                preview["why"] = "Policy blocked this command."
            preview["hint"] = _POLICY_DENY_HINT
        return preview
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "plan_exception", "error": error_str})
        return f"Error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_run(
    alias: str = "", command: str = "", ctx: Context | None = None
) -> ToolResult:
    """Execute SSH command with policy, network checks, progress, timeout, and cancellation."""
    start = time.time()
    cmd_hash = ""
    alias = alias or ""
    try:
        # Input validation
        valid, error_msg = _validate_alias(alias)
        if not valid:
            return f"Error: {error_msg}"

        valid, error_msg = _validate_command(command)
        if not valid:
            return f"Error: {error_msg}"

        # Normalize after validation
        alias = alias.strip()
        command = command.strip()

        host = config.get_host(alias)
        hostname = host.get("host", "")
        cmd_hash = hash_command(command)
        _ctx_log(ctx, "debug", "ssh_run_start", {"alias": alias, "hash": cmd_hash})
        tags = config.get_host_tags(alias)
        pol = Policy(config.get_policy())

        # Command policy
        allowed = pol.is_allowed(alias, tags, command)
        pol.log_decision(alias, cmd_hash, allowed)
        if not allowed:
            return json.dumps(
                _policy_denied_response(alias, command, cmd_hash),
                indent=2,
            )

        # Network precheck (DNS -> allowlist)
        ok, reason = _precheck_network(pol, hostname)
        if not ok:
            return json.dumps(
                _network_denied_response(alias, hostname, reason),
                indent=2,
            )

        limits = pol.limits_for(alias, tags)
        max_seconds = int(limits.get("max_seconds", 60))
        max_output_bytes = int(limits.get("max_output_bytes", 1024 * 1024))
        require_known_host_config = bool(
            limits.get("require_known_host", pol.require_known_host())
        )
        # Security: Always require known_host for security (CWE-295)
        if not require_known_host_config:
            log_json(
                {
                    "level": "warn",
                    "msg": "deprecation_warning",
                    "type": "host_key_policy_deprecated",
                    "detail": "require_known_host=False is deprecated and ignored. Always requiring known_hosts entry for security.",
                    "alias": alias,
                    "cwe": "CWE-295",
                }
            )
        require_known_host = True  # Always enforce strict host key verification

        task_id = TASKS.create(alias, cmd_hash)
        _ctx_log(
            ctx,
            "debug",
            "ssh_run_task_created",
            {"alias": alias, "hash": cmd_hash, "task_id": task_id},
        )

        def progress_cb(phase: str, bytes_read: int, elapsed_ms: int) -> None:
            pol.log_progress(task_id, phase, int(bytes_read), int(elapsed_ms))

        client = _client_for(alias, limits, require_known_host)
        cancel_event = TASKS.get_event(task_id)
        (
            exit_code,
            duration_ms,
            cancelled,
            timeout,
            bytes_out,
            bytes_err,
            combined,
            peer_ip,
        ) = client.run_streaming(
            command=command,
            cancel_event=cancel_event,
            max_seconds=max_seconds,
            max_output_bytes=max_output_bytes,
            progress_cb=progress_cb,
        )
        TASKS.cleanup(task_id)

        # Post-connect enforcement: ensure actual peer IP is allowed
        if peer_ip and not pol.is_ip_allowed(peer_ip):
            pol.log_audit(
                alias,
                cmd_hash,
                int(exit_code),
                int(duration_ms),
                int(bytes_out),
                int(bytes_err),
                bool(cancelled),
                bool(timeout),
                peer_ip,
            )
            return json.dumps(
                _network_denied_response(
                    alias, hostname, f"peer IP {peer_ip} not allowed"
                ),
                indent=2,
            )

        pol.log_audit(
            alias,
            cmd_hash,
            int(exit_code),
            int(duration_ms),
            int(bytes_out),
            int(bytes_err),
            bool(cancelled),
            bool(timeout),
            peer_ip,
        )
        result = {
            "task_id": task_id,
            "alias": alias,
            "hash": cmd_hash,
            "exit_code": int(exit_code),
            "duration_ms": int(duration_ms),
            "cancelled": bool(cancelled),
            "timeout": bool(timeout),
            "target_ip": peer_ip,
            "output": combined,
        }
        _ctx_log(
            ctx,
            "info",
            "ssh_run_complete",
            {
                "alias": alias,
                "hash": cmd_hash,
                "task_id": task_id,
                "exit_code": int(exit_code),
                "timeout": bool(timeout),
                "cancelled": bool(cancelled),
            },
        )
        return result
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "run_exception", "error": error_str})
        if cmd_hash:
            _ctx_log(
                ctx,
                "debug",
                "ssh_run_error",
                {
                    "alias": alias.strip(),
                    "hash": cmd_hash,
                    "error": sanitize_error(error_str),
                },
            )
        return f"Run error: {sanitize_error(error_str)}"
    finally:
        elapsed = int((time.time() - start) * 1000)
        log_json({"type": "trace", "op": "run_done", "elapsed_ms": elapsed})


@mcp.tool()
def ssh_run_on_tag(
    tag: str = "",
    command: str = "",
    ctx: Context | None = None,
) -> ToolResult:
    """Execute SSH command on all hosts with a tag (with network checks)."""
    try:
        # Input validation
        valid, error_msg = _validate_tag(tag)
        if not valid:
            return f"Error: {error_msg}"

        valid, error_msg = _validate_command(command)
        if not valid:
            return f"Error: {error_msg}"

        # Normalize after validation
        tag = tag.strip()
        command = command.strip()
        cmd_hash = hash_command(command)

        aliases = config.find_hosts_by_tag(tag)
        _ctx_log(
            ctx,
            "debug",
            "ssh_run_on_tag_start",
            {"tag": tag, "hash": cmd_hash, "target_count": len(aliases)},
        )
        if not aliases:
            return {"tag": tag, "results": [], "note": "No hosts matched."}

        results = []
        for alias in aliases:
            host = config.get_host(alias)
            hostname = host.get("host", "")
            tags = config.get_host_tags(alias)
            pol = Policy(config.get_policy())

            # Command policy
            allowed = pol.is_allowed(alias, tags, command)
            pol.log_decision(alias, cmd_hash, allowed)
            if not allowed:
                results.append(
                    {
                        "alias": alias,
                        "hash": cmd_hash,
                        "denied": True,
                        "reason": "policy",
                        "hint": _POLICY_DENY_HINT,
                    }
                )
                continue

            # Network precheck
            ok, reason = _precheck_network(pol, hostname)
            if not ok:
                results.append(
                    {
                        "alias": alias,
                        "hash": cmd_hash,
                        "denied": True,
                        "reason": f"network: {reason}",
                        "detail": reason,
                        "hint": _NETWORK_DENY_HINT,
                    }
                )
                continue

            # Wrap SSH connection/execution in try-except for per-host error handling
            task_id = None
            try:
                limits = pol.limits_for(alias, tags)
                max_seconds = int(limits.get("max_seconds", 60))
                max_output_bytes = int(limits.get("max_output_bytes", 1024 * 1024))
                require_known_host_config = bool(
                    limits.get("require_known_host", pol.require_known_host())
                )
                # Security: Always require known_host for security (CWE-295)
                if not require_known_host_config:
                    log_json(
                        {
                            "level": "warn",
                            "msg": "deprecation_warning",
                            "type": "host_key_policy_deprecated",
                            "detail": "require_known_host=False is deprecated and ignored. Always requiring known_hosts entry for security.",
                            "alias": alias,
                            "cwe": "CWE-295",
                        }
                    )
                require_known_host = True  # Always enforce strict host key verification

                task_id = TASKS.create(alias, cmd_hash)

                def progress_cb(
                    phase: str,
                    bytes_read: int,
                    elapsed_ms: int,
                    pol_ref: Policy = pol,
                    task_ref: str = task_id,
                ) -> None:
                    pol_ref.log_progress(
                        task_ref, phase, int(bytes_read), int(elapsed_ms)
                    )

                client = _client_for(alias, limits, require_known_host)
                cancel_event = TASKS.get_event(task_id)
                (
                    exit_code,
                    duration_ms,
                    cancelled,
                    timeout,
                    bytes_out,
                    bytes_err,
                    combined,
                    peer_ip,
                ) = client.run_streaming(
                    command=command,
                    cancel_event=cancel_event,
                    max_seconds=max_seconds,
                    max_output_bytes=max_output_bytes,
                    progress_cb=progress_cb,
                )
                TASKS.cleanup(task_id)

                # Post-connect enforcement
                if peer_ip and not pol.is_ip_allowed(peer_ip):
                    pol.log_audit(
                        alias,
                        cmd_hash,
                        int(exit_code),
                        int(duration_ms),
                        int(bytes_out),
                        int(bytes_err),
                        bool(cancelled),
                        bool(timeout),
                        peer_ip,
                    )
                    results.append(
                        {
                            "alias": alias,
                            "task_id": task_id,
                            "hash": cmd_hash,
                            "denied": True,
                            "reason": f"network: peer {peer_ip} not allowed",
                            "detail": f"peer {peer_ip} not allowed",
                            "hint": _NETWORK_DENY_HINT,
                        }
                    )
                    continue

                pol.log_audit(
                    alias,
                    cmd_hash,
                    int(exit_code),
                    int(duration_ms),
                    int(bytes_out),
                    int(bytes_err),
                    bool(cancelled),
                    bool(timeout),
                    peer_ip,
                )
                results.append(
                    {
                        "alias": alias,
                        "task_id": task_id,
                        "hash": cmd_hash,
                        "exit_code": int(exit_code),
                        "duration_ms": int(duration_ms),
                        "cancelled": bool(cancelled),
                        "timeout": bool(timeout),
                        "target_ip": peer_ip,
                        "output": combined,
                    }
                )
            except Exception as e:
                # Handle per-host failures gracefully
                error_str = str(e)
                log_json(
                    {
                        "level": "error",
                        "msg": "run_on_tag_host_failed",
                        "alias": alias,
                        "error": error_str,
                    }
                )

                # Clean up task if it was created
                if task_id:
                    try:
                        TASKS.cleanup(task_id)
                    except Exception:
                        pass

                # Add error result for this host
                results.append(
                    {
                        "alias": alias,
                        "task_id": task_id if task_id else "",
                        "hash": cmd_hash,
                        "exit_code": -1,
                        "duration_ms": 0,
                        "cancelled": False,
                        "timeout": False,
                        "target_ip": "",
                        "output": sanitize_error(error_str),
                    }
                )
                continue  # Continue with next host

        summary = {
            "tag": tag,
            "results": results,
        }
        _ctx_log(
            ctx,
            "info",
            "ssh_run_on_tag_complete",
            {
                "tag": tag,
                "hash": cmd_hash,
                "target_count": len(aliases),
                "succeeded": sum(1 for r in results if not r.get("denied")),
            },
        )
        return summary
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "run_on_tag_exception", "error": error_str})
        _ctx_log(
            ctx,
            "debug",
            "ssh_run_on_tag_error",
            {"tag": tag.strip(), "error": sanitize_error(error_str)},
        )
        return f"Run on tag error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_cancel(task_id: str = "", ctx: Context | None = None) -> ToolResult:
    """Request cancellation for a running task."""
    try:
        # Input validation
        valid, error_msg = _validate_task_id(task_id)
        if not valid:
            return f"Error: {error_msg}"

        task_id = task_id.strip()
        ok = TASKS.cancel(task_id)
        response = {
            "task_id": task_id,
            "cancelled": bool(ok),
            "message": "Cancellation signaled" if ok else "Task not found",
        }
        _ctx_log(
            ctx,
            "info",
            "ssh_cancel",
            {"task_id": task_id, "cancelled": bool(ok)},
        )
        return response
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "cancel_exception", "error": error_str})
        _ctx_log(
            ctx,
            "debug",
            "ssh_cancel_error",
            {"task_id": task_id.strip(), "error": sanitize_error(error_str)},
        )
        return f"Cancel error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_reload_config(ctx: Context | None = None) -> ToolResult:
    """Reload configuration files."""
    try:
        config.reload()
        _ctx_log(ctx, "info", "ssh_reload_config", {"status": "reloaded"})
        return {"status": "reloaded"}
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "reload_exception", "error": error_str})
        _ctx_log(
            ctx,
            "debug",
            "ssh_reload_config_error",
            {"error": sanitize_error(error_str)},
        )
        return {"status": "error", "error": sanitize_error(error_str)}


@mcp.tool()
async def ssh_run_async(
    alias: str = "", command: str = "", ctx: Context | None = None
) -> ToolResult:
    """Start SSH command asynchronously (SEP-1686 compliant).

    Returns immediately with task_id for polling. Use ssh_get_task_status
    and ssh_get_task_result to monitor and retrieve results.
    """
    try:
        # Input validation
        valid, error_msg = _validate_alias(alias)
        if not valid:
            return f"Error: {error_msg}"

        valid, error_msg = _validate_command(command)
        if not valid:
            return f"Error: {error_msg}"

        # Normalize after validation
        alias = alias.strip()
        command = command.strip()

        host = config.get_host(alias)
        hostname = host.get("host", "")
        cmd_hash = hash_command(command)
        tags = config.get_host_tags(alias)
        pol = Policy(config.get_policy())

        # Command policy
        allowed = pol.is_allowed(alias, tags, command)
        pol.log_decision(alias, cmd_hash, allowed)
        if not allowed:
            return json.dumps(
                _policy_denied_response(alias, command, cmd_hash),
                indent=2,
            )

        # Network precheck (DNS -> allowlist)
        ok, reason = _precheck_network(pol, hostname)
        if not ok:
            return json.dumps(
                _network_denied_response(alias, hostname, reason),
                indent=2,
            )

        limits = pol.limits_for(alias, tags)
        require_known_host_config = bool(
            limits.get("require_known_host", pol.require_known_host())
        )
        # Security: Always require known_host for security (CWE-295)
        if not require_known_host_config:
            log_json(
                {
                    "level": "warn",
                    "msg": "deprecation_warning",
                    "type": "host_key_policy_deprecated",
                    "detail": "require_known_host=False is deprecated and ignored. Always requiring known_hosts entry for security.",
                    "alias": alias,
                    "cwe": "CWE-295",
                }
            )
        require_known_host = True  # Always enforce strict host key verification

        # Create SSH client
        client = _client_for(alias, limits, require_known_host)

        # Enhanced progress callback for async tasks
        def progress_cb(phase: str, bytes_read: int, elapsed_ms: int) -> None:
            pol.log_progress(
                f"async:{alias}:{cmd_hash}", phase, int(bytes_read), int(elapsed_ms)
            )

        current_loop: asyncio.AbstractEventLoop | None = None
        if ctx is not None:
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

        notification_handler = _build_notification_handler(ctx, current_loop)

        # Start async task
        task_id = ASYNC_TASKS.start_async_task(
            alias=alias,
            command=command,
            ssh_client=client,
            limits=limits,
            progress_cb=progress_cb,
            notification_handler=notification_handler,
        )

        # Return SEP-1686 compliant response
        result = {
            "task_id": task_id,
            "status": "pending",
            "keepAlive": int(limits.get("task_result_ttl", 300)),
            "pollFrequency": int(limits.get("task_progress_interval", 5)),
            "alias": alias,
            "command": command,
            "hash": cmd_hash,
        }
        return result

    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "async_run_exception", "error": error_str})
        return f"Async run error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_get_task_status(task_id: str = "", ctx: Context | None = None) -> ToolResult:
    """Get current status of an async task (SEP-1686 compliant).

    Returns task state, progress, elapsed time, and output summary.
    """
    try:
        # Input validation
        valid, error_msg = _validate_task_id(task_id)
        if not valid:
            return f"Error: {error_msg}"

        task_id = task_id.strip()
        status = ASYNC_TASKS.get_task_status(task_id)
        if not status:
            return f"Error: Task not found: {task_id}"

        _ctx_log(ctx, "debug", "ssh_get_task_status", {"task_id": task_id})
        return status

    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "status_exception", "error": error_str})
        _ctx_log(
            ctx,
            "debug",
            "ssh_get_task_status_error",
            {"task_id": task_id.strip(), "error": sanitize_error(error_str)},
        )
        return f"Status error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_get_task_result(task_id: str = "", ctx: Context | None = None) -> ToolResult:
    """Get final result of completed task (SEP-1686 compliant).

    Returns complete output, exit code, and execution metadata.
    """
    try:
        # Input validation
        valid, error_msg = _validate_task_id(task_id)
        if not valid:
            return f"Error: {error_msg}"

        task_id = task_id.strip()
        result = ASYNC_TASKS.get_task_result(task_id)
        if not result:
            return f"Error: Task not found or expired: {task_id}"

        _ctx_log(ctx, "debug", "ssh_get_task_result", {"task_id": task_id})
        return result

    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "result_exception", "error": error_str})
        _ctx_log(
            ctx,
            "debug",
            "ssh_get_task_result_error",
            {"task_id": task_id.strip(), "error": sanitize_error(error_str)},
        )
        return f"Result error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_get_task_output(
    task_id: str = "", max_lines: int = 50, ctx: Context | None = None
) -> ToolResult:
    """Get recent output lines from running or completed task.

    Enhanced beyond SEP-1686: enables streaming output visibility.
    """
    try:
        # Input validation
        valid, error_msg = _validate_task_id(task_id)
        if not valid:
            return f"Error: {error_msg}"

        if max_lines < 1 or max_lines > 1000:
            return "Error: max_lines must be between 1 and 1000"

        task_id = task_id.strip()
        output = ASYNC_TASKS.get_task_output(task_id, max_lines)
        if not output:
            return f"Error: Task not found or no output available: {task_id}"

        _ctx_log(
            ctx,
            "debug",
            "ssh_get_task_output",
            {"task_id": task_id, "max_lines": max_lines},
        )
        return output

    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "output_exception", "error": error_str})
        _ctx_log(
            ctx,
            "debug",
            "ssh_get_task_output_error",
            {"task_id": task_id.strip(), "error": sanitize_error(error_str)},
        )
        return f"Output error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_cancel_async_task(task_id: str = "", ctx: Context | None = None) -> ToolResult:
    """Cancel a running async task."""
    try:
        # Input validation
        valid, error_msg = _validate_task_id(task_id)
        if not valid:
            return f"Error: {error_msg}"

        task_id = task_id.strip()
        success = ASYNC_TASKS.cancel_task(task_id)
        response = {
            "task_id": task_id,
            "cancelled": bool(success),
            "message": (
                "Cancellation signaled"
                if success
                else "Task not found or not cancellable"
            ),
        }
        _ctx_log(
            ctx,
            "info",
            "ssh_cancel_async_task",
            {"task_id": task_id, "cancelled": bool(success)},
        )
        return response

    except Exception as e:
        error_str = str(e)
        log_json(
            {"level": "error", "msg": "cancel_async_exception", "error": error_str}
        )
        _ctx_log(
            ctx,
            "debug",
            "ssh_cancel_async_task_error",
            {"task_id": task_id.strip(), "error": sanitize_error(error_str)},
        )
        return f"Cancel error: {sanitize_error(error_str)}"


def main() -> None:
    """Main entry point for MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

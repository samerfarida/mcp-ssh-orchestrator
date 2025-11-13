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
        return preview
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "plan_exception", "error": error_str})
        return f"Error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_run(alias: str = "", command: str = "") -> ToolResult:
    """Execute SSH command with policy, network checks, progress, timeout, and cancellation."""
    start = time.time()
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
            return f"Denied by policy: {command}"

        # Network precheck (DNS -> allowlist)
        ok, reason = _precheck_network(pol, hostname)
        if not ok:
            return f"Denied by network policy: {reason}"

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
            return f"Denied by network policy: peer IP {peer_ip} not allowed"

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
        return result
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "run_exception", "error": error_str})
        return f"Run error: {sanitize_error(error_str)}"
    finally:
        elapsed = int((time.time() - start) * 1000)
        log_json({"type": "trace", "op": "run_done", "elapsed_ms": elapsed})


@mcp.tool()
def ssh_run_on_tag(tag: str = "", command: str = "") -> ToolResult:
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

        aliases = config.find_hosts_by_tag(tag)
        if not aliases:
            return {"tag": tag, "results": [], "note": "No hosts matched."}

        results = []
        for alias in aliases:
            host = config.get_host(alias)
            hostname = host.get("host", "")
            cmd_hash = hash_command(command)
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
                    }
                )
                continue

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
                pol_ref.log_progress(task_ref, phase, int(bytes_read), int(elapsed_ms))

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

        return {"tag": tag, "results": results}
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "run_on_tag_exception", "error": error_str})
        return f"Run on tag error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_cancel(task_id: str = "") -> ToolResult:
    """Request cancellation for a running task."""
    try:
        # Input validation
        valid, error_msg = _validate_task_id(task_id)
        if not valid:
            return f"Error: {error_msg}"

        task_id = task_id.strip()
        ok = TASKS.cancel(task_id)
        if ok:
            return {
                "task_id": task_id,
                "cancelled": True,
                "message": "Cancellation signaled",
            }
        return {"task_id": task_id, "cancelled": False, "message": "Task not found"}
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "cancel_exception", "error": error_str})
        return f"Cancel error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_reload_config() -> ToolResult:
    """Reload configuration files."""
    try:
        config.reload()
        return {"status": "reloaded"}
    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "reload_exception", "error": error_str})
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
            return f"Denied by policy: {command}"

        # Network precheck (DNS -> allowlist)
        ok, reason = _precheck_network(pol, hostname)
        if not ok:
            return f"Denied by network policy: {reason}"

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
def ssh_get_task_status(task_id: str = "") -> ToolResult:
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

        return status

    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "status_exception", "error": error_str})
        return f"Status error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_get_task_result(task_id: str = "") -> ToolResult:
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

        return result

    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "result_exception", "error": error_str})
        return f"Result error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_get_task_output(task_id: str = "", max_lines: int = 50) -> ToolResult:
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

        return output

    except Exception as e:
        error_str = str(e)
        log_json({"level": "error", "msg": "output_exception", "error": error_str})
        return f"Output error: {sanitize_error(error_str)}"


@mcp.tool()
def ssh_cancel_async_task(task_id: str = "") -> ToolResult:
    """Cancel a running async task."""
    try:
        # Input validation
        valid, error_msg = _validate_task_id(task_id)
        if not valid:
            return f"Error: {error_msg}"

        task_id = task_id.strip()
        success = ASYNC_TASKS.cancel_task(task_id)
        if success:
            return {
                "task_id": task_id,
                "cancelled": True,
                "message": "Cancellation signaled",
            }
        else:
            return {
                "task_id": task_id,
                "cancelled": False,
                "message": "Task not found or not cancellable",
            }

    except Exception as e:
        error_str = str(e)
        log_json(
            {"level": "error", "msg": "cancel_async_exception", "error": error_str}
        )
        return f"Cancel error: {sanitize_error(error_str)}"


def main() -> None:
    """Main entry point for MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

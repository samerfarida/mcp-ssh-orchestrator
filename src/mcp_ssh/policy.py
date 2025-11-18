import fnmatch
import ipaddress
import json
import re
import sys
import time


def _match_any(value: str, patterns) -> bool:
    """Return True if value matches any glob pattern."""
    if not isinstance(patterns, list):
        return False
    for p in patterns:
        try:
            if fnmatch.fnmatch(value, str(p)):
                return True
        except Exception:
            continue
    return False


def _normalize_command(command: str) -> str:
    """Normalize command to prevent bypass attempts.

    Security: Normalizes command string to detect blocked commands that
    might be obfuscated with quotes, escaping, or whitespace variations.

    Args:
        command: Original command string

    Returns:
        Normalized command string for pattern matching
    """
    if not command:
        return ""

    normalized = command

    # Remove single and double quotes (common bypass technique)
    # Example: 'rm -rf /' or "rm -rf /" -> rm -rf /
    normalized = re.sub(r"['\"]", "", normalized)

    # Remove escaped characters (convert \n to space, \t to space, etc.)
    # Example: rm\ -rf\ / -> rm -rf /
    normalized = re.sub(r"\\(.)", r"\1", normalized)

    # Normalize whitespace: collapse multiple spaces/tabs to single space
    normalized = re.sub(r"\s+", " ", normalized)

    # Remove leading/trailing whitespace
    normalized = normalized.strip()

    return normalized


def _parse_command_chain(command: str) -> list[str]:
    """Parse command chain and extract individual commands.

    Security: Extracts individual commands from chained commands to validate
    each command separately, preventing policy bypass via command chaining.

    Handles:
    - Chaining operators: &&, ||, ;, |
    - Command substitution: `cmd`, $(cmd)
    - Parentheses grouping: (cmd1 || cmd2)
    - Nested structures

    Args:
        command: Command string that may contain chaining operators

    Returns:
        List of individual command strings (normalized, without operators)
        Returns single-item list if no chaining detected

    Example:
        "uptime && whoami" -> ["uptime", "whoami"]
        "echo $(whoami)" -> ["echo $(whoami)"]  # Substitution kept for validation
    """
    if not command or not command.strip():
        return []

    # Fast path: check if command contains chaining operators
    # This avoids expensive parsing for simple commands
    has_chaining = bool(
        re.search(r"[&|;]\s*[&|]|;\s*[^;]|\|\s*[^|]", command)
        or "`" in command
        or "$(" in command
    )

    if not has_chaining:
        # No chaining detected, return single command
        return [command.strip()]

    # Parse command chain
    commands = []
    current_command = ""
    i = 0
    in_single_quote = False
    in_double_quote = False
    in_backtick = False
    in_dollar_paren = False
    paren_depth = 0
    backtick_depth = 0
    dollar_paren_depth = 0

    while i < len(command):
        char = command[i]
        next_char = command[i + 1] if i + 1 < len(command) else ""

        # Handle quotes (they can contain operators)
        if (
            char == "'"
            and not in_double_quote
            and not in_backtick
            and not in_dollar_paren
        ):
            in_single_quote = not in_single_quote
            current_command += char
            i += 1
            continue

        if (
            char == '"'
            and not in_single_quote
            and not in_backtick
            and not in_dollar_paren
        ):
            in_double_quote = not in_double_quote
            current_command += char
            i += 1
            continue

        # Handle backtick command substitution
        if char == "`" and not in_single_quote and not in_double_quote:
            if not in_backtick:
                in_backtick = True
                backtick_depth += 1
            else:
                backtick_depth -= 1
                if backtick_depth == 0:
                    in_backtick = False
            current_command += char
            i += 1
            continue

        # Handle $(command) substitution
        if (
            char == "$"
            and next_char == "("
            and not in_single_quote
            and not in_double_quote
            and not in_backtick
        ):
            in_dollar_paren = True
            dollar_paren_depth = 1
            current_command += char + next_char
            i += 2
            continue

        if char == "(" and in_dollar_paren:
            dollar_paren_depth += 1
            current_command += char
            i += 1
            continue

        if char == ")" and in_dollar_paren:
            dollar_paren_depth -= 1
            current_command += char
            if dollar_paren_depth == 0:
                in_dollar_paren = False
            i += 1
            continue

        # Handle grouping parentheses (outside substitutions)
        if (
            char == "("
            and not in_single_quote
            and not in_double_quote
            and not in_backtick
            and not in_dollar_paren
        ):
            paren_depth += 1
            current_command += char
            i += 1
            continue

        if (
            char == ")"
            and not in_single_quote
            and not in_double_quote
            and not in_backtick
            and not in_dollar_paren
        ):
            paren_depth -= 1
            current_command += char
            i += 1
            continue

        # Only process chaining operators outside quotes and substitutions
        if (
            not in_single_quote
            and not in_double_quote
            and not in_backtick
            and not in_dollar_paren
            and paren_depth == 0
        ):
            # Check for && operator
            if char == "&" and next_char == "&":
                # Save current command if non-empty
                cmd = current_command.strip()
                if cmd:
                    commands.append(cmd)
                current_command = ""
                i += 2
                continue

            # Check for || operator
            if char == "|" and next_char == "|":
                cmd = current_command.strip()
                if cmd:
                    commands.append(cmd)
                current_command = ""
                i += 2
                continue

            # Check for ; operator
            if char == ";":
                cmd = current_command.strip()
                if cmd:
                    commands.append(cmd)
                current_command = ""
                i += 1
                continue

            # Check for | operator (pipe)
            if char == "|":
                cmd = current_command.strip()
                if cmd:
                    commands.append(cmd)
                current_command = ""
                i += 1
                continue

        # Regular character, add to current command
        current_command += char
        i += 1

    # Add final command
    cmd = current_command.strip()
    if cmd:
        commands.append(cmd)

    # If parsing failed or produced no commands, return original as single command
    if not commands:
        return [command.strip()]

    return commands


class Policy:
    """Policy engine for allow/deny with limits and network controls."""

    def __init__(self, config: dict):
        self.config = config or {}
        # Command/exec defaults (safe but overridable via policy.yml)
        self.default_limits = {
            "max_seconds": 60,
            "max_output_bytes": 1024 * 1024,
            "host_key_auto_add": False,  # Deprecated: ignored for security (CWE-295)
            "require_known_host": True,  # Security: always enforced, prevents MITM attacks
            "task_result_ttl": 300,  # 5 minutes default (SEP-1686 keepAlive)
            "task_progress_interval": 5,  # 5 seconds default
            # Expanded egress hardening defaults (can be overridden in policy.yml)
            "deny_substrings": [
                "rm -rf /",
                ":(){ :|:& };:",
                "mkfs ",
                "dd if=/dev/zero",
                "shutdown -h",
                "reboot",
                "userdel ",
                "passwd ",
                # Egress / lateral movement helpers
                "ssh ",
                "scp ",
                "rsync -e ssh",
                "curl ",
                "wget ",
                "nc ",
                "nmap ",
                "telnet ",
                "kubectl ",
                "aws ",
                "gcloud ",
                "az ",
            ],
        }

    # ----------------------------
    # Limits / Allow-Deny (commands)
    # ----------------------------
    def _collect_limits(self, alias: str, tags):
        """Resolve limits for alias and tags."""
        limits = dict(self.default_limits)
        pol = self.config or {}
        gl = pol.get("limits", {})
        for k, v in gl.items():
            limits[k] = v
        overrides = pol.get("overrides", {})
        alias_over = overrides.get("aliases", {}).get(alias, {})
        for k, v in alias_over.items():
            limits[k] = v
        if isinstance(tags, list):
            tag_over = overrides.get("tags", {})
            for t in tags:
                tv = tag_over.get(t, {})
                for k, v in tv.items():
                    # Tag overrides should only apply if not already set by alias
                    if k not in alias_over:
                        limits[k] = v
        return limits

    def limits_for(self, alias: str, tags):
        """Return effective limits for alias."""
        return self._collect_limits(alias, tags)

    def is_allowed(self, alias: str, tags, command: str) -> bool:
        """Return True if command is allowed by rules + deny substrings.

        Security: Enhanced with command normalization and chain parsing to prevent
        bypass attempts via quotes, escaping, whitespace variations, and command chaining.

        For chained commands, validates each command individually. Returns True only
        if ALL commands in the chain are allowed.
        """
        pol = self.config or {}
        deny_substrings = self._collect_limits(alias, tags).get("deny_substrings", [])

        # Parse command chain to extract individual commands
        # This prevents policy bypass via command chaining operators
        parsed_commands = _parse_command_chain(command)

        # If parsing produced multiple commands, validate each individually
        if len(parsed_commands) > 1:
            # Log chain parsing for security audit
            self._log_chain_parsing(alias, command, parsed_commands)

            # Validate each command in the chain
            for cmd in parsed_commands:
                if not self._is_single_command_allowed(
                    alias, tags, cmd, deny_substrings, pol
                ):
                    # Log which command in chain caused denial
                    self._log_chain_denial(alias, command, cmd, parsed_commands)
                    return False
            # All commands allowed
            return True

        # Single command (no chaining) - use existing validation logic
        return self._is_single_command_allowed(
            alias, tags, command, deny_substrings, pol
        )

    def get_denied_command_in_chain(self, alias: str, tags, command: str) -> str | None:
        """Identify which command in a chain is denied.

        Returns the denied command string if found, None if all commands are allowed.
        Useful for providing specific error messages.

        Args:
            alias: Host alias
            tags: Host tags
            command: Command string that may contain chaining

        Returns:
            Denied command string, or None if all commands allowed
        """
        parsed_commands = _parse_command_chain(command)
        if len(parsed_commands) <= 1:
            # Single command - check if denied
            if not self.is_allowed(alias, tags, command):
                return command
            return None

        # Multiple commands - check each
        deny_substrings = self._collect_limits(alias, tags).get("deny_substrings", [])
        pol = self.config or {}
        for cmd in parsed_commands:
            if not self._is_single_command_allowed(
                alias, tags, cmd, deny_substrings, pol
            ):
                return cmd
        return None

    def _is_single_command_allowed(
        self, alias: str, tags, command: str, deny_substrings: list, pol: dict
    ) -> bool:
        """Validate a single command (not chained) against policy.

        This is the core validation logic extracted for reuse in chain validation.
        """
        # Check deny_substrings first (hard blocks)
        if isinstance(deny_substrings, list):
            # Normalize command for bypass detection
            normalized_command = _normalize_command(command)

            for s in deny_substrings:
                if not s:
                    continue

                # Check original command (keep existing behavior)
                if s in command:
                    return False

                # Check normalized command (prevent bypass attempts)
                if s in normalized_command:
                    # Log bypass attempt if original didn't match but normalized did
                    if s not in command:
                        self._log_bypass_attempt(alias, command, normalized_command, s)
                    return False

                # Token-based matching for common bypasses
                # Split normalized command into tokens and check if any token matches
                tokens = normalized_command.split()
                for token in tokens:
                    if s.strip() == token:
                        # Exact token match (prevents: rm -rf /var vs rm -rf /)
                        if s.strip() in command:
                            return False
                        # Token match in normalized (bypass attempt)
                        self._log_bypass_attempt(alias, command, normalized_command, s)
                        return False

        # Check rules (allow/deny patterns)
        rules = pol.get("rules", [])
        matched = None
        for rule in rules:
            action = rule.get("action", "deny")
            aliases = rule.get("aliases", [])
            tag_patterns = rule.get("tags", [])
            cmd_patterns = rule.get("commands", [])
            alias_ok = _match_any(alias, aliases) if aliases else True
            tags_ok = True
            if isinstance(tag_patterns, list) and len(tag_patterns) > 0:
                tags_ok = False
                if isinstance(tags, list):
                    for t in tags:
                        if _match_any(t, tag_patterns):
                            tags_ok = True
                            break
            cmd_ok = _match_any(command, cmd_patterns) if cmd_patterns else False
            if alias_ok and tags_ok and cmd_ok:
                matched = action

        if matched is None:
            return False
        return matched == "allow"

    # ----------------------------
    # Network policy (IP/CIDR)
    # ----------------------------
    def _cidrs(self, items):
        nets = []
        if not isinstance(items, list):
            return nets
        for x in items:
            try:
                nets.append(ipaddress.ip_network(str(x), strict=False))
            except Exception:
                continue
        return nets

    def _ips(self, items):
        ips = set()
        if not isinstance(items, list):
            return ips
        for x in items:
            try:
                ips.add(str(ipaddress.ip_address(str(x))))
            except Exception:
                continue
        return ips

    def _network_cfg(self):
        return self.config.get("network", {}) or {}

    def is_ip_allowed(self, ip_str: str) -> bool:
        """Return True if peer IP passes allow/block lists."""
        cfg = self._network_cfg()
        # Hard blocks first
        block_ips = self._ips(cfg.get("block_ips", []))
        if ip_str in block_ips:
            return False
        block_cidrs = self._cidrs(cfg.get("block_cidrs", []))
        try:
            ipobj = ipaddress.ip_address(ip_str)
            for net in block_cidrs:
                if ipobj in net:
                    return False
        except Exception:
            # If it isn't a valid IP, fail closed
            return False

        # If allow lists are present, require membership
        allow_ips = self._ips(cfg.get("allow_ips", []))
        allow_cidrs = self._cidrs(cfg.get("allow_cidrs", []))
        if allow_ips or allow_cidrs:
            if ip_str in allow_ips:
                return True
            for net in allow_cidrs:
                if ipobj in net:
                    return True
            return False

        # No allow lists configured => allow (but blocks already applied)
        return True

    def require_known_host(self) -> bool:
        """Whether a known_hosts entry is required for connection."""
        cfg = self._network_cfg()
        # network.require_known_host overrides limits.require_known_host if set
        if "require_known_host" in cfg:
            return bool(cfg.get("require_known_host"))
        # fallback to limits default
        return True

    # ----------------------------
    # Logging helpers
    # ----------------------------
    def log_decision(self, alias: str, command_hash: str, allowed: bool):
        """Log policy decision."""
        entry = {
            "type": "policy_decision",
            "ts": time.time(),
            "alias": alias,
            "hash": command_hash,
            "allowed": allowed,
        }
        print(json.dumps(entry), file=sys.stderr)

    def log_audit(
        self,
        alias: str,
        command_hash: str,
        exit_code: int,
        duration_ms: int,
        bytes_out: int,
        bytes_err: int,
        cancelled: bool,
        timeout: bool,
        target_ip: str,
    ):
        """Log execution audit JSON."""
        entry = {
            "type": "audit",
            "ts": time.time(),
            "alias": alias,
            "hash": command_hash,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "bytes_out": bytes_out,
            "bytes_err": bytes_err,
            "cancelled": cancelled,
            "timeout": timeout,
            "target_ip": target_ip,
        }
        print(json.dumps(entry), file=sys.stderr)

    def log_progress(self, task_id: str, phase: str, bytes_read: int, elapsed_ms: int):
        """Log progress JSON."""
        entry = {
            "type": "progress",
            "ts": time.time(),
            "task_id": task_id,
            "phase": phase,
            "bytes_read": bytes_read,
            "elapsed_ms": elapsed_ms,
        }
        print(json.dumps(entry), file=sys.stderr)

    def _log_bypass_attempt(
        self,
        alias: str,
        original_command: str,
        normalized_command: str,
        blocked_pattern: str,
    ):
        """Log security event for bypass attempt detection."""
        entry = {
            "level": "error",
            "msg": "security_event",
            "type": "command_bypass_attempt",
            "ts": time.time(),
            "alias": alias,
            "original_command": original_command,
            "normalized_command": normalized_command,
            "blocked_pattern": blocked_pattern,
        }
        print(json.dumps(entry), file=sys.stderr)

    def _log_chain_parsing(
        self,
        alias: str,
        original_command: str,
        parsed_commands: list[str],
    ):
        """Log command chain parsing for security audit."""
        entry = {
            "level": "info",
            "msg": "security_event",
            "type": "command_chain_parsed",
            "ts": time.time(),
            "alias": alias,
            "original_command": original_command,
            "parsed_commands": parsed_commands,
            "command_count": len(parsed_commands),
        }
        print(json.dumps(entry), file=sys.stderr)

    def _log_chain_denial(
        self,
        alias: str,
        original_command: str,
        denied_command: str,
        parsed_commands: list[str],
    ):
        """Log which command in chain caused denial."""
        entry = {
            "level": "warn",
            "msg": "security_event",
            "type": "command_chain_denied",
            "ts": time.time(),
            "alias": alias,
            "original_command": original_command,
            "denied_command": denied_command,
            "parsed_commands": parsed_commands,
            "denied_index": (
                parsed_commands.index(denied_command)
                if denied_command in parsed_commands
                else -1
            ),
        }
        print(json.dumps(entry), file=sys.stderr)

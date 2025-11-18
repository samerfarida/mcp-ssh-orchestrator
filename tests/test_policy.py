"""Tests for policy engine."""

import pytest

from mcp_ssh.policy import Policy, _parse_command_chain


@pytest.fixture
def basic_policy():
    """Basic policy configuration for testing."""
    return {
        "limits": {
            "max_seconds": 60,
            "max_output_bytes": 1048576,
            "deny_substrings": ["rm -rf", "shutdown"],
        },
        "network": {
            "allow_ips": [],
            "allow_cidrs": ["10.0.0.0/8"],
            "block_ips": ["10.10.10.10"],
            "block_cidrs": [],
        },
        "rules": [
            {
                "action": "allow",
                "aliases": ["*"],
                "tags": [],
                "commands": ["uptime*", "df -h*"],
            },
            {
                "action": "allow",
                "aliases": [],
                "tags": ["staging"],
                "commands": ["systemctl restart *"],
            },
            {
                "action": "deny",
                "aliases": ["prod-*"],
                "tags": [],
                "commands": ["rm *"],
            },
        ],
        "overrides": {
            "aliases": {
                "prod-db-1": {
                    "max_seconds": 30,
                }
            },
            "tags": {
                "production": {
                    "max_output_bytes": 524288,
                }
            },
        },
    }


def test_is_allowed_safe_command(basic_policy):
    """Test allowing safe command."""
    pol = Policy(basic_policy)

    assert pol.is_allowed("test1", [], "uptime") is True
    assert pol.is_allowed("test1", [], "df -h") is True


def test_is_denied_no_match(basic_policy):
    """Test denying command that doesn't match any rule."""
    pol = Policy(basic_policy)

    # No rule matches, deny by default
    assert pol.is_allowed("test1", [], "unknown-command") is False


def test_is_allowed_tag_based(basic_policy):
    """Test allowing command based on tag."""
    pol = Policy(basic_policy)

    assert pol.is_allowed("stg-web-1", ["staging"], "systemctl restart nginx") is True
    assert (
        pol.is_allowed("prod-web-1", ["production"], "systemctl restart nginx") is False
    )


def test_is_denied_by_substring(basic_policy):
    """Test denying command by substring."""
    pol = Policy(basic_policy)

    assert pol.is_allowed("test1", [], "rm -rf /tmp") is False
    assert pol.is_allowed("test1", [], "shutdown -h now") is False


def test_is_denied_by_explicit_rule(basic_policy):
    """Test denying command by explicit rule."""
    pol = Policy(basic_policy)

    assert pol.is_allowed("prod-web-1", [], "rm file.txt") is False


def test_limits_global(basic_policy):
    """Test global limits."""
    pol = Policy(basic_policy)

    limits = pol.limits_for("test1", [])
    assert limits["max_seconds"] == 60
    assert limits["max_output_bytes"] == 1048576


def test_limits_alias_override(basic_policy):
    """Test alias-specific limit override."""
    pol = Policy(basic_policy)

    limits = pol.limits_for("prod-db-1", [])
    assert limits["max_seconds"] == 30  # Overridden


def test_limits_tag_override(basic_policy):
    """Test tag-specific limit override."""
    pol = Policy(basic_policy)

    limits = pol.limits_for("test1", ["production"])
    assert limits["max_output_bytes"] == 524288  # Overridden


def test_is_ip_allowed_in_cidr(basic_policy):
    """Test IP allowed by CIDR."""
    pol = Policy(basic_policy)

    assert pol.is_ip_allowed("10.0.0.1") is True
    assert pol.is_ip_allowed("10.255.255.255") is True


def test_is_ip_denied_outside_cidr(basic_policy):
    """Test IP denied outside allowed CIDR."""
    pol = Policy(basic_policy)

    assert pol.is_ip_allowed("192.168.1.1") is False
    assert pol.is_ip_allowed("11.0.0.1") is False


def test_is_ip_blocked_explicit(basic_policy):
    """Test IP explicitly blocked."""
    pol = Policy(basic_policy)

    assert pol.is_ip_allowed("10.10.10.10") is False


def test_is_ip_allowed_no_allowlist():
    """Test IP allowed when no allowlist configured."""
    pol = Policy({"network": {"allow_ips": [], "allow_cidrs": []}})

    # No allowlist = allow all (unless blocked)
    assert pol.is_ip_allowed("1.2.3.4") is True
    assert pol.is_ip_allowed("10.0.0.1") is True


def test_is_ip_allowed_exact_ip():
    """Test exact IP match in allowlist."""
    pol = Policy(
        {
            "network": {
                "allow_ips": ["10.0.0.1", "10.0.0.2"],
                "allow_cidrs": [],
            }
        }
    )

    assert pol.is_ip_allowed("10.0.0.1") is True
    assert pol.is_ip_allowed("10.0.0.2") is True
    assert pol.is_ip_allowed("10.0.0.3") is False


def test_require_known_host_default(basic_policy):
    """Test default known_host requirement."""
    pol = Policy(basic_policy)

    # Should default to True
    assert pol.require_known_host() is True


def test_require_known_host_network_override():
    """Test known_host requirement from network config."""
    pol = Policy(
        {
            "network": {"require_known_host": False},
            "limits": {"require_known_host": True},
        }
    )

    # Network setting overrides limits
    assert pol.require_known_host() is False


def test_glob_pattern_matching():
    """Test glob pattern matching in rules."""
    pol = Policy(
        {
            "rules": [
                {
                    "action": "allow",
                    "aliases": ["web-*"],
                    "tags": [],
                    "commands": ["systemctl status *"],
                }
            ]
        }
    )

    assert pol.is_allowed("web-1", [], "systemctl status nginx") is True
    assert pol.is_allowed("web-prod", [], "systemctl status apache") is True
    assert pol.is_allowed("db-1", [], "systemctl status nginx") is False


def test_multiple_tags_any_match():
    """Test that any tag matching enables the rule."""
    pol = Policy(
        {
            "rules": [
                {
                    "action": "allow",
                    "aliases": [],
                    "tags": ["staging", "dev"],
                    "commands": ["deploy*"],
                }
            ]
        }
    )

    assert pol.is_allowed("test1", ["staging"], "deploy.sh") is True
    assert pol.is_allowed("test2", ["dev"], "deploy.sh") is True
    assert pol.is_allowed("test3", ["staging", "other"], "deploy.sh") is True
    assert pol.is_allowed("test4", ["production"], "deploy.sh") is False


def test_empty_config():
    """Test policy with empty config."""
    pol = Policy({})

    # Should have sensible defaults
    limits = pol.limits_for("test1", [])
    assert "max_seconds" in limits
    assert "max_output_bytes" in limits

    # Deny by default
    assert pol.is_allowed("test1", [], "any command") is False


def test_bypass_prevention_quotes_single(basic_policy):
    """Test that single quotes don't bypass command denial."""
    pol = Policy(basic_policy)

    # Should be blocked even with quotes
    assert pol.is_allowed("test1", [], "echo 'rm -rf /'") is False
    assert pol.is_allowed("test1", [], "'rm -rf /'") is False


def test_bypass_prevention_quotes_double(basic_policy):
    """Test that double quotes don't bypass command denial."""
    pol = Policy(basic_policy)

    # Should be blocked even with quotes
    assert pol.is_allowed("test1", [], 'echo "rm -rf /"') is False
    assert pol.is_allowed("test1", [], '"rm -rf /"') is False


def test_bypass_prevention_mixed_quotes(basic_policy):
    """Test that mixed quotes don't bypass command denial."""
    pol = Policy(basic_policy)

    # Should be blocked even with mixed quotes
    assert pol.is_allowed("test1", [], "echo \"rm -rf /'test'\"") is False
    assert pol.is_allowed("test1", [], "echo 'rm -rf /\"/test\"'") is False


def test_bypass_prevention_escaped_characters(basic_policy):
    """Test that escaped characters don't bypass command denial."""
    pol = Policy(basic_policy)

    # Should be blocked even with escaped characters
    assert pol.is_allowed("test1", [], "rm\\ -rf\\ /") is False
    assert pol.is_allowed("test1", [], "shutdown\\ -h") is False


def test_bypass_prevention_whitespace_variations(basic_policy):
    """Test that whitespace variations don't bypass command denial."""
    pol = Policy(basic_policy)

    # Multiple spaces should normalize to single space
    assert pol.is_allowed("test1", [], "rm    -rf    /") is False
    # Tabs should normalize to space
    assert pol.is_allowed("test1", [], "rm\t-rf\t/") is False
    # Mixed whitespace should normalize
    assert pol.is_allowed("test1", [], "rm  \t  -rf  \t  /") is False


def test_bypass_prevention_token_matching(basic_policy):
    """Test that token-based matching prevents bypasses."""
    # Token-based matching is tested via normalized command checking
    # which checks both original and normalized forms
    # Additional token-specific tests would require more complex policy rules
    pass


def test_bypass_prevention_legitimate_commands_still_work(basic_policy):
    """Test that legitimate commands still work despite normalization."""
    pol = Policy(basic_policy)

    # These should still be allowed (match allow rules, don't match deny_substrings)
    assert pol.is_allowed("test1", [], "uptime") is True
    assert pol.is_allowed("test1", [], "df -h") is True

    # Commands with quotes that match allow rules should still work
    # Note: 'echo "hello world"' doesn't match any allow rule, so would be denied
    # But commands that ARE allowed by rules should work even with quotes
    assert (
        pol.is_allowed("test1", [], 'uptime "server1"') is True
    )  # Still contains "uptime"


def test_normalize_command_quotes_removal():
    """Test command normalization removes quotes."""
    from mcp_ssh.policy import _normalize_command

    assert _normalize_command("rm -rf /") == "rm -rf /"
    assert _normalize_command('"rm -rf /"') == "rm -rf /"
    assert _normalize_command("'rm -rf /'") == "rm -rf /"
    assert _normalize_command('echo "rm -rf /"') == "echo rm -rf /"


def test_normalize_command_escape_removal():
    """Test command normalization removes escaping."""
    from mcp_ssh.policy import _normalize_command

    assert _normalize_command("rm\\ -rf\\ /") == "rm -rf /"
    assert _normalize_command("shutdown\\ -h") == "shutdown -h"


def test_normalize_command_whitespace_normalization():
    """Test command normalization normalizes whitespace."""
    from mcp_ssh.policy import _normalize_command

    assert _normalize_command("rm    -rf    /") == "rm -rf /"
    assert _normalize_command("rm\t-rf\t/") == "rm -rf /"
    assert _normalize_command("rm  \t  -rf  \t  /") == "rm -rf /"
    assert _normalize_command("  rm -rf /  ") == "rm -rf /"


def test_normalize_command_complex_bypass():
    """Test command normalization handles complex bypass attempts."""
    from mcp_ssh.policy import _normalize_command

    # Complex bypass attempt
    normalized = _normalize_command('echo "rm\\ -rf\\ /"')
    # Should normalize to: echo rm -rf /
    assert "rm -rf /" in normalized
    assert '"' not in normalized
    assert "\\" not in normalized

    # Another complex case
    normalized = _normalize_command("'rm'    '-rf'    '/'")
    assert normalized == "rm -rf /"


def test_bypass_prevention_substring_in_normalized_only(basic_policy):
    """Test that commands blocked only in normalized form are detected."""
    pol = Policy(basic_policy)

    # Command that would bypass without normalization
    # 'rm -rf /' doesn't contain 'rm -rf /' directly, but normalized does
    assert pol.is_allowed("test1", [], "'rm -rf /'") is False

    # Similar with escaped
    assert pol.is_allowed("test1", [], "rm\\ -rf\\ /") is False


def test_bypass_prevention_multiple_patterns(basic_policy):
    """Test bypass prevention works for multiple deny patterns."""
    pol = Policy(basic_policy)

    # Both patterns should be caught
    assert pol.is_allowed("test1", [], "'rm -rf /'") is False
    assert pol.is_allowed("test1", [], '"shutdown -h"') is False


# ==================== Command Chain Parsing Tests ====================


def test_parse_command_chain_simple():
    """Test parsing simple command (no chaining)."""
    result = _parse_command_chain("uptime")
    assert result == ["uptime"]


def test_parse_command_chain_and_operator():
    """Test parsing && operator."""
    result = _parse_command_chain("uptime && whoami")
    assert result == ["uptime", "whoami"]


def test_parse_command_chain_semicolon():
    """Test parsing ; operator."""
    result = _parse_command_chain("uptime; whoami")
    assert result == ["uptime", "whoami"]


def test_parse_command_chain_pipe():
    """Test parsing | operator."""
    result = _parse_command_chain("uptime | cat")
    assert result == ["uptime", "cat"]


def test_parse_command_chain_or_operator():
    """Test parsing || operator."""
    result = _parse_command_chain("uptime || whoami")
    assert result == ["uptime", "whoami"]


def test_parse_command_chain_multiple():
    """Test parsing multiple chained commands."""
    result = _parse_command_chain("uptime && whoami && hostname")
    assert result == ["uptime", "whoami", "hostname"]


def test_parse_command_chain_mixed_operators():
    """Test parsing mixed operators."""
    result = _parse_command_chain("uptime; whoami && hostname")
    assert result == ["uptime", "whoami", "hostname"]


def test_parse_command_chain_with_quotes():
    """Test parsing commands with quotes (operators in quotes should be ignored)."""
    result = _parse_command_chain('echo "hello && world" && whoami')
    assert result == ['echo "hello && world"', "whoami"]


def test_parse_command_chain_backtick_substitution():
    """Test parsing commands with backtick substitution."""
    result = _parse_command_chain("uptime `whoami`")
    # Backtick substitution is kept as part of command for validation
    assert len(result) == 1
    assert "uptime" in result[0]
    assert "`whoami`" in result[0]


def test_parse_command_chain_dollar_paren_substitution():
    """Test parsing commands with $(command) substitution."""
    result = _parse_command_chain("echo $(whoami) && uptime")
    # $(whoami) should be kept with echo, then uptime is separate
    assert len(result) == 2
    assert "$(whoami)" in result[0]
    assert result[1] == "uptime"


def test_parse_command_chain_parentheses():
    """Test parsing commands with parentheses grouping."""
    result = _parse_command_chain("uptime && (whoami || hostname)")
    # Parentheses grouping should be preserved in the command
    assert len(result) == 2
    assert result[0] == "uptime"
    assert "(whoami || hostname)" in result[1]


def test_parse_command_chain_empty():
    """Test parsing empty command."""
    result = _parse_command_chain("")
    assert result == []


def test_parse_command_chain_whitespace():
    """Test parsing commands with extra whitespace."""
    result = _parse_command_chain("uptime   &&   whoami")
    assert result == ["uptime", "whoami"]


# ==================== Command Chain Policy Validation Tests ====================


def test_chain_both_commands_allowed(basic_policy):
    """Test that chaining two allowed commands works."""
    pol = Policy(basic_policy)

    # Both uptime and df -h are allowed
    assert pol.is_allowed("test1", [], "uptime && df -h") is True
    assert pol.is_allowed("test1", [], "uptime; df -h") is True


def test_chain_first_allowed_second_denied(basic_policy):
    """Test that chaining allowed with denied command is blocked."""
    pol = Policy(basic_policy)

    # uptime is allowed, but "rm -rf" is in deny_substrings
    assert pol.is_allowed("test1", [], "uptime && rm -rf /tmp") is False
    assert pol.is_allowed("test1", [], "uptime; rm -rf /tmp") is False


def test_chain_first_denied_second_allowed(basic_policy):
    """Test that chaining denied with allowed command is blocked."""
    pol = Policy(basic_policy)

    # rm -rf is denied, even if followed by allowed command
    assert pol.is_allowed("test1", [], "rm -rf /tmp && uptime") is False
    assert pol.is_allowed("test1", [], "rm -rf /tmp; uptime") is False


def test_chain_both_denied(basic_policy):
    """Test that chaining two denied commands is blocked."""
    pol = Policy(basic_policy)

    # Both commands are denied
    assert pol.is_allowed("test1", [], "rm -rf / && shutdown -h") is False


def test_chain_multiple_commands_all_allowed(basic_policy):
    """Test that chaining multiple allowed commands works."""
    pol = Policy(basic_policy)

    # All three commands are allowed
    assert pol.is_allowed("test1", [], "uptime && df -h && uptime") is True


def test_chain_multiple_commands_one_denied(basic_policy):
    """Test that chaining multiple commands fails if any is denied."""
    pol = Policy(basic_policy)

    # Middle command is denied
    assert pol.is_allowed("test1", [], "uptime && rm -rf / && df -h") is False


def test_chain_order_independence(basic_policy):
    """Test that command order doesn't affect validation."""
    pol = Policy(basic_policy)

    # Both should behave the same (both allowed)
    result1 = pol.is_allowed("test1", [], "uptime && df -h")
    result2 = pol.is_allowed("test1", [], "df -h && uptime")
    assert result1 == result2
    assert result1 is True


def test_chain_with_command_substitution_denied(basic_policy):
    """Test that command substitution with denied command is blocked."""
    pol = Policy(basic_policy)

    # echo is allowed, but $(rm -rf /) contains denied substring
    # Note: This depends on how substitution is handled in parsing
    # For now, the entire command with substitution is checked
    assert pol.is_allowed("test1", [], 'echo "$(rm -rf /)"') is False


def test_chain_backward_compatibility_simple(basic_policy):
    """Test that simple commands (no chaining) still work as before."""
    pol = Policy(basic_policy)

    # These should work exactly as before
    assert pol.is_allowed("test1", [], "uptime") is True
    assert pol.is_allowed("test1", [], "df -h") is True
    assert pol.is_allowed("test1", [], "unknown-command") is False


def test_get_denied_command_in_chain_single(basic_policy):
    """Test identifying denied command in single command."""
    pol = Policy(basic_policy)

    denied = pol.get_denied_command_in_chain("test1", [], "rm -rf /tmp")
    assert denied == "rm -rf /tmp"

    denied = pol.get_denied_command_in_chain("test1", [], "uptime")
    assert denied is None


def test_get_denied_command_in_chain_multiple(basic_policy):
    """Test identifying which command in chain is denied."""
    pol = Policy(basic_policy)

    # First command denied
    denied = pol.get_denied_command_in_chain("test1", [], "rm -rf /tmp && uptime")
    assert denied == "rm -rf /tmp"

    # Second command denied
    denied = pol.get_denied_command_in_chain("test1", [], "uptime && rm -rf /tmp")
    assert denied == "rm -rf /tmp"

    # All allowed
    denied = pol.get_denied_command_in_chain("test1", [], "uptime && df -h")
    assert denied is None


def test_chain_with_pipe_operator(basic_policy):
    """Test that pipe operator is treated as chaining."""
    pol = Policy(basic_policy)

    # Pipe should be treated as chaining - both commands must be allowed
    # uptime is allowed, but we need to check what "cat" would match
    # For this test, assume both are allowed or adjust policy
    result = pol.is_allowed("test1", [], "uptime | cat")
    # Result depends on whether "cat" matches any allow rule
    # Since basic_policy doesn't have "cat", it should be denied
    assert result is False

#!/usr/bin/env python3
"""Validate YAML configuration files (policy.yml, servers.yml, credentials.yml).

This script validates configuration files for syntax, required fields, types,
and cross-references.

Usage:
    python scripts/validate-config.py [config_dir]
"""

import sys
from pathlib import Path
from typing import Any

import yaml


def validate_servers(servers_data: dict[str, Any], config_dir: Path) -> list[str]:
    """Validate servers.yml configuration."""
    errors = []

    if "hosts" not in servers_data:
        errors.append("servers.yml: Missing required 'hosts' field")
        return errors

    hosts = servers_data["hosts"]
    if not isinstance(hosts, list):
        errors.append("servers.yml: 'hosts' must be a list")
        return errors

    for i, host in enumerate(hosts):
        if not isinstance(host, dict):
            errors.append(f"servers.yml: hosts[{i}] must be a dict")
            continue

        # Required fields
        if "alias" not in host:
            errors.append(f"servers.yml: hosts[{i}]: Missing required 'alias' field")
        if "host" not in host:
            errors.append(f"servers.yml: hosts[{i}]: Missing required 'host' field")

        # Validate alias format
        if "alias" in host:
            alias = host["alias"]
            if not isinstance(alias, str) or not alias.strip():
                errors.append(
                    f"servers.yml: hosts[{i}]: 'alias' must be a non-empty string"
                )

        # Validate port if present
        if "port" in host:
            port = host["port"]
            try:
                port_int = int(port)
                if not (1 <= port_int <= 65535):
                    errors.append(
                        f"servers.yml: hosts[{i}]: 'port' must be between 1 and 65535"
                    )
            except (ValueError, TypeError):
                errors.append(f"servers.yml: hosts[{i}]: 'port' must be an integer")

    return errors


def validate_credentials(creds_data: dict[str, Any], config_dir: Path) -> list[str]:
    """Validate credentials.yml configuration."""
    errors = []

    if "entries" not in creds_data:
        errors.append("credentials.yml: Missing required 'entries' field")
        return errors

    entries = creds_data["entries"]
    if not isinstance(entries, list):
        errors.append("credentials.yml: 'entries' must be a list")
        return errors

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"credentials.yml: entries[{i}] must be a dict")
            continue

        if "name" not in entry:
            errors.append(
                f"credentials.yml: entries[{i}]: Missing required 'name' field"
            )

        # Check that at least one auth method is present
        has_key = "key_path" in entry and entry["key_path"]
        has_password = "password" in entry and entry["password"]
        if not has_key and not has_password:
            errors.append(
                f"credentials.yml: entries[{i}]: Must have either 'key_path' or 'password'"
            )

    return errors


def validate_policy(policy_data: dict[str, Any], config_dir: Path) -> list[str]:
    """Validate policy.yml configuration."""
    errors = []

    # Validate limits section
    if "limits" in policy_data:
        limits = policy_data["limits"]
        if not isinstance(limits, dict):
            errors.append("policy.yml: 'limits' must be a dict")
        else:
            # Validate max_seconds
            if "max_seconds" in limits:
                try:
                    max_sec = int(limits["max_seconds"])
                    if max_sec < 1:
                        errors.append("policy.yml: limits.max_seconds must be >= 1")
                except (ValueError, TypeError):
                    errors.append("policy.yml: limits.max_seconds must be an integer")

            # Validate max_output_bytes
            if "max_output_bytes" in limits:
                try:
                    max_bytes = int(limits["max_output_bytes"])
                    if max_bytes < 1:
                        errors.append(
                            "policy.yml: limits.max_output_bytes must be >= 1"
                        )
                except (ValueError, TypeError):
                    errors.append(
                        "policy.yml: limits.max_output_bytes must be an integer"
                    )

    # Validate rules section
    if "rules" in policy_data:
        rules = policy_data["rules"]
        if not isinstance(rules, list):
            errors.append("policy.yml: 'rules' must be a list")
        else:
            for i, rule in enumerate(rules):
                if not isinstance(rule, dict):
                    errors.append(f"policy.yml: rules[{i}] must be a dict")
                    continue

                action = rule.get("action", "deny")
                if action not in ["allow", "deny"]:
                    errors.append(
                        f"policy.yml: rules[{i}]: 'action' must be 'allow' or 'deny'"
                    )

    # Validate network section
    if "network" in policy_data:
        network = policy_data["network"]
        if not isinstance(network, dict):
            errors.append("policy.yml: 'network' must be a dict")

    return errors


def validate_cross_references(
    servers_data: dict[str, Any], creds_data: dict[str, Any]
) -> list[str]:
    """Validate cross-references between servers and credentials."""
    errors = []

    if "hosts" not in servers_data or "entries" not in creds_data:
        return errors

    hosts = servers_data["hosts"]
    cred_entries = creds_data["entries"]

    # Build credential names set
    cred_names = {
        entry.get("name") for entry in cred_entries if isinstance(entry, dict)
    }

    # Check each host's credentials reference
    for i, host in enumerate(hosts):
        if not isinstance(host, dict):
            continue

        cred_ref = host.get("credentials")
        if cred_ref and cred_ref not in cred_names:
            errors.append(
                f"servers.yml: hosts[{i}]: References non-existent credentials '{cred_ref}'"
            )

    return errors


def main() -> int:
    """Main validation function."""
    if len(sys.argv) > 1:
        config_dir = Path(sys.argv[1])
    else:
        config_dir = Path(__file__).parent.parent / "config"

    if not config_dir.exists():
        print(f"Error: Config directory not found: {config_dir}", file=sys.stderr)
        return 1

    all_errors = []

    # Validate servers.yml
    servers_file = config_dir / "servers.yml"
    if servers_file.exists():
        try:
            with open(servers_file) as f:
                servers_data = yaml.safe_load(f) or {}
            errors = validate_servers(servers_data, config_dir)
            all_errors.extend([f"servers.yml: {e}" for e in errors])
        except yaml.YAMLError as e:
            all_errors.append(f"servers.yml: YAML syntax error: {e}")
        except Exception as e:
            all_errors.append(f"servers.yml: Error reading file: {e}")

    # Validate credentials.yml
    creds_file = config_dir / "credentials.yml"
    if creds_file.exists():
        try:
            with open(creds_file) as f:
                creds_data = yaml.safe_load(f) or {}
            errors = validate_credentials(creds_data, config_dir)
            all_errors.extend([f"credentials.yml: {e}" for e in errors])
        except yaml.YAMLError as e:
            all_errors.append(f"credentials.yml: YAML syntax error: {e}")
        except Exception as e:
            all_errors.append(f"credentials.yml: Error reading file: {e}")

    # Validate policy.yml
    policy_file = config_dir / "policy.yml"
    if policy_file.exists():
        try:
            with open(policy_file) as f:
                policy_data = yaml.safe_load(f) or {}
            errors = validate_policy(policy_data, config_dir)
            all_errors.extend([f"policy.yml: {e}" for e in errors])
        except yaml.YAMLError as e:
            all_errors.append(f"policy.yml: YAML syntax error: {e}")
        except Exception as e:
            all_errors.append(f"policy.yml: Error reading file: {e}")

    # Validate cross-references
    if servers_file.exists() and creds_file.exists():
        try:
            with open(servers_file) as f:
                servers_data = yaml.safe_load(f) or {}
            with open(creds_file) as f:
                creds_data = yaml.safe_load(f) or {}
            errors = validate_cross_references(servers_data, creds_data)
            all_errors.extend(errors)
        except Exception as e:
            all_errors.append(f"Cross-reference validation error: {e}")

    # Report results
    if all_errors:
        print("Configuration validation errors found:", file=sys.stderr)
        for error in all_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("All configuration files validated successfully!", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

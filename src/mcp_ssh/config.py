"""YAML config loader for servers, credentials, and policy."""

import json
import os
import sys

import yaml

DEFAULT_CONFIG_DIR = os.environ.get("MCP_SSH_CONFIG_DIR", "/app/config")
DEFAULT_KEYS_DIR = os.environ.get("MCP_SSH_KEYS_DIR", "/app/keys")
DEFAULT_SECRETS_DIR = os.environ.get("MCP_SSH_SECRETS_DIR", "/app/secrets")


def _load_yaml(path: str) -> dict:
    """Load YAML file to dict."""
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        _log_err("config_error", {"path": path, "error": str(e)})
        return {}


def _log_err(kind: str, data: dict) -> None:
    """Log error to stderr as JSON."""
    try:
        sys.stderr.write(json.dumps({"level": "error", "kind": kind, **data}) + "\n")
    except Exception:
        pass


def _resolve_secret(secret_name: str, secrets_dir: str = "") -> str:
    """Resolve a secret from Docker secrets directory or environment variable.

    Security: Validates against path traversal attacks and only allows
    safe characters in secret names (alphanumeric, dash, underscore).
    """
    if not secret_name:
        return ""

    # Try environment variable first (format: MCP_SSH_SECRET_<name>)
    env_key = f"MCP_SSH_SECRET_{secret_name.upper()}"
    if env_key in os.environ:
        return os.environ[env_key]

    # Security validation: only allow safe characters in secret_name
    # Allowed: alphanumeric, dash, underscore
    if not secret_name.replace("-", "").replace("_", "").isalnum():
        _log_err(
            "security_event",
            {
                "type": "invalid_secret_name",
                "secret_name": secret_name,
                "reason": "contains_invalid_characters",
            },
        )
        return ""

    # Reject absolute paths (for secrets, enforce relative paths only)
    if os.path.isabs(secret_name):
        _log_err(
            "security_event",
            {
                "type": "path_traversal_attempt",
                "secret_name": secret_name,
                "reason": "absolute_path_rejected",
            },
        )
        return ""

    # Try Docker secrets file with path traversal protection
    base_dir = secrets_dir or DEFAULT_SECRETS_DIR
    secret_path = os.path.join(base_dir, secret_name)

    # Normalize path to handle any ../ sequences
    normalized_path = os.path.normpath(secret_path)

    # Get absolute paths for comparison
    base_abs = os.path.abspath(base_dir)
    resolved_abs = os.path.abspath(normalized_path)

    # Validate resolved path stays within secrets_dir
    # Check that resolved path starts with base_abs + separator
    if not resolved_abs.startswith(base_abs + os.sep) and resolved_abs != base_abs:
        _log_err(
            "security_event",
            {
                "type": "path_traversal_attempt",
                "secret_name": secret_name,
                "attempted_path": resolved_abs,
                "base_dir": base_abs,
                "reason": "path_outside_allowed_directory",
            },
        )
        return ""

    try:
        with open(resolved_abs, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _resolve_key_path(key_path: str, keys_dir: str = "") -> str:
    """Resolve SSH key path (supports relative paths and absolute paths)."""
    if not key_path:
        return ""

    # If already absolute, return as-is
    if os.path.isabs(key_path):
        return key_path

    # Otherwise, resolve relative to keys directory
    base_dir = keys_dir or DEFAULT_KEYS_DIR
    return os.path.join(base_dir, key_path)


class Config:
    """Configuration manager for servers, credentials, and policy."""

    def __init__(self, config_dir: str = "", keys_dir: str = "", secrets_dir: str = ""):
        self.config_dir = config_dir or DEFAULT_CONFIG_DIR
        self.keys_dir = keys_dir or DEFAULT_KEYS_DIR
        self.secrets_dir = secrets_dir or DEFAULT_SECRETS_DIR
        self._data = {}
        self.reload()

    def reload(self) -> None:
        """Reload configuration from disk."""
        servers = _load_yaml(os.path.join(self.config_dir, "servers.yml"))
        creds = _load_yaml(os.path.join(self.config_dir, "credentials.yml"))
        policy = _load_yaml(os.path.join(self.config_dir, "policy.yml"))
        self._data = {"servers": servers, "credentials": creds, "policy": policy}

    def list_hosts(self) -> list:
        """List all host aliases."""
        servers = self._data.get("servers", {}).get("hosts", [])
        result = []
        for h in servers:
            alias = str(h.get("alias", "")).strip()
            if alias:
                result.append(alias)
        return result

    def get_host(self, alias: str) -> dict:
        """Get host configuration by alias."""
        for h in self._data.get("servers", {}).get("hosts", []):
            if str(h.get("alias", "")) == str(alias):
                return h
        raise ValueError(f"Host alias not found: {alias}")

    def get_host_tags(self, alias: str) -> list:
        """Get tags for a host."""
        try:
            host = self.get_host(alias)
            return host.get("tags", []) or []
        except ValueError:
            return []

    def find_hosts_by_tag(self, tag: str) -> list:
        """Find all host aliases with a given tag."""
        out = []
        tag_str = str(tag).strip()
        for h in self._data.get("servers", {}).get("hosts", []):
            tags = h.get("tags", []) or []
            if tag_str in tags:
                out.append(str(h.get("alias", "")))
        return out

    def get_credentials(self, creds_name: str) -> dict:
        """Get credentials by name with secret resolution."""
        creds = {}
        for c in self._data.get("credentials", {}).get("entries", []):
            if str(c.get("name", "")) == str(creds_name):
                creds = c
                break

        if not creds:
            return {}

        # Resolve key path
        key_path = creds.get("key_path", "")
        if key_path:
            key_path = _resolve_key_path(key_path, self.keys_dir)

        # Resolve password from secret or env var
        password = ""
        password_secret = creds.get("password_secret", "")
        if password_secret:
            password = _resolve_secret(password_secret, self.secrets_dir)
        elif creds.get("password", ""):
            password = creds.get("password", "")

        # Resolve key passphrase from secret or env var
        passphrase = ""
        passphrase_secret = creds.get("key_passphrase_secret", "")
        if passphrase_secret:
            passphrase = _resolve_secret(passphrase_secret, self.secrets_dir)

        return {
            "username": str(creds.get("username", "")),
            "key_path": key_path,
            "password": password,
            "passphrase": passphrase,
        }

    def get_policy(self) -> dict:
        """Get policy configuration."""
        return self._data.get("policy", {})

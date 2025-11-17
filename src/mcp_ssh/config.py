"""YAML config loader for servers, credentials, and policy."""

import json
import os
import sys
import time

import yaml

DEFAULT_CONFIG_DIR = os.environ.get("MCP_SSH_CONFIG_DIR", "/app/config")
DEFAULT_KEYS_DIR = os.environ.get("MCP_SSH_KEYS_DIR", "/app/keys")
DEFAULT_SECRETS_DIR = os.environ.get("MCP_SSH_SECRETS_DIR", "/app/secrets")

# Maximum file size for YAML config files (10MB)
# Prevents resource exhaustion attacks via oversized YAML files
MAX_YAML_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

# Input length limits for configuration parameters
# Prevents resource exhaustion attacks via oversized string inputs
MAX_SECRET_NAME_LENGTH = 100  # Maximum length for secret names
MAX_KEY_PATH_LENGTH = 500  # Maximum length for SSH key paths


def _load_yaml(path: str) -> dict:
    """Load YAML file to dict with size limit protection.

    Security: Validates file size before loading to prevent resource exhaustion
    attacks via oversized YAML files.

    Args:
        path: Path to YAML file to load

    Returns:
        Dictionary containing parsed YAML data, or empty dict on error/size limit
    """
    try:
        # Check if file exists
        if not os.path.exists(path):
            return {}

        # Check file size before loading to prevent resource exhaustion
        file_size = os.path.getsize(path)
        if file_size > MAX_YAML_FILE_SIZE:
            _log_security_event(
                event_type="file_size_limit_exceeded",
                attempted_path=path,
                resolved_path=os.path.abspath(path),
                reason="yaml_file_too_large",
                additional_data={
                    "file_size": file_size,
                    "max_size": MAX_YAML_FILE_SIZE,
                },
            )
            return {}

        # Load YAML file
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


def _log_security_event(
    event_type: str,
    attempted_path: str = "",
    resolved_path: str = "",
    reason: str = "",
    additional_data: dict | None = None,
) -> None:
    """Log security audit event to stderr in structured JSON format.

    Security: Provides comprehensive audit logging for security-relevant events
    including path traversal attempts, invalid file access, oversized files, etc.

    Args:
        event_type: Type of security event (e.g., "path_traversal_attempt",
                   "invalid_file_access", "file_size_limit_exceeded",
                   "input_length_limit_exceeded")
        attempted_path: Original path/input that triggered the security event
        resolved_path: Resolved/absolute path (if applicable)
        reason: Human-readable reason for the security event
        additional_data: Optional additional context (field names, sizes, etc.)
    """
    try:
        audit_entry = {
            "level": "error",
            "kind": "security_audit",
            "type": "security_event",
            "event_type": event_type,
            "ts": time.time(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        }

        # Add path information if provided
        if attempted_path:
            audit_entry["attempted_path"] = attempted_path
        if resolved_path:
            audit_entry["resolved_path"] = resolved_path

        # Add reason if provided
        if reason:
            audit_entry["reason"] = reason

        # Merge additional data if provided
        if additional_data:
            audit_entry.update(additional_data)

        sys.stderr.write(json.dumps(audit_entry) + "\n")
    except Exception:
        # Silently fail to prevent logging errors from breaking functionality
        pass


def _validate_file_path(
    file_path: str, base_dir: str, require_exists: bool = True
) -> bool:
    """Validate that a file path is a regular file within allowed directory.

    Security: Validates that the path:
    - Stays within the allowed base directory
    - Is not a directory (if path exists)
    - Is not a symlink (if path exists, symlinks are rejected for security)
    - Is a regular file (if path exists and require_exists=True)

    Args:
        file_path: Absolute path to the file to validate
        base_dir: Absolute path to the base directory (allowed directory)
        require_exists: If True, require file to exist and be a regular file.
                       If False, only check directory/symlink if path exists.

    Returns:
        True if valid, False otherwise
    """
    if not file_path or not base_dir:
        return False

    # Check that file path stays within base_dir
    base_abs = os.path.abspath(base_dir)
    file_abs = os.path.abspath(file_path)

    # Validate resolved path stays within base directory
    if not file_abs.startswith(base_abs + os.sep) and file_abs != base_abs:
        _log_security_event(
            event_type="file_validation_failed",
            attempted_path=file_path,
            resolved_path=file_abs,
            reason="path_outside_allowed_directory",
            additional_data={"base_dir": base_abs},
        )
        return False

    # If path doesn't exist, only validate if we require existence
    if not os.path.exists(file_abs):
        if require_exists:
            _log_security_event(
                event_type="file_validation_failed",
                attempted_path=file_path,
                resolved_path=file_abs,
                reason="file_not_found",
            )
            return False
        # If we don't require existence, path is valid (file might be created later)
        return True

    # Check if path is a directory (reject directories)
    if os.path.isdir(file_abs):
        _log_security_event(
            event_type="file_validation_failed",
            attempted_path=file_path,
            resolved_path=file_abs,
            reason="path_is_directory",
        )
        return False

    # Check if path is a symlink (reject symlinks for security)
    if os.path.islink(file_abs):
        _log_security_event(
            event_type="file_validation_failed",
            attempted_path=file_path,
            resolved_path=file_abs,
            reason="path_is_symlink",
        )
        return False

    # If we require existence, check if path is a regular file
    if require_exists and not os.path.isfile(file_abs):
        _log_security_event(
            event_type="file_validation_failed",
            attempted_path=file_path,
            resolved_path=file_abs,
            reason="path_not_regular_file",
        )
        return False

    return True


def _resolve_secret(secret_name: str, secrets_dir: str = "") -> str:
    """Resolve a secret from Docker secrets directory or environment variable.

    Security: Validates against path traversal attacks and only allows
    safe characters in secret names (alphanumeric, dash, underscore).
    Also validates length to prevent resource exhaustion.

    Resolution order (supports both Docker MCP Gateway and standalone usage):
    1. Direct environment variable (Docker MCP Gateway): <SECRET_NAME>
       - Docker MCP Gateway injects secrets as env vars matching the 'env:' field
       - Example: server.yml has 'env: SSH_KEY_PASSPHRASE_01' -> container gets 'SSH_KEY_PASSPHRASE_01'
    2. Prefixed environment variable (standalone/backward compatibility): MCP_SSH_SECRET_<SECRET_NAME>
       - Supports existing standalone deployments using prefixed env vars
    3. Docker secrets file: /app/secrets/<secret_name>
       - Supports file-based secret storage for standalone deployments
    """
    if not secret_name:
        return ""

    # Length validation: prevent resource exhaustion
    if len(secret_name) > MAX_SECRET_NAME_LENGTH:
        _log_security_event(
            event_type="input_length_limit_exceeded",
            attempted_path=secret_name,
            reason="secret_name_too_long",
            additional_data={
                "field": "secret_name",
                "length": len(secret_name),
                "max_length": MAX_SECRET_NAME_LENGTH,
            },
        )
        return ""

    # Try direct environment variable first (Docker MCP Gateway pattern)
    # Docker MCP Gateway injects secrets as env vars matching the 'env:' field in server.yml
    # Example: server.yml has 'env: SSH_KEY_PASSPHRASE_01' -> container gets 'SSH_KEY_PASSPHRASE_01'
    # Secrets are ONLY injected when Docker MCP Gateway runs the container (not when running manually)
    direct_env_key = secret_name.upper()
    if direct_env_key in os.environ:
        return os.environ[direct_env_key]

    # Try prefixed environment variable (standalone/backward compatibility)
    # Supports existing MCP_SSH_SECRET_<name> pattern for standalone usage
    prefixed_env_key = f"MCP_SSH_SECRET_{secret_name.upper()}"
    if prefixed_env_key in os.environ:
        return os.environ[prefixed_env_key]

    # Security validation: only allow safe characters in secret_name
    # Allowed: alphanumeric, dash, underscore
    if not secret_name.replace("-", "").replace("_", "").isalnum():
        _log_security_event(
            event_type="invalid_secret_name",
            attempted_path=secret_name,
            reason="contains_invalid_characters",
        )
        return ""

    # Reject absolute paths (for secrets, enforce relative paths only)
    if os.path.isabs(secret_name):
        _log_security_event(
            event_type="path_traversal_attempt",
            attempted_path=secret_name,
            reason="absolute_path_rejected",
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
        _log_security_event(
            event_type="path_traversal_attempt",
            attempted_path=secret_name,
            resolved_path=resolved_abs,
            reason="path_outside_allowed_directory",
            additional_data={"base_dir": base_abs},
        )
        return ""

    # Validate file path: must be regular file, not directory or symlink
    if not _validate_file_path(resolved_abs, base_abs):
        return ""

    try:
        with open(resolved_abs, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _resolve_key_path(key_path: str, keys_dir: str = "") -> str:
    """Resolve SSH key path with path traversal protection.

    Security: Validates against path traversal attacks. For absolute paths,
    validates they're within keys_dir. For relative paths, validates they
    stay within keys_dir after normalization. Also validates length to prevent
    resource exhaustion.
    """
    if not key_path:
        return ""

    # Length validation: prevent resource exhaustion
    if len(key_path) > MAX_KEY_PATH_LENGTH:
        _log_security_event(
            event_type="input_length_limit_exceeded",
            attempted_path=key_path,
            reason="key_path_too_long",
            additional_data={
                "field": "key_path",
                "length": len(key_path),
                "max_length": MAX_KEY_PATH_LENGTH,
            },
        )
        return ""

    # Security check: reject paths containing traversal patterns
    # Check for .. patterns (including encoded variants like ....//)
    if ".." in key_path:
        _log_security_event(
            event_type="path_traversal_attempt",
            attempted_path=key_path,
            reason="contains_traversal_pattern",
            additional_data={"pattern": ".."},
        )
        return ""

    # Check for backslashes with potential traversal (Windows style)
    # Convert backslashes to forward slashes for consistent checking
    normalized_for_check = key_path.replace("\\", "/")
    if ".." in normalized_for_check:
        _log_security_event(
            event_type="path_traversal_attempt",
            attempted_path=key_path,
            reason="contains_traversal_pattern",
            additional_data={"pattern": "backslash_with_traversal"},
        )
        return ""

    base_dir = keys_dir or DEFAULT_KEYS_DIR
    base_abs = os.path.abspath(base_dir)

    # Handle absolute paths
    if os.path.isabs(key_path):
        # Validate absolute path is within keys_dir for security
        resolved_abs = os.path.abspath(key_path)
        if not resolved_abs.startswith(base_abs + os.sep) and resolved_abs != base_abs:
            _log_security_event(
                event_type="path_traversal_attempt",
                attempted_path=key_path,
                resolved_path=resolved_abs,
                reason="absolute_path_outside_keys_directory",
                additional_data={"base_dir": base_abs},
            )
            return ""
        # Validate file path: reject directories and symlinks, but allow non-existent files
        # (key file will be validated when actually used in SSH connection)
        if not _validate_file_path(resolved_abs, base_abs, require_exists=False):
            return ""
        return resolved_abs

    # Handle relative paths with path traversal protection
    key_path_joined = os.path.join(base_dir, key_path)

    # Normalize path to handle any ../ sequences
    normalized_path = os.path.normpath(key_path_joined)

    # Get absolute paths for comparison
    resolved_abs = os.path.abspath(normalized_path)

    # Validate resolved path stays within keys_dir
    if not resolved_abs.startswith(base_abs + os.sep) and resolved_abs != base_abs:
        _log_security_event(
            event_type="path_traversal_attempt",
            attempted_path=key_path,
            resolved_path=resolved_abs,
            reason="path_outside_allowed_directory",
            additional_data={"base_dir": base_abs},
        )
        return ""

    # Validate file path: reject directories and symlinks, but allow non-existent files
    # (key file will be validated when actually used in SSH connection)
    if not _validate_file_path(resolved_abs, base_abs, require_exists=False):
        return ""

    return resolved_abs


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

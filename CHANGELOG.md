# Changelog

All notable changes to mcp-ssh-orchestrator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Fixed

- **Async Task Notifications (Unreleased)**: Fixed the async notification bridge so `_send_task_notification()` receives the expected `(event_type, task_id, data)` parameters, resolving "notification_failed" warnings and restoring MCP task updates.
- **Security: SSH Host Key Validation (CWE-295)**: Documented the hardening work from commit 46a8919d95ce8e0106bf9bd0c1895ebde4d771d7 that enforces Paramiko's `RejectPolicy()`, ignores unsafe host-key options, and requires known_hosts entries to mitigate MITM risks.

## [0.3.0] - 2025-11-02

### Added

- **Security Audit Logging (PR10)**: Added comprehensive security audit logging for security-relevant events
  - Created `_log_security_event()` function with structured JSON format
  - Unified all security event logging to use audit format
  - Includes both Unix timestamp (ts) and ISO 8601 timestamp (timestamp)
  - Logs attempted_path and resolved_path for path-related events
  - Logs additional context (field names, sizes, limits, patterns)
  - Event types: path_traversal_attempt, file_validation_failed, file_size_limit_exceeded, input_length_limit_exceeded, invalid_secret_name, dns_rate_limit_exceeded, command_bypass_attempt
  - Comprehensive tests for audit logging (format validation, path traversal, invalid file access, oversized files, timestamp validation)
  - Updated documentation with security audit logging format and event types
  - Enables security monitoring and incident response via structured audit trail
- **Input Length Limits for Configuration Parameters (PR9)**: Added length validation for secret names and SSH key paths
  - Secret name length limit: 100 characters (prevents oversized secret names in credentials.yml)
  - SSH key path length limit: 500 characters (prevents oversized key paths)
  - Length validation occurs before other validations (character checks, path traversal checks)
  - Security event logging for length limit violations
  - Comprehensive tests for length limits (at limit, exceeds limit, under limit)
  - Updated documentation with all input length limits (MCP tools + config parameters)
  - Complements PR6 input validation for MCP tool parameters (alias, command, tag, task_id)
- **DNS Rate Limiting (PR8)**: Added rate limiting and caching for DNS resolution to prevent DoS attacks
  - Rate limiting: Maximum 10 resolutions per second per hostname (time-window based)
  - Result caching: 60-second TTL cache for DNS results (reduces DNS server load)
  - Timeout protection: 5-second timeout for DNS resolution (prevents hanging)
  - Thread-safe implementation for concurrent access
  - Rate limit violations logged as security events
  - Comprehensive tests for rate limiting, caching, and timeout handling
  - Updated documentation with DNS rate limiting details
- **Command Denial Bypass Prevention (PR7)**: Enhanced command denial logic to prevent bypass attempts
  - Added `_normalize_command()` function that removes quotes, handles escaped characters, and normalizes whitespace
  - Enhanced `is_allowed()` method with dual checking (original + normalized command)
  - Added token-based matching for common bypass patterns
  - Added security event logging for detected bypass attempts
  - Prevents bypasses via: quote obfuscation (`'rm -rf /'`), escaped characters (`rm\ -rf\ /`), whitespace variations
  - Comprehensive tests for all bypass prevention techniques
  - Updated documentation with bypass prevention details and limitations
- **Input Validation for User-Controlled Parameters (PR6)**: Added comprehensive input validation to prevent injection attacks and resource exhaustion
  - Added validation helper functions: `_validate_alias()`, `_validate_command()`, `_validate_tag()`, `_validate_task_id()`
  - Alias validation: 100 char limit, alphanumeric/dash/underscore/dot only
  - Command validation: 10,000 char limit, rejects null bytes and control characters
  - Tag validation: 50 char limit, alphanumeric/dash/underscore/dot only
  - Task ID validation: 200 char limit, format validation
  - Applied validation to all MCP tools: `ssh_describe_host`, `ssh_plan`, `ssh_run`, `ssh_run_on_tag`, `ssh_run_async`, `ssh_cancel`, `ssh_get_task_status`, `ssh_get_task_result`, `ssh_get_task_output`, `ssh_cancel_async_task`
  - Security event logging for injection attempts (null bytes, control characters)
  - Comprehensive tests for all validation functions
  - Updated documentation with input validation requirements
- **Error Message Sanitization (PR5)**: Added error message sanitization to prevent information disclosure
  - All user-facing error messages sanitized to remove sensitive information
  - File paths, IP addresses, hostnames, credentials, and port numbers removed from user responses
  - Original detailed errors logged to stderr (structured JSON logs) for debugging
  - Added `sanitize_error()` function in `mcp_ssh/tools/utilities.py` with comprehensive pattern matching
  - Updated all exception handlers in `mcp_server.py` to sanitize errors
  - Updated `ssh_client.py` to provide generic error messages (detailed errors in exception chain)
  - Comprehensive tests for all sanitization patterns
  - Updated documentation with error sanitization details
- **YAML File Size Limits (PR4)**: Added file size validation for YAML configuration files
  - Maximum file size limit of 10MB per YAML file (`servers.yml`, `credentials.yml`, `policy.yml`)
  - File size validation before parsing to prevent resource exhaustion attacks
  - Security event logging for size limit violations
  - Added `MAX_YAML_FILE_SIZE` constant (10MB) with clear documentation
  - Updated `_load_yaml()` function with size checking logic
  - Comprehensive tests for normal, oversized, and edge case file sizes
  - Updated documentation with file size limit details
- **Path Traversal Protection (PR1 & PR2)**: Security enhancements to prevent path traversal attacks
  - **Secret Path Protection (`_resolve_secret`)**:
    - Secret name validation: only alphanumeric characters, dashes, and underscores allowed
    - Path normalization and validation to ensure paths stay within `/app/secrets`
    - Absolute path rejection for secrets (relative paths only)
    - Path traversal pattern detection and blocking (`../`, `..\\`)
    - Security event logging for all traversal attempts
  - **SSH Key Path Protection (`_resolve_key_path`)**:
    - Traversal pattern detection and rejection
    - Absolute path validation (must be within `keys_dir`)
    - Relative path validation with directory confinement
    - Cross-platform support (handles both forward slash and backslash traversal)
    - Security event logging for all traversal attempts
  - Comprehensive test coverage with 9 new security-focused tests per function
- **File Path Validation (PR3)**: Added file type validation for secret and key paths
  - Added `_validate_file_path()` helper function that validates paths are regular files
  - Rejects directories (paths must point to files, not directories)
  - Rejects symbolic links (symlinks rejected for security)
  - Integrated validation into `_resolve_secret()` and `_resolve_key_path()`
  - Added comprehensive tests for directory/symlink rejection and regular file validation
  - Updated documentation with file type validation requirements
- Path traversal protection documentation
  - Comprehensive path traversal protection section in `docs/SECURITY.md`
  - Secret name validation documentation with allowed characters and examples
  - SSH key path validation documentation with relative/absolute path rules
  - Security event logging examples for path traversal attempts
  - Updated credentials and configuration documentation with security features

### Fixed

- **Security Fix: SSH Host Key Validation (CWE-295)**: Fixed CodeQL security alert by removing unsafe Paramiko host key policies
  - Removed `AcceptPolicy` class and `AutoAddPolicy()` usage which accept unknown host keys
  - Always use `RejectPolicy()` for strict host key verification to prevent MITM attacks
  - `host_key_auto_add` and `require_known_host=False` are now deprecated and ignored
  - Deprecation warnings logged when unsafe configurations are detected
  - All SSH connections now require known_hosts entry for security
  - Updated documentation to reflect security requirements and migration path
  - References CodeQL alert: py/paramiko-missing-host-key-validation
- **CI/CD Workflow Fix**: Fixed lint and build workflows to run on documentation-only PRs
  - Removed restrictive `paths:` filter from `pull_request` triggers in `lint.yml` and `build.yml`
  - Added `check-changes` job using `dorny/paths-filter` to detect code vs documentation changes
  - Made all lint/build/test jobs conditional - they skip gracefully when only documentation changed
  - Added `skip-docs-only` job that always succeeds when no code changes detected
  - Workflows now always run (satisfies required branch protection checks) while skipping unnecessary jobs
  - Prevents "Expected - Waiting for status to be reported" blocking merges on documentation PRs
- **Repository Maintenance**: Added `plan.plan.md` to `.gitignore` to prevent planning documents from being committed

## [0.2.1] - 2025-10-31

### Changed

- Updated Dockerfile to use Python 3.13-slim with pinned SHA256 digest for reproducibility
- Switched from Python 3.14 (pre-release) to stable Python 3.13
- Changed from editable install (`pip install -e .`) to production install (`pip install .`)

### Removed

- Removed `openssh-client` from Docker image (debug tool not needed in production)
- Removed `libffi8` system dependency (not required by Python wheels)
- Removed redundant example configuration file copies in Docker image
- Removed unused PATH modification for user local bin directory

### Fixed

- Fixed trailing whitespace in Dockerfile apt-get command

## [0.2.0] - 2025-10-25

### Added

- **Async Task Support (SEP-1686)**: Complete implementation of asynchronous task execution with real-time progress monitoring
  - `ssh_run_async`: Start SSH commands asynchronously with immediate task ID return
  - `ssh_get_task_status`: Poll task status with progress percentage and elapsed time
  - `ssh_get_task_result`: Retrieve final results with complete output and metadata
  - `ssh_get_task_output`: Stream recent output lines from running tasks
  - `ssh_cancel_async_task`: Cancel running async tasks mid-execution
- **AsyncTaskManager**: Thread-safe task management with background execution
  - Task lifecycle states: pending → running → completed/failed/cancelled/timeout
  - Output buffering with line-by-line streaming
  - Result storage with configurable TTL (default 5 minutes)
  - MCP notification support for task events
- **Policy Configuration Enhancements**:
  - `task_result_ttl`: Configurable task result retention (default 300 seconds)
  - `task_progress_interval`: Progress update frequency (default 5 seconds)
  - Per-host and per-tag overrides for async task settings
- **MCP Notifications**: Server-initiated notifications for task state changes
  - `tasks/created`: Task started
  - `tasks/progress`: Periodic progress updates
  - `tasks/completed`: Task finished successfully
  - `tasks/failed`: Task finished with error
  - `tasks/cancelled`: Task was cancelled
- Production-ready Docker Compose configuration (`docker-compose.yml`) that pulls published image from ghcr.io
- Development Docker Compose configuration (`docker-compose.dev.yml`) for local builds
- Smart setup script with auto-detection for dev vs end-user modes
- Enhanced compose documentation with clear production vs development workflows
- YAML Style Guide in `docs/POLICY_REFERENCE.md` with consistent formatting guidelines
- Standardized array formatting rules for improved readability

### Changed

- Renamed docker-compose files to follow convention: `docker-compose.yml` for production (default), `docker-compose.dev.yml` for development
- Updated `compose/setup.sh` to support both dev and end-user workflows with auto-detection
- Refactored compose README to clearly distinguish production and development setup paths
- Updated main README with separate instructions for end users vs developers
- Enforced consistent YAML array formatting across all configuration files:
  - Empty arrays: inline format `[]`
  - Single items: inline format `["item"]`
  - Multiple items: multi-line format with dash syntax
- Updated all documentation examples to follow consistent style guide
- Standardized `aliases` and `tags` arrays in policy rules (multi-line for 2+ items)
- Updated all `servers.yml` tag arrays to multi-line format for consistency
- Refactored all YAML configuration files to follow unified style guidelines

### Removed

- Old `docker-compose.prod.yml` file (consolidated into default `docker-compose.yml`)

### Files Modified

- `compose/docker-compose.yml` (now default production)
- `compose/docker-compose.dev.yml` (new development file)
- `compose/setup.sh` (enhanced with dev/enduser modes)
- `compose/README.md` (completely restructured)
- `README.md` (updated Docker Compose instructions)
- `config/policy.yml`
- `config/servers.yml`
- `examples/example-policy.yml`
- `examples/example-servers.yml`
- `docs/POLICY_EXAMPLES.md`
- `docs/POLICY_REFERENCE.md`

## [0.1.3] - 2025-01-27

### Added

- Comprehensive policy configuration documentation
  - `docs/POLICY_REFERENCE.md` - Complete technical reference with all configuration options, types, defaults, and examples
  - `docs/POLICY_EXAMPLES.md` - 10+ practical configuration examples for different environments and use cases
  - `docs/POLICY_SECURITY.md` - Security best practices, troubleshooting guide, and incident response procedures
- Policy documentation links in main README.md
- Cross-references between all policy documentation files
- Comprehensive tables for all policy configuration sections (limits, network, rules, overrides)
- Real-world examples for production, development, staging, Proxmox, and network-restricted environments
- Security checklists and troubleshooting guides
- Glob pattern matching syntax documentation
- Rule evaluation order and precedence explanations

### Changed

- Updated README.md to include dedicated "Policy Configuration" section with links to comprehensive documentation
- Enhanced documentation structure with consistent cross-references between policy docs

## [0.1.2] - 2025-10-24

### Fixed

- Fixed SSH host key handling when `require_known_host` is set to false
- Added `AcceptPolicy` class to handle unknown host keys without saving them
- Resolved "Server not found in known_hosts" error when using permissive host key policies
- Improved SSH connection reliability for environments with dynamic host keys

### Changed

- Enhanced SSH client logic to properly respect `require_known_host: false` setting
- Updated host key policy handling to support three modes: strict, permissive, and auto-add

## [0.1.1] - 2025-10-22

### Fixed

- Fixed Docker build issues in CI/CD pipeline
- Resolved linting and formatting errors for automated workflows
- Fixed Docker test step to properly load built images
- Corrected exception chaining in SSH client error handling
- Fixed loop variable binding issues in progress callbacks

### Changed

- Updated Python base image to 3.14-slim for latest security patches
- Improved Docker build process with better .dockerignore configuration
- Enhanced CI/CD workflows with proper dependency management
- Updated development dependencies (black, ruff, mypy, pytest)

### Added

- Automated dependency management with Dependabot
- Comprehensive CI/CD pipeline with linting, testing, and Docker builds
- Automated code formatting and type checking
- Docker Compose setup with automated configuration
- Example configuration files and setup scripts

## [0.1.0] - 2025-10-21

### Added

- Initial release of MCP SSH Orchestrator
- Core MCP server implementation with STDIO transport
- SSH command execution with Paramiko
- Policy-based access control engine
  - Allow/deny rules with glob pattern matching
  - Per-alias and per-tag limit overrides
  - Deny substrings for dangerous commands
- Network security controls
  - IP allowlist/blocklist with CIDR support
  - Pre-connect DNS resolution verification
  - Post-connect peer IP validation
- Credential management
  - SSH key-based authentication
  - Password-based authentication
  - Docker secrets integration
  - Environment variable support for secrets
- Configuration system
  - YAML-based configuration (servers, credentials, policy)
  - Hot-reload capability
  - Example configuration files
- MCP Tools
  - `ssh_ping` - Health check
  - `ssh_list_hosts` - List configured hosts
  - `ssh_describe_host` - Get host details
  - `ssh_plan` - Dry-run command with policy check
  - `ssh_run` - Execute command on single host
  - `ssh_run_on_tag` - Execute command on tagged hosts
  - `ssh_cancel` - Cancel running commands
  - `ssh_reload_config` - Hot-reload configuration
- Execution features
  - Real-time streaming output
  - Cancellation support
  - Timeout enforcement
  - Output size limits
  - Progress callbacks
- Docker support
  - Multi-stage Dockerfile
  - Non-root user (UID 10001)
  - Health checks
  - Docker Compose configuration
- Audit logging
  - JSON-formatted logs to stderr
  - Policy decisions
  - Execution metrics
  - Network events
- Documentation
  - Comprehensive README
  - Example configurations
  - Docker Desktop integration guide
- Docker MCP Registry compliance
  - Registry-compliant server.json metadata
  - Proper versioning and tagging

### Security

- Host key verification with known_hosts
- Network egress controls
- Deny-by-default policy model
- Audit trail for all commands
- Read-only container mounts
- Non-root container execution

# Changelog

All notable changes to mcp-ssh-orchestrator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-11-02

### Added
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


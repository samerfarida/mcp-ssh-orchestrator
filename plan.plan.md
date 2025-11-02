<!-- 5215c5a7-753b-47f6-bb16-1cc9efdff15f 890e4bfa-c9fa-4bb3-8988-4824d09949c8 -->
# Security Fixes Plan - One PR Per Issue

This plan addresses 10 security vulnerabilities from CodeQL analysis, fixing them incrementally with one pull request per issue. Each PR will include tests and be validated before moving to the next.

## PR 1: Add Path Traversal Protection to `_resolve_secret`

**Files to modify:**

- `src/mcp_ssh/config.py` - Update `_resolve_secret()` function
- `tests/test_config.py` - Add path traversal test cases
- **Documentation updates:**
  - `docs/SECURITY.md` - Add path traversal protection section
  - `docs/wiki/06.2-credentials.yml.md` - Document secret path validation
  - `docs/wiki/06-Configuration.md` - Document path traversal protection

**Changes:**

- Add path normalization using `os.path.normpath()`
- Validate resolved path stays within `secrets_dir` using `os.path.abspath()` comparison
- Reject absolute paths (for secrets, enforce relative paths only)
- Add validation that secret_name contains only safe characters (alphanumeric, dash, underscore)
- Return empty string on any path traversal attempt

**Test cases to add:**

- Test path traversal with `../`
- Test path traversal with `..\\`
- Test absolute path rejection
- Test secret name with special characters
- Test directory traversal attempts
- Ensure existing tests still pass

**Security impact:** Prevents reading files outside `/app/secrets` directory via path traversal attacks.

---

## PR 2: Add Path Traversal Protection to `_resolve_key_path`

**Files to modify:**

- `src/mcp_ssh/config.py` - Update `_resolve_key_path()` function
- `tests/test_config.py` - Update existing test and add path traversal cases
- **Documentation updates:**
  - `docs/SECURITY.md` - Document key path protection
  - `docs/wiki/06.2-credentials.yml.md` - Document key path validation
  - `docs/wiki/06-Configuration.md` - Update path traversal section

**Changes:**

- Normalize paths using `os.path.normpath()`
- For relative paths: validate they stay within `keys_dir`
- For absolute paths: validate they're within `keys_dir` or reject (security decision needed - see question)
- Return empty string on path traversal attempts
- Update `test_resolve_key_path_absolute` to reflect new security behavior

**Test cases to add:**

- Test relative path with `../` traversal
- Test absolute path validation (if allowing absolute paths)
- Test empty string handling
- Ensure existing relative path tests pass

**Security impact:** Prevents accessing SSH keys outside intended directory.

---

## PR 3: Validate File Paths Are Regular Files Within Allowed Directories

**Files to modify:**

- `src/mcp_ssh/config.py` - Add file validation helper functions
- Update `_resolve_secret()` and `_resolve_key_path()` to use validation
- `tests/test_config.py` - Add tests for directory/symlink rejection
- **Documentation updates:**
  - `docs/SECURITY.md` - Document file type validation
  - `docs/wiki/06.2-credentials.yml.md` - Note file validation requirements

**Changes:**

- Add `_validate_file_path()` helper function that checks:
- Path exists and is a regular file (`os.path.isfile()`)
- Path is not a directory
- Path is not a symlink (or handle symlinks explicitly)
- Path stays within allowed base directory
- Integrate validation into secret and key path resolution
- Return empty string on validation failure

**Test cases to add:**

- Test directory path rejection
- Test symlink handling (follow or reject?)
- Test non-existent file
- Test file outside allowed directory

**Security impact:** Prevents accessing directories or symlinks that could lead to security issues.

---

## PR 4: Add File Size Limits for YAML Loading

**Files to modify:**

- `src/mcp_ssh/config.py` - Update `_load_yaml()` function
- `tests/test_config.py` - Add tests for file size limits
- **Documentation updates:**
  - `docs/SECURITY.md` - Document file size limits
  - `docs/wiki/06-Configuration.md` - Note file size constraints

**Changes:**

- Add maximum file size constant (e.g., 10MB for config files)
- Check file size before loading using `os.path.getsize()`
- Return empty dict if file exceeds size limit
- Log error when size limit exceeded

**Test cases to add:**

- Test normal sized file (should work)
- Test oversized file (should return empty dict)
- Test missing file (existing behavior maintained)

**Security impact:** Prevents resource exhaustion attacks via oversized YAML files.

---

## PR 5: Sanitize Error Messages to Prevent Information Disclosure

**Files to modify:**

- `src/mcp_ssh/mcp_server.py` - Update exception handling
- `src/mcp_ssh/ssh_client.py` - Sanitize error messages
- `tests/test_server_tools.py` - Add tests for sanitized errors
- **Documentation updates:**
  - `docs/SECURITY.md` - Document error message sanitization
  - `docs/wiki/12-Troubleshooting.md` - Note sanitized error format

**Changes:**

- Create `_sanitize_error()` helper function that:
- Removes file paths
- Removes hostnames/IPs
- Removes credential references
- Returns generic error messages for users
- Apply sanitization to all user-facing error messages
- Keep detailed errors in logs (stderr) but not in user responses
- Update all exception handlers to use sanitization

**Test cases to add:**

- Test that file paths are removed from errors
- Test that hostnames are removed
- Test that detailed errors still logged to stderr
- Ensure error messages still useful for troubleshooting

**Security impact:** Prevents leaking sensitive system information through error messages.

---

## PR 6: Add Input Validation for User-Controlled Parameters

**Files to modify:**

- `src/mcp_ssh/mcp_server.py` - Add validation helpers
- Update all `@mcp.tool()` functions with input validation
- `tests/test_server_tools.py` - Add validation tests
- **Documentation updates:**
  - `docs/SECURITY.md` - Document input validation
  - `docs/wiki/07-Tools-Reference.md` - Document input constraints

**Changes:**

- Add `_validate_alias()`, `_validate_command()`, `_validate_tag()` helpers
- Validate:
- String length limits (e.g., alias max 100 chars, command max 10000 chars)
- Allowed characters (alphanumeric, dash, underscore, dots for aliases)
- Command parameter validation (prevent null bytes, control characters)
- Apply to: `ssh_run`, `ssh_describe_host`, `ssh_run_on_tag`, `ssh_run_async`, etc.

**Test cases to add:**

- Test overly long inputs
- Test special characters in aliases
- Test null bytes in commands
- Test control characters
- Ensure valid inputs still work

**Security impact:** Prevents injection attacks and resource exhaustion via malformed inputs.

---

## PR 7: Improve Command Denial Logic to Prevent Bypasses

**Files to modify:**

- `src/mcp_ssh/policy.py` - Enhance `is_allowed()` method
- `tests/test_policy.py` - Add bypass attempt tests
- **Documentation updates:**
  - `docs/SECURITY.md` - Document command denial improvements
  - `docs/wiki/06.3-policy.yml.md` - Note bypass prevention

**Changes:**

- Keep substring matching but add additional checks:
- Normalize command (remove quotes, handle escaped characters)
- Check for command in normalized form
- Consider token-based matching for common bypasses
- Add logging when bypass attempts detected
- Document limitations of substring matching

**Test cases to add:**

- Test command with quotes: `echo "rm -rf /"`
- Test escaped commands
- Test commands with whitespace variations
- Ensure legitimate commands still work

**Security impact:** Reduces risk of command denial bypasses (note: perfect prevention may require command parsing).

---

## PR 8: Add Rate Limiting for DNS Resolution

**Files to modify:**

- `src/mcp_ssh/ssh_client.py` - Add rate limiting to `resolve_ips()`
- `tests/test_ssh.py` - Add rate limiting tests
- **Documentation updates:**
  - `docs/SECURITY.md` - Document DNS rate limiting
  - `docs/wiki/05-Security-Model.md` - Note rate limiting controls

**Changes:**

- Add simple in-memory rate limiter (time-based, e.g., max 10 resolutions per second per hostname)
- Cache DNS results with short TTL (e.g., 60 seconds)
- Add timeout to `socket.getaddrinfo()` call
- Log rate limit violations

**Test cases to add:**

- Test normal DNS resolution
- Test rate limiting triggers
- Test DNS timeout handling
- Test cached results

**Security impact:** Prevents DNS-based DoS attacks and reduces load from repeated resolutions.

---

## PR 9: Add Input Length Limits on String Parameters

**Files to modify:**

- `src/mcp_ssh/mcp_server.py` - Add length validation (may overlap with PR 6)
- `src/mcp_ssh/config.py` - Validate config file string lengths
- `tests/test_config.py` - Add length limit tests
- **Documentation updates:**
  - `docs/SECURITY.md` - Document length limits
  - `docs/wiki/07-Tools-Reference.md` - Document parameter length limits

**Changes:**

- Define constants for max lengths:
- Alias: 100 characters
- Command: 10000 characters (already exists, verify)
- Tag: 50 characters
- Secret name: 100 characters
- Key path: 500 characters
- Apply limits in all relevant functions
- Return clear error messages when limits exceeded

**Test cases to add:**

- Test each parameter at limit boundary
- Test parameters exceeding limits
- Ensure existing functionality unaffected

**Security impact:** Prevents resource exhaustion and buffer overflow risks.

---

## PR 10: Add Security Audit Logging for Path Traversal Attempts

**Files to modify:**

- `src/mcp_ssh/config.py` - Add audit logging
- Create security audit log format
- **Documentation updates:**
  - `docs/SECURITY.md` - Document security event logging
  - `docs/wiki/11-Observability-Audit.md` - Document security events

**Changes:**

- Add `_log_security_event()` function that logs to stderr in structured JSON
- Log events:
- Path traversal attempts
- Invalid file access attempts
- Oversized file attempts
- Rate limit violations
- Include: timestamp, event type, attempted path, resolved path, user context

**Test cases to add:**

- Test audit logging for path traversal
- Test audit logging for invalid files
- Verify log format is valid JSON
- Ensure logging doesn't break functionality

**Security impact:** Enables security monitoring and incident response.

---

## Testing Strategy

For each PR:

1. Run existing test suite: `pytest tests/`
2. Add new security-focused test cases
3. Run linters: `ruff check src/` and `black --check src/`
4. Run type checking: `mypy src/`
5. Manual testing with malicious inputs
6. Verify no regressions in existing functionality

## Documentation Update Strategy

For each PR:

1. **Security Documentation (`docs/SECURITY.md`)**: Add relevant security control documentation
2. **Configuration Documentation**: Update relevant wiki pages to document new security features
3. **API Documentation**: Update tool reference if input/output changes
4. **Examples**: Update examples if behavior changes affect usage

**Documentation Files to Review Per PR:**

- `docs/SECURITY.md` - Main security guide
- `docs/wiki/06-Configuration.md` - Configuration overview
- `docs/wiki/06.2-credentials.yml.md` - Credentials configuration
- `docs/wiki/06.3-policy.yml.md` - Policy configuration (if relevant)
- `docs/wiki/07-Tools-Reference.md` - Tool documentation (if API changes)
- `docs/wiki/12-Troubleshooting.md` - Troubleshooting (if error handling changes)
- `docs/wiki/11-Observability-Audit.md` - Audit/logging (if logging changes)
- `README.md` - Main readme (if major features added)

## Validation Checklist Per PR

- [ ] All new tests pass
- [ ] Existing tests still pass (no regressions)
- [ ] Code passes linting (ruff, black)
- [ ] Code passes type checking (mypy)
- [ ] Security fix tested with malicious inputs
- [ ] **Documentation updated** (security docs, wiki pages, examples)
- [ ] Code review ready

## Notes

- PR 1 and PR 2 can potentially be combined if desired, but keeping separate for focused review
- PR 6 and PR 9 have some overlap (input validation) - can be adjusted if needed
- Each PR should be small enough for focused review
- All security fixes maintain backward compatibility where possible (fail closed on invalid inputs)
- **Documentation must be updated with each PR** to reflect security improvements


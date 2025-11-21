# Scripts Directory

This directory contains utility scripts for development, testing, and validation.

## Essential Scripts (Keep)

### `validate-mcp-schema.py`

**Purpose:** Validates MCP tool definitions against MCP schema 2025-06-18.

**Usage:**

```bash
python scripts/validate-mcp-schema.py
```

**Status:** ✅ Active - Used in pre-commit hooks and CI/CD

---

### `validate-config.py`

**Purpose:** Validates YAML configuration files (servers.yml, credentials.yml, policy.yml).

**Usage:**

```bash
python scripts/validate-config.py [config_dir]
```

**Status:** ✅ Active - Used in pre-commit hooks (optional)

---

### `setup-pre-commit.sh`

**Purpose:** Sets up pre-commit hooks for developers.

**Usage:**

```bash
./scripts/setup-pre-commit.sh
```

**Status:** ✅ Active - Referenced in CONTRIBUTING.md

---

### `docker-build.sh`

**Purpose:** Helper script for building Docker images locally.

**Usage:**

```bash
./scripts/docker-build.sh
# Or with custom image name:
IMAGE_NAME=my-image:tag ./scripts/docker-build.sh
```

**Status:** ✅ Active - Referenced in documentation

---

### `docker-smoketest.sh`

**Purpose:** Smoke test Docker image with MCP Inspector.

**Usage:**

```bash
./scripts/docker-smoketest.sh
```

**Status:** ✅ Active - Referenced in documentation and CHANGELOG

---

### `test-mcp-inspector-errors.sh`

**Purpose:** Tests error handling scenarios with MCP Inspector.

**Usage:**

```bash
./scripts/test-mcp-inspector-errors.sh
```

**Status:** ✅ Active - Useful for manual testing of error paths

---

### `test-mcp-automated.py`

**Purpose:** Automated programmatic testing of all MCP tools without requiring interactive MCP Inspector.

**Usage:**

```bash
# Test with default Docker image
python3 scripts/test-mcp-automated.py

# Test with custom Docker image
python3 scripts/test-mcp-automated.py --docker-image mcp-ssh-orchestrator:dev

# Test with custom config directory
python3 scripts/test-mcp-automated.py --config-dir /path/to/config
```

**Status:** ✅ Active - Automated CI/CD testing, validates all 13 tools programmatically

---

## Notes

- **Markdownlint fixes:** Handled automatically by pre-commit hooks (no manual scripts needed)
- **Docker annotations:** Validated and implemented in `.github/workflows/release.yml`

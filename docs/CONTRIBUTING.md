# Contributing to mcp-ssh-orchestrator

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Ways to Contribute

- **Report Bugs**: Open an issue with steps to reproduce
- **Suggest Features**: Propose new functionality or improvements
- **Fix Issues**: Submit pull requests for open issues
- **Improve Documentation**: Fix typos, add examples, clarify instructions
- **Write Tests**: Increase test coverage
- **Review PRs**: Help review and test pull requests

## Getting Started

### Development Setup

1. **Fork and Clone**

   ```bash
   git clone https://github.com/YOUR_USERNAME/mcp-ssh-orchestrator
   cd mcp-ssh-orchestrator
   ```

2. **Create Virtual Environment**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

4. **Install Pre-Commit Hooks** (Optional)

   ```bash
   pip install pre-commit
   pre-commit install
   ```

### Project Structure

```
mcp-ssh-orchestrator/
├── src/mcp_ssh/          # Main package
│   ├── mcp_server.py     # MCP server entrypoint
│   ├── config.py         # Configuration loader
│   ├── ssh_client.py     # SSH client wrapper
│   ├── policy.py         # Policy engine
│   └── tools/            # Utilities
├── tests/                # Test suite
├── config/               # Default configs (gitignored)
├── examples/             # Example configs
├── docs/                 # Documentation
├── .github/workflows/    # CI/CD
└── pyproject.toml        # Package metadata
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

**Branch naming:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions/fixes

### 2. Make Changes

**Code Style:**

- Follow PEP 8 conventions
- Use type hints where helpful (but keep primitive types per instructions)
- Single-line docstrings for simple functions
- Keep functions focused and small

**MCP Rules (Critical):**

Per the project instructions:

1. ❌ NO `@mcp.prompt()` decorators
2. ❌ NO `prompt` parameter to `FastMCP()`
3. ❌ NO complex typing annotations
4. ✅ Use primitive types only (all params as `str = ""`)
5. ✅ Single-line docstrings only
6. ✅ Default to empty strings
7. ✅ All MCP tools must return strings
8. ✅ Always run in Docker
9. ✅ Log to stderr
10. ✅ Graceful error handling only

**Example MCP Tool:**

```python
@mcp.tool()
def ssh_example(alias: str = "", command: str = "") -> str:
    """Execute an example command."""
    try:
        result = do_something(alias, command)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {e}"
```

### 3. Write Tests

All new functionality should include tests.

**Test Structure:**

```python
# tests/test_feature.py
import pytest
from mcp_ssh.module import function


def test_function_success():
    """Test successful execution."""
    result = function("input")
    assert result == "expected"


def test_function_error():
    """Test error handling."""
    with pytest.raises(ValueError):
        function("invalid")
```

**Run Tests:**

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_config.py

# Run with coverage
pytest --cov=mcp_ssh --cov-report=html

# View coverage report
open htmlcov/index.html
```

### 4. Lint and Format

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/ --ignore-missing-imports

# Fix auto-fixable issues
ruff check --fix src/ tests/
```

**Pre-commit** (if installed):

```bash
pre-commit run --all-files
```

### 5. Test Docker Build

```bash
# Build image
docker build -t mcp-ssh-orchestrator:dev .

# Test import
docker run --rm mcp-ssh-orchestrator:dev python -c "import mcp_ssh; print('OK')"

# Test entrypoint (will wait for stdin)
echo '{"jsonrpc":"2.0","method":"ping","id":1}' | \
  docker run -i --rm mcp-ssh-orchestrator:dev
```

### 6. Update Documentation

If your changes affect:

- **User-facing features**: Update README.md
- **Configuration**: Update example files and docs
- **Security**: Update SECURITY.md
- **API**: Update tool docstrings

### 7. Commit Changes

**Commit Message Format:**

```
<type>: <short description>

<optional longer description>

<optional footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `refactor`: Code refactoring
- `test`: Test additions/fixes
- `chore`: Build/tooling changes

**Examples:**

```bash
git commit -m "feat: add support for ECDSA keys"
git commit -m "fix: resolve credentials from env vars correctly"
git commit -m "docs: update Docker Desktop setup instructions"
```

### 8. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Pull Request Guidelines

### PR Title

Use the same format as commit messages:

```
feat: add retry logic to SSH connections
fix: handle missing credentials gracefully
```

### PR Description

Include:

1. **Summary**: What does this PR do?
2. **Motivation**: Why is this change needed?
3. **Changes**: What was changed?
4. **Testing**: How was it tested?
5. **Screenshots**: If UI/output changes
6. **Related Issues**: Fixes #123

**Template:**

```markdown
## Summary
Brief description of changes

## Motivation
Why this change is needed

## Changes
- Added X
- Modified Y
- Removed Z

## Testing
- [ ] Unit tests pass
- [ ] Docker build succeeds
- [ ] Manually tested with...

## Related Issues
Fixes #123
```

### Checklist

Before submitting:

- [ ] Code follows project style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] Docker build succeeds
- [ ] Commit messages are clear
- [ ] No merge conflicts
- [ ] Branch is up to date with main

## Code Review Process

1. **Automated Checks**: CI must pass (lint, test, build)
2. **Manual Review**: At least one maintainer review required
3. **Changes Requested**: Address feedback and update PR
4. **Approval**: Once approved, PR can be merged
5. **Merge**: Squash and merge (or rebase if clean history)

### Review Criteria

Reviewers will check:

- Functionality: Does it work as intended?
- Tests: Are there adequate tests?
- Code Quality: Is it readable and maintainable?
- Security: Are there security implications?
- Documentation: Is it properly documented?
- Compatibility: Does it break existing functionality?

## Testing Guidelines

### Unit Tests

Test individual functions in isolation:

```python
def test_config_load():
    """Test configuration loading."""
    config = Config("/path/to/test/config")
    assert config.list_hosts() == ["test1", "test2"]
```

### Integration Tests

Test components working together:

```python
def test_ssh_execution_flow():
    """Test full SSH execution with policy."""
    # Mock SSH connection
    # Test policy enforcement
    # Verify audit logging
```

### Docker Tests

Test container behavior:

```bash
# In tests/docker_test.sh
docker run --rm mcp-ssh-orchestrator:dev python -m pytest
```

### Test Data

Use fixtures for test data:

```python
@pytest.fixture
def sample_config():
    return {
        "servers": {"hosts": [{"alias": "test1", "host": "10.0.0.1"}]},
        "credentials": {"entries": []},
        "policy": {"rules": []}
    }
```

## Documentation Guidelines

### Docstrings

**Format:**

```python
def function(param: str = "") -> str:
    """Single-line description of what the function does."""
    # Implementation
```

For complex functions (if needed):

```python
def complex_function(param1: str = "", param2: str = "") -> str:
    """
    Brief description.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    """
```

### README Updates

When adding features:

1. Update "Features" section
2. Add tool documentation
3. Update examples
4. Add to Quick Start if relevant

### Example Code

Keep examples:

- **Runnable**: User can copy-paste and run
- **Complete**: Don't omit important details
- **Commented**: Explain non-obvious parts
- **Tested**: Verify examples work

## Release Process

Maintainers only, but good to understand:

1. **Version Bump**: Update version in `pyproject.toml` and `server.json`
2. **Changelog**: Update CHANGELOG.md with release notes
3. **Tag**: Create git tag `v0.2.0`
4. **Push**: `git push origin v0.2.0`
5. **CI**: GitHub Actions builds and pushes Docker image
6. **Release**: GitHub release created automatically

## Issue Reporting

### Bug Reports

Include:

- **Description**: What's broken?
- **Steps to Reproduce**:
  1. Step one
  2. Step two
  3. Observe error
- **Expected Behavior**: What should happen?
- **Actual Behavior**: What actually happens?
- **Environment**:
  - OS (macOS, Linux, Windows)
  - Docker version
  - Python version (if local dev)
  - MCP orchestrator version
- **Logs**: Relevant error messages or stack traces
- **Configuration**: Sanitized config snippets if relevant

### Feature Requests

Include:

- **Use Case**: What problem does this solve?
- **Proposed Solution**: How should it work?
- **Alternatives**: What workarounds exist?
- **Impact**: Who benefits from this?

## Questions?

- **Issues**: Open a GitHub issue for bugs/features
- **Discussions**: Use GitHub Discussions for questions
- **Email**: [Your contact email]

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.

## Recognition

Contributors will be acknowledged in:

- GitHub contributors page
- Release notes (for significant contributions)
- README (for major features)

Thank you for contributing! 🎉


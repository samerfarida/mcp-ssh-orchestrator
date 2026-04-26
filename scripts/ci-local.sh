#!/usr/bin/env bash
set -euo pipefail

echo "[ci-local] Running local CI parity checks"

ruff check src/ tests/
black --check src/ tests/
mypy src/ --ignore-missing-imports || true
pytest --cov=mcp_ssh --cov-report=xml --cov-report=term
docker build -t mcp-ssh-orchestrator:test .
docker run --rm mcp-ssh-orchestrator:test python -c "import mcp_ssh; print('MCP SSH module imported successfully')"

echo "[ci-local] All checks completed"

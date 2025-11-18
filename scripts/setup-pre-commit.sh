#!/bin/bash
# Setup pre-commit hooks for mcp-ssh-orchestrator
#
# This script installs and configures pre-commit hooks to ensure code quality
# before commits are made to the repository.
#
# Usage:
#   ./scripts/setup-pre-commit.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Setting up pre-commit hooks for mcp-ssh-orchestrator..."
echo "Project root: $PROJECT_ROOT"

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "Error: pre-commit is not installed"
    echo "Install it with: pip install pre-commit"
    echo "Or: pip install '.[dev]'"
    exit 1
fi

# Check if .pre-commit-config.yaml exists
if [ ! -f "$PROJECT_ROOT/.pre-commit-config.yaml" ]; then
    echo "Error: .pre-commit-config.yaml not found in project root"
    exit 1
fi

# Install pre-commit hooks
cd "$PROJECT_ROOT"
pre-commit install

echo ""
echo "Pre-commit hooks installed successfully!"
echo ""
echo "To test the hooks, run:"
echo "  pre-commit run --all-files"
echo ""
echo "To skip hooks for a commit, use:"
echo "  git commit --no-verify"
echo ""

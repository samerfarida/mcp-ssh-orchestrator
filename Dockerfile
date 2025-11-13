# syntax=docker/dockerfile:1.7
# NOTE: Python 3.13 is pinned here because MCP SDK (mcp>=1.21.0) officially
# supports only Python 3.10-3.13. Python 3.14 is not yet officially supported.
# DO NOT update to Python 3.14 until MCP SDK adds official support.
# See: https://github.com/modelcontextprotocol/python-sdk
# To prevent Dependabot from bumping this, see .github/dependabot.yml
FROM python:3.13-slim@sha256:85dfbf1b566b7addfe645faea9938e81a0a01a83580b0ea05fb23706357d77fb AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_SSH_CONFIG_DIR=/app/config \
    MCP_SSH_KEYS_DIR=/app/keys \
    MCP_SSH_SECRETS_DIR=/app/secrets

# Container image metadata labels (OCI annotations)
LABEL org.opencontainers.image.source=https://github.com/samerfarida/mcp-ssh-orchestrator
LABEL org.opencontainers.image.description="A secure SSH fleet orchestrator for MCP (STDIO transport). Enforces declarative policy and audited access for Claude Desktop, Cursor, and any MCP-aware client."
LABEL org.opencontainers.image.licenses=Apache-2.0

# Non-root user
RUN useradd -u 10001 -m appuser
WORKDIR /app

# Copy project
COPY pyproject.toml README.md LICENSE requirements.txt /app/
COPY src /app/src
COPY examples /app/examples

# Install dependencies as root
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --require-hashes -r requirements.txt && \
    pip install --no-cache-dir .

# Create runtime directories and set ownership
RUN mkdir -p /app/config /app/keys /app/secrets && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Healthcheck (server exits only on fatal; this just checks python can import)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import mcp_ssh" || exit 1

# STDIO MCP entrypoint
ENTRYPOINT ["python", "-m", "mcp_ssh.mcp_server", "stdio"]
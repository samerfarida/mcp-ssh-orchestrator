# syntax=docker/dockerfile:1.7
FROM python:3.13-slim@sha256:0222b795db95bf7412cede36ab46a266cfb31f632e64051aac9806dabf840a61 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_SSH_CONFIG_DIR=/app/config \
    MCP_SSH_KEYS_DIR=/app/keys \
    MCP_SSH_SECRETS_DIR=/app/secrets

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
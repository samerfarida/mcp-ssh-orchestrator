# syntax=docker/dockerfile:1.7
FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_SSH_CONFIG_DIR=/app/config \
    MCP_SSH_KEYS_DIR=/app/keys \
    MCP_SSH_SECRETS_DIR=/app/secrets

# Install minimal OS deps for paramiko (libffi, openssh-client for debugging)
RUN apt-get update && apt-get install -y --no-install-recommends \
      openssh-client \ 
      libffi8 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -u 10001 -m appuser
WORKDIR /app

# Copy project
COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src
COPY examples /app/examples

# Create config directory and copy example configs if they exist
RUN mkdir -p /app/config
COPY examples/example-servers.yml /app/config/servers.yml.example
COPY examples/example-credentials.yml /app/config/credentials.yml.example  
COPY examples/example-policy.yml /app/config/policy.yml.example
ENV PATH="/home/appuser/.local/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Minimal directories for mounts (binds overwrite these at runtime)
RUN mkdir -p /app/keys /app/secrets && chown -R appuser:appuser /app
USER appuser

# Healthcheck (server exits only on fatal; this just checks python can import)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import mcp_ssh" || exit 1

# STDIO MCP entrypoint
ENTRYPOINT ["python", "-m", "mcp_ssh.mcp_server", "stdio"]
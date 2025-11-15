# 9. Deployment

**Purpose:** Complete guide for deploying mcp-ssh-orchestrator in production environments with security best practices.

## Overview

mcp-ssh-orchestrator is designed for **containerized deployment** with security-first principles. This guide covers production deployment, scaling, and maintenance.

## Deployment Methods

### Docker (Recommended)

**Single Container Deployment:**

```bash
# Pull the image
docker pull ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

# Run with configuration
docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  -v ~/mcp-ssh/secrets:/app/secrets:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

**Production Configuration:**

```bash
# Create secure directories
mkdir -p ~/mcp-ssh/{config,keys,secrets}
chmod 0700 ~/mcp-ssh/secrets
chmod 0400 ~/mcp-ssh/keys/*

# Run with resource limits
docker run -i --rm \
  --memory=512m \
  --cpus=1 \
  --user=10001:10001 \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  -v ~/mcp-ssh/secrets:/app/secrets:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

### Image & Provenance Verification

Before promoting a new build, validate the Sigstore signature attached to the GHCR image:

```bash
COSIGN_EXPERIMENTAL=1 cosign verify \
  --certificate-identity-regexp "https://github.com/samerfarida/mcp-ssh-orchestrator/.github/workflows/release.yml@.*" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

- Record the digest printed by `cosign verify` (or from the [package feed](https://github.com/samerfarida/mcp-ssh-orchestrator/pkgs/container/mcp-ssh-orchestrator/versions)) and pin it in your manifests.
- For air-gapped promotion, download the signature bundle produced by cosign and store it alongside the image tarball.

### Docker Compose

**Production Compose:**

```yaml
version: '3.8'

services:
  mcp-ssh:
    image: ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
    user: "10001:10001"
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1'
    volumes:
      - ./config:/app/config:ro
      - ./keys:/app/keys:ro
      - ./secrets:/app/secrets:ro
    healthcheck:
      test: ["CMD", "python", "-c", "import mcp_ssh"]
      interval: 30s
      timeout: 5s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Development Compose:**

```yaml
version: '3.8'

services:
  mcp-ssh:
    build: .
    volumes:
      - ./config:/app/config:ro
      - ./keys:/app/keys:ro
      - ./secrets:/app/secrets:ro
    environment:
      - MCP_SSH_DEBUG=1
    healthcheck:
      test: ["CMD", "python", "-c", "import mcp_ssh"]
      interval: 30s
      timeout: 5s
      retries: 3
```

## Production Setup

### 1. Configuration Setup

**Create configuration directory:**

```bash
mkdir -p /opt/mcp-ssh/{config,keys,secrets}
chown -R 10001:10001 /opt/mcp-ssh
chmod 0700 /opt/mcp-ssh/secrets
chmod 0400 /opt/mcp-ssh/keys/*
```

**Copy example configurations:**

```bash
cp examples/example-servers.yml /opt/mcp-ssh/config/servers.yml
cp examples/example-credentials.yml /opt/mcp-ssh/config/credentials.yml
cp examples/example-policy.yml /opt/mcp-ssh/config/policy.yml
```

### 2. SSH Key Management

**Generate production keys:**

```bash
# Generate Ed25519 key pair
ssh-keygen -t ed25519 -f /opt/mcp-ssh/keys/mcp_prod -C "mcp-ssh-orchestrator-prod"

# Set permissions
chmod 0400 /opt/mcp-ssh/keys/mcp_prod
chmod 0444 /opt/mcp-ssh/keys/mcp_prod.pub

# Deploy public key to target hosts
ssh-copy-id -i /opt/mcp-ssh/keys/mcp_prod.pub ubuntu@10.0.0.11
```

**Update credentials.yml:**

```yaml
entries:
  - name: "prod_admin"
    username: "ubuntu"
    key_path: "mcp_prod"
    key_passphrase_secret: "prod_key_passphrase"
    password_secret: ""
```

### 3. Policy Configuration

**Production policy.yml:**

```yaml
known_hosts_path: "/app/keys/known_hosts"

limits:
  max_seconds: 30
  max_output_bytes: 131072
  host_key_auto_add: false
  require_known_host: true
  deny_substrings:
    - "rm -rf /"
    - "shutdown*"
    - "reboot*"
    - "systemctl restart*"
    - "systemctl stop*"
    - "systemctl start*"

network:
  allow_cidrs:
    - "10.0.0.0/8"
  block_cidrs:
    - "0.0.0.0/0"
  require_known_host: true

rules:
  - action: "allow"
    aliases: ["prod-*"]
    tags: ["production"]
    commands:
      - "uptime*"
      - "df -h*"
      - "systemctl status *"
      - "journalctl --no-pager -n 20 *"

overrides:
  aliases:
    prod-db-1:
      max_seconds: 15
      max_output_bytes: 65536
```

### 4. Secrets Management

**Docker Secrets (Recommended):**

```bash
# Create secrets
echo "production-passphrase" | docker secret create mcp_prod_passphrase -
echo "admin-password" | docker secret create mcp_admin_password -

# Use in Docker Compose
services:
  mcp-ssh:
    image: ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
    secrets:
      - mcp_prod_passphrase
      - mcp_admin_password
    volumes:
      - ./config:/app/config:ro
      - ./keys:/app/keys:ro

secrets:
  mcp_prod_passphrase:
    external: true
  mcp_admin_password:
    external: true
```

**Environment Variables:**

```bash
# Set environment variables
export MCP_SSH_SECRET_PROD_KEY_PASSPHRASE="production-passphrase"
export MCP_SSH_SECRET_ADMIN_PASSWORD="admin-password"

# Use in Docker run
docker run -i --rm \
  -e MCP_SSH_SECRET_PROD_KEY_PASSPHRASE \
  -e MCP_SSH_SECRET_ADMIN_PASSWORD \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

## Resource Management

### Container Optimization

MCP SSH Orchestrator is designed to run efficiently as a single container instance per MCP client connection.

**Resource Limits:**

```yaml
# docker-compose.yml
services:
  mcp-ssh:
    image: ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1'
```

**Current Architecture:**

- One container instance per MCP client (Claude Desktop, Cursor, etc.)
- Stateless design allows horizontal scaling at the client level
- Each MCP client connects to its own orchestrator instance
- No load balancer required for single-client scenarios

**Scaling Considerations:**

- Horizontal fan-out requires external orchestration (load balancers, shared audit storage) and is not bundled with this project.
- Recommended pattern: keep one orchestrator container per MCP client session for deterministic policy enforcement.

### Health Monitoring

**Health Check Script:**

```bash
#!/bin/bash
# health-check.sh
set -e

CONTAINER=${1:-mcp-ssh}

echo "== Container health =="
docker ps --filter "name=${CONTAINER}" --filter "health=healthy"

echo "== Recent logs =="
docker logs --tail=20 "${CONTAINER}"

echo "== Config summary =="
docker exec -i "${CONTAINER}" python - <<'PY'
from mcp_ssh.config import Config
cfg = Config()
print("Hosts configured:", len(cfg.list_hosts()))
policy = cfg.get_policy() or {}
print("Policy rules:", len(policy.get("rules", [])))
print("Deny substrings:", len((policy.get("limits") or {}).get("deny_substrings", [])))
PY
```

**Structured Logging:**

- All policy/audit events are emitted as JSON on stderr. Collect them with `docker logs` or ship them to your logging stack (Loki, Elastic, CloudWatch, etc.).
- For scraping-friendly output, pipe stderr into `jq` or a log forwarder:

```bash
docker logs -f mcp-ssh | jq '.'
```

## Security Hardening

### Container Security

**Non-root execution:**

```dockerfile
# Container runs as UID 10001
RUN useradd -u 10001 -m appuser
USER appuser
```

**Resource limits:**

```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '1'
    reservations:
      memory: 256M
      cpus: '0.5'
```

**Read-only filesystem:**

```bash
docker run -i --rm \
  --read-only \
  --tmpfs /tmp \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
```

### Network Security

**Network isolation:**

```yaml
services:
  mcp-ssh:
    image: ghcr.io/samerfarida/mcp-ssh-orchestrator:latest
    networks:
      - mcp-network
    volumes:
      - ./config:/app/config:ro
      - ./keys:/app/keys:ro

networks:
  mcp-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

**Firewall rules:**

```bash
# Allow only necessary ports
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw deny 2376/tcp  # Docker daemon
ufw deny 2377/tcp  # Docker swarm
```

## Maintenance and Updates

### Configuration Updates

**Hot reload:**

```bash
# Update configuration files
vim /opt/mcp-ssh/config/policy.yml

# Reload without restart
docker exec mcp-ssh-1 python -c "
from mcp_ssh.mcp_server import reload_config
reload_config()
"
```

**Rolling updates:**

```bash
# Update to new version
docker pull ghcr.io/samerfarida/mcp-ssh-orchestrator:latest

# Rolling update
docker service update --image ghcr.io/samerfarida/mcp-ssh-orchestrator:latest mcp-ssh
```

### Backup and Recovery

**Configuration backup:**

```bash
#!/bin/bash
# backup-config.sh

BACKUP_DIR="/opt/backups/mcp-ssh"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" \
  -C /opt/mcp-ssh config/ keys/

# Keep only last 7 days
find "$BACKUP_DIR" -name "config_*.tar.gz" -mtime +7 -delete
```

**Disaster recovery:**

```bash
#!/bin/bash
# restore-config.sh

BACKUP_FILE="$1"
RESTORE_DIR="/opt/mcp-ssh"

# Stop services
docker-compose down

# Restore configuration
tar -xzf "$BACKUP_FILE" -C "$RESTORE_DIR"

# Restart services
docker-compose up -d
```

## Troubleshooting

### Common Issues

**Container won't start:**

```bash
# Check logs
docker logs mcp-ssh-1

# Check configuration
docker exec mcp-ssh-1 python -c "
from mcp_ssh.config import Config
config = Config('/app/config')
print('Config valid:', config.validate())
"
```

**SSH connection failures:**

```bash
# Test SSH connectivity
ssh -i /opt/mcp-ssh/keys/mcp_prod ubuntu@10.0.0.11

# Check host key verification
docker exec mcp-ssh-1 ssh-keyscan 10.0.0.11
```

**Policy issues:**

```bash
# Test policy rules
docker exec mcp-ssh-1 python -c "
from mcp_ssh.policy import Policy
policy = Policy('/app/config/policy.yml')
result = policy.evaluate('prod-web-1', 'uptime', ['production'])
print('Policy result:', result)
"
```

## Next Steps

- **[Integrations](10-Integrations)** - MCP client setup and configuration
- **[Observability & Audit](11-Observability-Audit)** - Monitoring and compliance
- **[Troubleshooting](12-Troubleshooting)** - Common deployment issues
- **[Security Model](05-Security-Model)** - Security architecture details

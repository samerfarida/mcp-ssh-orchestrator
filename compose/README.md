# MCP-SSH-ORCHESTRATOR — Compose Environment

This directory provides Docker Compose configurations for the
[`mcp-ssh-orchestrator`](https://github.com/samerfarida/mcp-ssh-orchestrator)
MCP (Model Context Protocol) server.

## Choose Your Setup

We provide two Docker Compose files depending on your use case:

| File | Purpose | When to Use |
|------|---------|-------------|
| `docker-compose.yml` | **Production/End User** - Pulls published image | For end users who want to use the published image (default) |
| `docker-compose.dev.yml` | **Development/Testing** - Builds from local source | For developers and contributors working on the codebase |

---

## Quick Start (End Users - Recommended)

If you just want to use the tool and don't plan to modify the code:

1. **Create configuration directories:**

```bash
   mkdir -p ~/mcp-ssh/{config,keys,secrets}

```

1. **Copy example configurations:**

```bash
   # If you've cloned the repo
   cd mcp-ssh-orchestrator
   cp examples/example-servers.yml ~/mcp-ssh/config/servers.yml
   cp examples/example-credentials.yml ~/mcp-ssh/config/credentials.yml
   cp examples/example-policy.yml ~/mcp-ssh/config/policy.yml

   # Edit these files with your actual hosts and credentials

```

1. **Add your SSH keys:**

```bash
   cp ~/.ssh/id_ed25519 ~/mcp-ssh/keys/
   chmod 0400 ~/mcp-ssh/keys/id_ed25519
   cp ~/.ssh/known_hosts ~/mcp-ssh/keys/known_hosts  # optional but recommended

```

1. **Bootstrap with the setup script (recommended):**

```bash
   cd mcp-ssh-orchestrator/compose
   ./setup.sh enduser   # or simply ./setup.sh (auto-detects)

```

   This creates `config/`, `keys/`, `secrets/`, and `.env`, copying the latest example configs.

1. **Run with compose (default production setup):**

```bash
   docker compose up

```

The production compose file pulls `ghcr.io/samerfarida/mcp-ssh-orchestrator:latest` by default.

---

## Development Setup (For Contributors)

If you're developing or contributing to the project:

1. **Use the setup script (auto-detects dev mode in repo):**

```bash
   cd compose
   ./setup.sh dev

```

   Or just:

```bash
   ./setup.sh

```

1. **Run with development compose (builds from source):**

```bash
   docker compose -f docker-compose.dev.yml up --build

```

This will build the container from the local Dockerfile in the repository root.

---

## What's Included

| File | Purpose |
|------|----------|
| `docker-compose.yml` | **Prod**: Pulls published image from ghcr.io (default) |
| `docker-compose.dev.yml` | **Dev**: Builds container from local source |
| `setup.sh` | Automated setup script for directories, configs, and `.env` stub |
| `README.md` | You're reading it! Usage guide and examples |

---

## Prerequisites

Before running the container:

1. Ensure **Docker** and **Docker Compose v2+** are installed.
1. **For production use**: Clone the repo or copy example configs to your chosen location.
1. **For development**: Use the automated setup script:

```bash
   cd compose
   ./setup.sh dev

```

   This will:

- Create required directories (`../config`, `../keys`, `../secrets`)
- Copy example configuration files from `../examples/`
- Generate a `.env` stub you can customize

   **Note**: The script auto-detects if you're in the repo, so just `./setup.sh` works too.

**For end users**: You can also fetch the script directly:

```bash
   mkdir -p ~/mcp-ssh && cd ~/mcp-ssh
   curl -fsSLO https://raw.githubusercontent.com/samerfarida/mcp-ssh-orchestrator/main/compose/setup.sh
   chmod +x setup.sh
   ./setup.sh enduser

```

1. Add your SSH private keys and password files under:

- `../keys` — SSH key files (e.g., id_ed25519)
- `../secrets` — password or passphrase files

---

## Configuration

### Environment Variables

The `.env` file is optional. It lets you remap where configs/secrets live *inside* the container or inject Docker secrets as environment variables.

Example `.env`:

```env
# Override only if you mount to different locations
# MCP_SSH_CONFIG_DIR=/app/config
# MCP_SSH_KEYS_DIR=/app/keys
# MCP_SSH_SECRETS_DIR=/app/secrets

# Example secret injection
# MCP_SSH_SECRET_DB_PASSWORD=supersecretvalue

```

---

## Running the Server

### Option A: Production Mode (End Users)

Pull and run the published image (default):

```bash
# From the compose directory
docker compose up

```

This:

- Pulls the `ghcr.io/samerfarida/mcp-ssh-orchestrator:latest` image
- Mounts `../config`, `../keys`, and `../secrets` as read-only volumes
- Launches the MCP server in STDIO mode

### Option B: Development Mode (Contributors)

Build from local source:

```bash
# From the compose directory
docker compose -f docker-compose.dev.yml up --build

```

This:

- Builds the container from the local Dockerfile
- Mounts `../config`, `../keys`, and `../secrets` as read-only volumes
- Launches the MCP server in STDIO mode

**Note**: The `--build` flag ensures changes to the source code are included.

### Verify It's Running

You should see startup logs like:

```json
{"evt": "server_start", "tool": "mcp-ssh-orchestrator", "mode": "stdio"}

```

---

## Testing from Claude Desktop

**For Production (using published image - default):**

Add this to your Claude Desktop config.json:

```json
{
  "mcpServers": {
    "mcp-ssh-orchestrator": {
      "command": "docker",
      "args": [
        "compose",
        "-f",
        "/ABS/PATH/mcp-ssh-orchestrator/compose/docker-compose.yml",
        "run",
        "--rm",
        "mcp-ssh"
      ]
    }
  }
}

```

**For Development (using local build):**

```json
{
  "mcpServers": {
    "mcp-ssh-orchestrator": {
      "command": "docker",
      "args": [
        "compose",
        "-f",
        "/ABS/PATH/mcp-ssh-orchestrator/compose/docker-compose.dev.yml",
        "run",
        "--rm",
        "mcp-ssh"
      ]
    }
  }
}

```

> **Important**: Replace `/ABS/PATH/mcp-ssh-orchestrator/` with your actual directory path.

**Alternative**: You can also use the direct Docker run command (simpler, no compose needed):

```json
{
  "mcpServers": {
    "ssh-orchestrator": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/config:/app/config:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/keys:/app/keys:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/secrets:/app/secrets:ro",
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:latest"
      ]
    }
  }
}

```

---

## Useful Commands

### Production Mode (Default)

| Action | Command |
|--------|---------|
| Check logs | `docker compose logs -f` |
| Pull latest image | `docker compose pull` |
| Stop everything | `docker compose down -v` |

### Development Mode

| Action | Command |
|--------|---------|
| Check logs | `docker compose -f docker-compose.dev.yml logs -f` |
| Rebuild image | `docker compose -f docker-compose.dev.yml build --no-cache` |
| Stop everything | `docker compose -f docker-compose.dev.yml down -v` |
| Clean old images | `docker system prune -f` |

---

## Developer Notes

- The server uses STDIO transport only.
- Default config path: /app/config
- Default entrypoint: `python -m mcp_ssh.mcp_server stdio`
- Tag fan-out and async jobs still flow through the same deny-by-default policy engine.
- Policy enforcement uses glob patterns (`fnmatch`), paired with hard-coded deny substrings.

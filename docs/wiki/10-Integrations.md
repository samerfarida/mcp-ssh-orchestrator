# 10. Integrations

**Purpose:** Guide for integrating mcp-ssh-orchestrator with MCP clients like Claude Desktop, OpenAI Codex, and custom applications.

## Overview

mcp-ssh-orchestrator integrates with MCP clients through the **stdio transport** protocol. This section covers setup for popular MCP clients and custom integrations.

## Common Local Setup

Complete these steps once on the machine where your MCP client (Cursor, Claude Desktop, etc.) runs. Replace `/Users/YOUR_USERNAME` with your absolute path and adjust filenames if you use non-default keys.

**1. Pull the image:**

```bash
docker pull ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3
```

**2. Create configuration directories:**

```bash
mkdir -p ~/mcp-ssh/{config,keys,secrets}
```

**3. Copy example configuration files:**

```bash
cp examples/example-servers.yml ~/mcp-ssh/config/servers.yml
cp examples/example-credentials.yml ~/mcp-ssh/config/credentials.yml
cp examples/example-policy.yml ~/mcp-ssh/config/policy.yml
```

**4. Add SSH materials:**

```bash
cp ~/.ssh/id_ed25519 ~/mcp-ssh/keys/
chmod 0400 ~/mcp-ssh/keys/id_ed25519
# (optional) Restrict trusted hosts
cp ~/.ssh/known_hosts ~/mcp-ssh/keys/known_hosts
```

**5. Populate secrets files (optional but recommended):**

```text
~/mcp-ssh/secrets/
├── prod_db_password.txt
└── jump_host_passphrase.txt
```

Reference these files in `credentials.yml` to keep sensitive values out of environment variables.

Once the shared setup is in place, connect your MCP client using the appropriate guide below.

## Cursor Integration

1. **Run a long-lived container** (prevents Cursor from launching multiple instances):

   ```bash
   docker run -d --name mcp-ssh-orchestrator \
     -v ~/mcp-ssh/config:/app/config:ro \
     -v ~/mcp-ssh/keys:/app/keys:ro \
     -v ~/mcp-ssh/secrets:/app/secrets:ro \
     ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3
   ```

   Restart it later with `docker start mcp-ssh-orchestrator` if needed.

2. **Configure Cursor** (`~/.cursor/mcp.json` on macOS/Linux):

   ```json
   {
     "mcpServers": {
       "mcp-ssh-orchestrator": {
         "command": "docker",
         "args": [
           "start",
           "-a",
           "mcp-ssh-orchestrator"
         ],
         "env": {
           "PYTHONUNBUFFERED": "1"
         }
       }
     }
   }
   ```

   Notes:
   - `docker start -a` attaches Cursor’s multiple MCP clients (chat, composer, code actions) to the same container.
   - Prefer ephemeral containers instead? Replace the args with the `docker run -i --rm …` command from the Claude Desktop example.

3. **Validate the integration:** launch Cursor, run `ssh_list_hosts`, and confirm activity in `docker logs mcp-ssh-orchestrator`.

## Claude Desktop Integration

### Basic Setup

Configure Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3"
      ]
    }
  }
}
```

On Windows the path is `%APPDATA%\Claude\claude_desktop_config.json`.

### Advanced Configuration

#### With Environment Variables for Secrets

```json
{
  "mcpServers": {
    "ssh-orchestrator": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e", "MCP_SSH_SECRET_PROD_PASSWORD=your-password",
        "-e", "MCP_SSH_SECRET_KEY_PASSPHRASE=your-passphrase",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/config:/app/config:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/keys:/app/keys:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/secrets:/app/secrets:ro",
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3"
      ]
    }
  }
}
```

#### With Resource Limits

```json
{
  "mcpServers": {
    "ssh-orchestrator": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--memory=512m",
        "--cpus=1",
        "--user=10001:10001",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/config:/app/config:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/keys:/app/keys:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh/secrets:/app/secrets:ro",
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3"
      ]
    }
  }
}
```

## Docker Desktop Integration

### Using Docker MCP Toolkit

#### Step 1: Install Docker Desktop

Install Docker Desktop with the MCP Toolkit extension enabled.

#### Step 2: Configure MCP Toolkit

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
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3"
      ]
    }
  }
}
```

#### Step 3: Test the integration

```bash
# Test MCP server
docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  -v ~/mcp-ssh/secrets:/app/secrets:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3
```

## OpenAI Codex Integration

### Via Docker MCP Toolkit

#### Step 1: Install Docker MCP Toolkit

#### Step 2: Configure Codex integration

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
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3"
      ]
    }
  }
}
```

#### Step 3: Test with Codex

```bash
# Test MCP tools
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_ping","arguments":{}},"id":1}' | \
  docker run -i --rm \
    -v ~/mcp-ssh/config:/app/config:ro \
    -v ~/mcp-ssh/keys:/app/keys:ro \
    -v ~/mcp-ssh/secrets:/app/secrets:ro \
    ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3
```

## Custom Application Integration

### Python Integration

**Using MCP SDK:**

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # Configure server parameters
    server_params = StdioServerParameters(
        command="docker",
        args=[
            "run", "-i", "--rm",
            "-v", "/path/to/config:/app/config:ro",
            "-v", "/path/to/keys:/app/keys:ro",
            "-v", "/path/to/secrets:/app/secrets:ro",
            "ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3"
        ]
    )
    
    # Create client session
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize session
            await session.initialize()
            
            # List available tools
            tools = await session.list_tools()
            print("Available tools:", tools)
            
            # Execute SSH command
            result = await session.call_tool(
                "ssh_run",
                {"alias": "web1", "command": "uptime"}
            )
            print("Command result:", result)

if __name__ == "__main__":
    asyncio.run(main())
```

### Node.js Integration

**Using MCP client library:**

```javascript
const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');
const { spawn } = require('child_process');

async function main() {
  // Create transport
  const transport = new StdioClientTransport({
    command: 'docker',
    args: [
      'run', '-i', '--rm',
      '-v', '/path/to/config:/app/config:ro',
      '-v', '/path/to/keys:/app/keys:ro',
      '-v', '/path/to/secrets:/app/secrets:ro',
      'ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3'
    ]
  });
  
  // Create client
  const client = new Client({
    name: 'ssh-orchestrator-client',
    version: '1.0.0'
  }, {
    capabilities: {}
  });
  
  // Connect
  await client.connect(transport);
  
  // List tools
  const tools = await client.listTools();
  console.log('Available tools:', tools);
  
  // Execute SSH command
  const result = await client.callTool({
    name: 'ssh_run',
    arguments: {
      alias: 'web1',
      command: 'uptime'
    }
  });
  
  console.log('Command result:', result);
  
  // Disconnect
  await client.close();
}

main().catch(console.error);
```

## Multi-Environment Setup

### Development Environment

#### Claude Desktop config for development

```json
{
  "mcpServers": {
    "ssh-orchestrator-dev": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e", "MCP_SSH_DEBUG=1",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh-dev/config:/app/config:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh-dev/keys:/app/keys:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh-dev/secrets:/app/secrets:ro",
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3"
      ]
    }
  }
}
```

### Staging Environment

#### Claude Desktop config for staging

```json
{
  "mcpServers": {
    "ssh-orchestrator-staging": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh-staging/config:/app/config:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh-staging/keys:/app/keys:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh-staging/secrets:/app/secrets:ro",
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3"
      ]
    }
  }
}
```

### Production Environment

#### Claude Desktop config for production

```json
{
  "mcpServers": {
    "ssh-orchestrator-prod": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--memory=512m",
        "--cpus=1",
        "--user=10001:10001",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh-prod/config:/app/config:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh-prod/keys:/app/keys:ro",
        "-v", "/Users/YOUR_USERNAME/mcp-ssh-prod/secrets:/app/secrets:ro",
        "ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3"
      ]
    }
  }
}
```

## Testing Integrations

### Health Check

**Test MCP server connectivity:**

```bash
# Test ping
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_ping","arguments":{}},"id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  -v ~/mcp-ssh/secrets:/app/secrets:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3
```

**Test host listing:**

```bash
# List hosts
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_list_hosts","arguments":{}},"id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  -v ~/mcp-ssh/secrets:/app/secrets:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3
```

### Command Testing

**Test policy with dry-run:**

```bash
# Test policy
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_plan","arguments":{"alias":"web1","command":"uptime"}},"id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  -v ~/mcp-ssh/secrets:/app/secrets:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3
```

**Execute test command:**

```bash
# Execute command
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ssh_run","arguments":{"alias":"web1","command":"uptime"}},"id":1}' | \
  docker run -i --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/keys:/app/keys:ro \
  -v ~/mcp-ssh/secrets:/app/secrets:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3
```

## Troubleshooting

### Common Issues

**MCP server not responding:**

```bash
# Check container logs
docker logs $(docker ps -q --filter "ancestor=ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3")

# Test container health
docker run --rm ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3 python -c "import mcp_ssh; print('OK')"
```

**Configuration errors:**

```bash
# Validate configuration
docker run --rm \
  -v ~/mcp-ssh/config:/app/config:ro \
  -v ~/mcp-ssh/secrets:/app/secrets:ro \
  ghcr.io/samerfarida/mcp-ssh-orchestrator:0.3.3 \
  python -c "
from mcp_ssh.config import Config
config = Config('/app/config')
print('Config valid:', config.validate())
"
```

**SSH connection issues:**

```bash
# Test SSH connectivity
ssh -i ~/mcp-ssh/keys/id_ed25519 ubuntu@10.0.0.11

# Check host key verification
ssh-keyscan 10.0.0.11 >> ~/mcp-ssh/keys/known_hosts
```

## Next Steps

- **[Deployment](09-Deployment)** - Production deployment guide
- **[Observability & Audit](11-Observability-Audit)** - Monitoring and compliance
- **[Troubleshooting](12-Troubleshooting)** - Common integration issues
- **[Usage Cookbook](08-Usage-Cookbook)** - Practical usage examples

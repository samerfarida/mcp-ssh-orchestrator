#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="${IMAGE_NAME:-mcp-ssh-orchestrator:dev}"
CONFIG_ROOT="$(mktemp -d)"
CONFIG_DIR="${CONFIG_ROOT}/config"
KEYS_DIR="${CONFIG_ROOT}/keys"
SECRETS_DIR="${CONFIG_ROOT}/secrets"

cleanup() {
    rm -rf "${CONFIG_ROOT}"
}
trap cleanup EXIT

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "[test-mcp-inspector-errors] Missing required command: $1" >&2
        exit 1
    fi
}

require_cmd docker
require_cmd npx

mkdir -p "${CONFIG_DIR}" "${KEYS_DIR}" "${SECRETS_DIR}"

echo "[test-mcp-inspector-errors] Preparing test configuration for error scenarios"
echo "[test-mcp-inspector-errors] Config directory: ${CONFIG_ROOT}"

# Create servers.yml with hosts that will fail (invalid hosts for connection testing)
cat > "${CONFIG_DIR}/servers.yml" <<'EOF'
hosts:
  - alias: "valid-host"
    host: "127.0.0.1"
    port: 22
    credentials: "test-cred"
    tags: ["test"]
  - alias: "invalid-host-1"
    host: "192.0.2.1"  # TEST-NET-1 (RFC 5737) - will fail to connect
    port: 22
    credentials: "test-cred"
    tags: ["test"]
  - alias: "invalid-host-2"
    host: "192.0.2.2"  # TEST-NET-1 (RFC 5737) - will fail to connect
    port: 22
    credentials: "test-cred"
    tags: ["test"]
  - alias: "dns-fail-host"
    host: "this-hostname-does-not-exist-12345.invalid"
    port: 22
    credentials: "test-cred"
    tags: ["test"]
EOF

# Create credentials.yml
cat > "${CONFIG_DIR}/credentials.yml" <<'EOF'
entries:
  - name: "test-cred"
    username: "testuser"
    key_path: "test_key"
EOF

# Create policy.yml that allows uptime
cat > "${CONFIG_DIR}/policy.yml" <<'EOF'
limits:
  max_seconds: 60
rules:
  - action: "allow"
    aliases: ["*"]
    tags: []
    commands: ["uptime*"]
network:
  allowlist: ["127.0.0.0/8", "192.0.2.0/24"]
EOF

# Create placeholder key
cat > "${KEYS_DIR}/test_key" <<'EOF'
-----BEGIN PRIVATE KEY-----
placeholder
-----END PRIVATE KEY-----
EOF
chmod 600 "${KEYS_DIR}/test_key"

# Create known_hosts (empty for testing)
touch "${KEYS_DIR}/known_hosts"

echo ""
echo "[test-mcp-inspector-errors] Test Configuration:"
echo "  - valid-host: 127.0.0.1 (may succeed if SSH server running)"
echo "  - invalid-host-1: 192.0.2.1 (will fail - connection refused/timeout)"
echo "  - invalid-host-2: 192.0.2.2 (will fail - connection refused/timeout)"
echo "  - dns-fail-host: invalid hostname (will fail - DNS resolution)"
echo ""
echo "[test-mcp-inspector-errors] Launching MCP Inspector to test error handling"
echo "[test-mcp-inspector-errors] Inspector will open in your browser"
echo ""
echo "Test Scenarios to verify:"
echo "  1. Run 'ssh_run' with alias='invalid-host-1' and command='uptime'"
echo "     - Should return error message (not crash)"
echo "     - Error should be specific (e.g., 'SSH connection refused' or 'SSH connection timeout')"
echo "     - Error should NOT contain IP addresses or sensitive paths"
echo ""
echo "  2. Run 'ssh_run_on_tag' with tag='test' and command='uptime'"
echo "     - Should return results for all 4 hosts"
echo "     - Some hosts should have exit_code: -1 (failed)"
echo "     - Some hosts may have exit_code: 0 (succeeded if SSH server available)"
echo "     - Failed hosts should have specific error messages in 'output' field"
echo "     - Verify that one host failure doesn't stop other hosts"
echo ""
echo "  3. Run 'ssh_run_async' with alias='invalid-host-1' and command='uptime'"
echo "     - Should return task_id immediately"
echo "     - Use 'ssh_get_task_status' to check status"
echo "     - Use 'ssh_get_task_result' when status is 'failed'"
echo "     - Verify error message is sanitized and specific"
echo ""
echo "  4. Verify error messages:"
echo "     - Are user-friendly and actionable"
echo "     - Do NOT contain IP addresses"
echo "     - Do NOT contain file paths"
echo "     - Do NOT contain hostnames"
echo "     - Are specific (not just 'SSH connection failed')"
echo ""
echo "Press Ctrl+C to stop the inspector when done testing"
echo ""

npx @modelcontextprotocol/inspector \
    docker run -i --rm \
    -v "${CONFIG_DIR}:/app/config:ro" \
    -v "${KEYS_DIR}:/app/keys:ro" \
    -v "${SECRETS_DIR}:/app/secrets:ro" \
    "${IMAGE_NAME}"


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
        echo "[docker-smoketest] Missing required command: $1" >&2
        exit 1
    fi
}

require_cmd docker
require_cmd npx

mkdir -p "${CONFIG_DIR}" "${KEYS_DIR}" "${SECRETS_DIR}"

echo "[docker-smoketest] Preparing sample configuration under ${CONFIG_ROOT}"
cp "${REPO_ROOT}/examples/example-servers.yml" "${CONFIG_DIR}/servers.yml"
cp "${REPO_ROOT}/examples/example-credentials.yml" "${CONFIG_DIR}/credentials.yml"
cp "${REPO_ROOT}/examples/example-policy.yml" "${CONFIG_DIR}/policy.yml"

create_secret() {
    local name="$1"
    if [ ! -f "${SECRETS_DIR}/${name}" ]; then
        echo "placeholder-${name}" > "${SECRETS_DIR}/${name}"
    fi
}

for secret in prod_admin_passphrase stg_deploy_key_passphrase lab_maint_password ops_key_passphrase ops_password; do
    create_secret "${secret}"
done

create_key() {
    local path="$1"
    local full_path="${KEYS_DIR}/${path}"
    mkdir -p "$(dirname "${full_path}")"
    if [ ! -f "${full_path}" ]; then
        cat <<'EOF' > "${full_path}"
-----BEGIN PRIVATE KEY-----
placeholder
-----END PRIVATE KEY-----
EOF
        chmod 600 "${full_path}"
    fi
}

create_key "prod/id_ed25519"
create_key "staging/id_rsa_encrypted"
create_key "shared/id_rsa_encrypted"

echo "[docker-smoketest] Launching MCP Inspector via npm to connect to Docker image '${IMAGE_NAME}'"
echo "[docker-smoketest] Inspector shortcuts:"
echo "  - Run 'ssh_list_hosts' to confirm discovery"
echo "  - Open the Resources tab to browse ssh://hosts and ssh://host/{alias}"
echo "  - Execute 'ssh_run' + 'ssh_plan' to validate policy pathways"

npx @modelcontextprotocol/inspector \
    docker run -i --rm \
    -v "${CONFIG_DIR}:/app/config:ro" \
    -v "${KEYS_DIR}:/app/keys:ro" \
    -v "${SECRETS_DIR}:/app/secrets:ro" \
    "${IMAGE_NAME}"

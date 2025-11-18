#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="${IMAGE_NAME:-mcp-ssh-orchestrator:dev}"
DOCKERFILE_PATH="${DOCKERFILE_PATH:-${REPO_ROOT}/Dockerfile}"

if ! command -v docker >/dev/null 2>&1; then
    echo "[docker-build] Docker CLI not found in PATH. Install Docker Desktop or docker-ce first." >&2
    exit 1
fi

echo "[docker-build] Building image '${IMAGE_NAME}' from ${DOCKERFILE_PATH}"
docker build --file "${DOCKERFILE_PATH}" --tag "${IMAGE_NAME}" "${REPO_ROOT}"
echo "[docker-build] Image '${IMAGE_NAME}' ready."

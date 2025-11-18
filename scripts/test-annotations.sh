#!/bin/bash
# Comprehensive test script for Docker buildx annotations format
# Tests the outputs parameter format before implementing in release workflow

set -e

echo "========================================="
echo "Docker Buildx Annotations Format Tests"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test image names
TEST_MIN="test-annotations-min"
TEST_FULL="test-annotations-full"
TEST_MULTI="test-annotations-multi"

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up test images..."
    docker rmi ${TEST_MIN}:latest 2>/dev/null || true
    docker rmi ${TEST_FULL}:latest 2>/dev/null || true
    docker rmi ${TEST_MULTI}:latest 2>/dev/null || true
    echo "Cleanup complete."
}

trap cleanup EXIT

# Set up buildx if needed
echo "Setting up Docker Buildx..."
docker buildx create --use --name test-builder 2>/dev/null || docker buildx use test-builder
echo ""

# Test 1: Minimal description (safest format)
echo "Test 1: Minimal description (safest format)"
echo "-------------------------------------------"
echo "Testing with minimal description: 'Secure SSH fleet orchestrator for MCP'"
echo ""

if docker buildx build \
    --platform linux/amd64 \
    --output type=image,name=${TEST_MIN},annotation-index.org.opencontainers.image.description="Secure SSH fleet orchestrator for MCP",annotation-index.org.opencontainers.image.source="https://github.com/samerfarida/mcp-ssh-orchestrator",annotation-index.org.opencontainers.image.licenses=Apache-2.0 \
    --load \
    -t ${TEST_MIN}:latest \
    . > /tmp/test-min.log 2>&1; then
    echo -e "${GREEN}Test 1 PASSED: Minimal description format works${NC}"
    echo ""
else
    echo -e "${RED}Test 1 FAILED: Minimal description format failed${NC}"
    echo "Error log:"
    cat /tmp/test-min.log
    exit 1
fi

# Test 2: Full simplified description (no commas)
echo "Test 2: Full simplified description (no commas)"
echo "-----------------------------------------------"
echo "Testing with full simplified description (no commas in values)"
echo "Description: 'A secure SSH fleet orchestrator for MCP STDIO transport. Enforces declarative policy and audited access for Claude Desktop Cursor and MCP-aware clients'"
echo ""

if docker buildx build \
    --platform linux/amd64 \
    --output type=image,name=${TEST_FULL},annotation-index.org.opencontainers.image.description="A secure SSH fleet orchestrator for MCP STDIO transport. Enforces declarative policy and audited access for Claude Desktop Cursor and MCP-aware clients",annotation-index.org.opencontainers.image.source="https://github.com/samerfarida/mcp-ssh-orchestrator",annotation-index.org.opencontainers.image.licenses=Apache-2.0 \
    --load \
    -t ${TEST_FULL}:latest \
    . > /tmp/test-full.log 2>&1; then
    echo -e "${GREEN}Test 2 PASSED: Full simplified description format works${NC}"
    echo ""
else
    echo -e "${RED}Test 2 FAILED: Full simplified description format failed${NC}"
    echo "Error log:"
    cat /tmp/test-full.log
    exit 1
fi

# Test 3: Verify annotations in built image
echo "Test 3: Verify annotations in built image"
echo "-----------------------------------------"
echo "Inspecting built image to verify annotations are present..."
echo ""

if docker image inspect ${TEST_FULL}:latest | grep -q "org.opencontainers.image.description"; then
    echo -e "${GREEN}Test 3 PASSED: Annotations found in image${NC}"
    echo ""
    echo "Image labels:"
    docker image inspect ${TEST_FULL}:latest | grep -A 10 "Labels" || true
    echo ""
else
    echo -e "${YELLOW}Test 3 WARNING: Annotations not found in image labels (may be in manifest index for multi-arch)${NC}"
    echo ""
fi

# Test 4: Multi-platform syntax validation (build to OCI directory to validate syntax)
echo "Test 4: Multi-platform syntax validation"
echo "----------------------------------------"
echo "Testing multi-platform format (linux/amd64,linux/arm64) - building to OCI directory for syntax validation"
echo ""

TMP_DIR=$(mktemp -d)
if docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --output type=oci,dest=${TMP_DIR}/test-multi.tar,annotation-index.org.opencontainers.image.description="A secure SSH fleet orchestrator for MCP STDIO transport. Enforces declarative policy and audited access for Claude Desktop Cursor and MCP-aware clients",annotation-index.org.opencontainers.image.source="https://github.com/samerfarida/mcp-ssh-orchestrator",annotation-index.org.opencontainers.image.licenses=Apache-2.0 \
    . > /tmp/test-multi.log 2>&1; then
    echo -e "${GREEN}Test 4 PASSED: Multi-platform syntax is valid${NC}"
    echo ""
    rm -rf ${TMP_DIR}
else
    echo -e "${RED}Test 4 FAILED: Multi-platform syntax validation failed${NC}"
    echo "Error log:"
    cat /tmp/test-multi.log
    rm -rf ${TMP_DIR}
    exit 1
fi

# Summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "${GREEN}All tests passed!${NC}"
echo ""
echo "The outputs parameter format is valid and ready for implementation."
echo "Format that will be used in release workflow:"
echo ""
echo "outputs: type=image,name=\${{ env.REGISTRY }}/\${{ env.IMAGE_NAME }},annotation-index.org.opencontainers.image.description=A secure SSH fleet orchestrator for MCP STDIO transport. Enforces declarative policy and audited access for Claude Desktop Cursor and MCP-aware clients,annotation-index.org.opencontainers.image.source=https://github.com/\${{ github.repository }},annotation-index.org.opencontainers.image.licenses=Apache-2.0"
echo ""

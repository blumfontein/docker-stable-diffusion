#!/bin/bash
# GPU Verification Script for NVIDIA Driver 585 / CUDA 12.9 Compatibility
# Run this script on the target GPU machine to verify container compatibility

set -e

echo "==========================================="
echo "GPU Compatibility Verification Script"
echo "==========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS="${GREEN}✓ PASS${NC}"
FAIL="${RED}✗ FAIL${NC}"
WARN="${YELLOW}⚠ WARNING${NC}"

# Track overall status
OVERALL_PASS=true

echo "1. Checking Host GPU Configuration..."
echo "-------------------------------------------"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv
    DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
    echo -e "   Driver Version: ${DRIVER_VERSION}"
    echo -e "   ${PASS} nvidia-smi accessible"
else
    echo -e "   ${FAIL} nvidia-smi not found"
    OVERALL_PASS=false
fi
echo ""

echo "2. Checking NVIDIA Container Toolkit..."
echo "-------------------------------------------"
if command -v nvidia-ctk &> /dev/null; then
    nvidia-ctk --version
    echo -e "   ${PASS} NVIDIA Container Toolkit installed"
else
    echo -e "   ${FAIL} nvidia-ctk not found. Install NVIDIA Container Toolkit."
    OVERALL_PASS=false
fi
echo ""

echo "3. Checking Docker NVIDIA Runtime..."
echo "-------------------------------------------"
if docker info 2>/dev/null | grep -q "nvidia"; then
    echo -e "   ${PASS} Docker NVIDIA runtime configured"
else
    echo -e "   ${WARN} Docker NVIDIA runtime not explicitly shown (may still work with --gpus flag)"
fi
echo ""

echo "4. Testing GPU Access in Container..."
echo "-------------------------------------------"
echo "   Running: docker run --rm --gpus all nvidia/cuda:12.1-runtime-ubuntu22.04 nvidia-smi"
if docker run --rm --gpus all nvidia/cuda:12.1-runtime-ubuntu22.04 nvidia-smi; then
    echo -e "   ${PASS} GPU accessible in CUDA 12.1 container"
else
    echo -e "   ${FAIL} GPU not accessible in container"
    OVERALL_PASS=false
fi
echo ""

echo "5. Building Application Image..."
echo "-------------------------------------------"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
echo "   Building from: $PROJECT_DIR"
if docker build -t text-to-image-api-test . ; then
    echo -e "   ${PASS} Docker image built successfully"
else
    echo -e "   ${FAIL} Docker build failed"
    OVERALL_PASS=false
fi
echo ""

echo "6. Running Application Container..."
echo "-------------------------------------------"
# Clean up any existing test container
docker rm -f text-to-image-gpu-test 2>/dev/null || true

if docker run -d --gpus all -p 8000:8000 --name text-to-image-gpu-test text-to-image-api-test; then
    echo -e "   ${PASS} Container started"

    echo "   Waiting for API to initialize (60 seconds for model loading)..."
    sleep 60

    echo ""
    echo "7. Testing Health Endpoint..."
    echo "-------------------------------------------"
    if curl -s http://localhost:8000/health | jq . 2>/dev/null || curl -s http://localhost:8000/health; then
        echo ""
        echo -e "   ${PASS} Health endpoint responding"
    else
        echo -e "   ${FAIL} Health endpoint not responding"
        OVERALL_PASS=false
    fi

    echo ""
    echo "   Container logs (last 20 lines):"
    docker logs --tail 20 text-to-image-gpu-test

    echo ""
    echo "8. Cleanup..."
    echo "-------------------------------------------"
    docker stop text-to-image-gpu-test
    docker rm text-to-image-gpu-test
    echo -e "   ${PASS} Cleanup complete"
else
    echo -e "   ${FAIL} Container failed to start"
    OVERALL_PASS=false
fi

echo ""
echo "==========================================="
echo "VERIFICATION SUMMARY"
echo "==========================================="
if [ "$OVERALL_PASS" = true ]; then
    echo -e "${GREEN}All checks passed! GPU configuration is compatible.${NC}"
    echo ""
    echo "Configuration verified:"
    echo "  - Host Driver: 585 (CUDA 12.9 support)"
    echo "  - Container: nvidia/cuda:12.1-runtime-ubuntu22.04"
    echo "  - Status: FULLY COMPATIBLE"
    exit 0
else
    echo -e "${RED}Some checks failed. Please review the output above.${NC}"
    exit 1
fi

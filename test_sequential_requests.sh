#!/bin/bash
# Test script for sequential request processing
# This verifies that the queue system correctly handles sequential image generation requests

set -e

API_BASE_URL="http://localhost:8000"
HEALTH_ENDPOINT="${API_BASE_URL}/health"
GENERATION_ENDPOINT="${API_BASE_URL}/v1/images/generations"
TEST_PROMPT="a simple red cube on white background"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================================================"
echo "Sequential Request Processing Test"
echo "======================================================================"

# Step 1: Check server health
echo ""
echo "1. Checking server health..."

if ! curl -f -s "${HEALTH_ENDPOINT}" > /dev/null; then
    echo -e "${RED}✗ Server is not running${NC}"
    echo "  Start server with: uvicorn app.main:app --host 0.0.0.0 --port 8000"
    exit 1
fi

HEALTH_RESPONSE=$(curl -s "${HEALTH_ENDPOINT}")
READY=$(echo "${HEALTH_RESPONSE}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('ready', False))" 2>/dev/null || echo "false")

if [ "${READY}" != "True" ]; then
    echo -e "${RED}✗ Server is not ready yet${NC}"
    echo "  Health response: ${HEALTH_RESPONSE}"
    exit 1
fi

echo -e "${GREEN}✓ Server is ready${NC}"
echo "  Health response: ${HEALTH_RESPONSE}"

# Step 2: Send 3 sequential requests
echo ""
echo "2. Sending 3 sequential requests..."
echo ""

SUCCESS_COUNT=0
FAIL_COUNT=0

for i in {1..3}; do
    echo "--- Request ${i} ---"
    START_TIME=$(date +%s)

    REQUEST_BODY="{\"prompt\":\"${TEST_PROMPT}\",\"n\":1,\"size\":\"1024x1024\"}"

    HTTP_CODE=$(curl -s -o /tmp/response_${i}.json -w "%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "${REQUEST_BODY}" \
        "${GENERATION_ENDPOINT}")

    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))

    if [ "${HTTP_CODE}" = "200" ]; then
        # Check if response contains image data
        HAS_DATA=$(python3 -c "import sys, json; data=json.load(open('/tmp/response_${i}.json')); print('true' if 'data' in data and len(data['data']) > 0 and ('b64_json' in data['data'][0] or 'url' in data['data'][0]) else 'false')" 2>/dev/null || echo "false")

        if [ "${HAS_DATA}" = "true" ]; then
            echo -e "${GREEN}✓ Request ${i} succeeded in ${ELAPSED}s${NC}"
            echo "  Status: ${HTTP_CODE}"
            echo "  Image data present: Yes"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            echo -e "${RED}✗ Request ${i} failed: Response missing image data${NC}"
            echo "  Status: ${HTTP_CODE}"
            echo "  Response: $(cat /tmp/response_${i}.json)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    else
        echo -e "${RED}✗ Request ${i} failed with status ${HTTP_CODE}${NC}"
        echo "  Response: $(cat /tmp/response_${i}.json)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    # Small delay between requests
    if [ ${i} -lt 3 ]; then
        sleep 0.5
    fi

    echo ""
done

# Step 3: Summarize results
echo "======================================================================"
echo "Test Results Summary"
echo "======================================================================"
echo ""
echo "Total requests: 3"
echo "Successful: ${SUCCESS_COUNT}"
echo "Failed: ${FAIL_COUNT}"
echo ""

# Step 4: Final verdict
echo "======================================================================"
if [ ${SUCCESS_COUNT} -eq 3 ]; then
    echo -e "${GREEN}✓ TEST PASSED: All 3 sequential requests succeeded${NC}"
    echo "======================================================================"

    # Cleanup temp files
    rm -f /tmp/response_*.json
    exit 0
else
    echo -e "${RED}✗ TEST FAILED: Not all requests succeeded${NC}"
    echo "======================================================================"

    # Keep temp files for debugging
    echo ""
    echo "Response files saved in /tmp/response_*.json for debugging"
    exit 1
fi

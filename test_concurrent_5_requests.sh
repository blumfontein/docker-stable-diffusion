#!/bin/bash

# Test 5 concurrent requests to verify queue buffering
# This test verifies that all 5 requests are queued and processed successfully (no 429 errors)

set -e

API_URL="http://localhost:8000/v1/images/generations"
RESULTS_DIR="./test_results_concurrent5"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Testing Queue Buffering (5 Concurrent Requests)"
echo "=========================================="
echo ""

# Create results directory
mkdir -p "$RESULTS_DIR"
rm -f "$RESULTS_DIR"/*.json "$RESULTS_DIR"/*.log

# Check if server is running
echo "Checking server health..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Server is not running at http://localhost:8000${NC}"
    echo "Please start the server first:"
    echo "  export GENERATION_TIMEOUT=300"
    echo "  uvicorn app.main:app --host 0.0.0.0 --port 8000"
    exit 1
fi

HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
echo "Health check: $HEALTH_RESPONSE"

if echo "$HEALTH_RESPONSE" | grep -q '"ready":true'; then
    echo -e "${GREEN}✓ Server is ready${NC}"
else
    echo -e "${RED}ERROR: Server is not ready${NC}"
    echo "Please wait for model to load"
    exit 1
fi
echo ""

# Function to send a request
send_request() {
    local request_num=$1
    local output_file="$RESULTS_DIR/request_${request_num}.json"
    local log_file="$RESULTS_DIR/request_${request_num}.log"

    echo "[Request $request_num] Starting at $(date +%H:%M:%S)" >> "$log_file"

    HTTP_CODE=$(curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -d "{\"prompt\":\"test concurrent request $request_num - simple red cube\",\"n\":1,\"size\":\"1024x1024\"}" \
        -o "$output_file" \
        -w "%{http_code}" 2>> "$log_file")

    echo "[Request $request_num] Completed with status $HTTP_CODE at $(date +%H:%M:%S)" >> "$log_file"
    echo "$HTTP_CODE" > "$RESULTS_DIR/status_${request_num}.txt"
}

echo "Sending 5 concurrent requests..."
echo "Start time: $(date +%H:%M:%S)"
echo ""

# Launch all 5 requests in parallel
for i in {1..5}; do
    send_request $i &
done

# Wait for all background jobs to complete
echo "Waiting for all requests to complete..."
wait

echo ""
echo "End time: $(date +%H:%M:%S)"
echo ""

# Analyze results
echo "=========================================="
echo "Results Analysis"
echo "=========================================="
echo ""

success_count=0
error_429_count=0
other_error_count=0

for i in {1..5}; do
    status_file="$RESULTS_DIR/status_${i}.txt"
    if [ -f "$status_file" ]; then
        status=$(cat "$status_file")

        if [ "$status" = "200" ]; then
            echo -e "Request $i: ${GREEN}✓ SUCCESS (200)${NC}"
            success_count=$((success_count + 1))
        elif [ "$status" = "429" ]; then
            echo -e "Request $i: ${RED}✗ REJECTED (429 - Too Many Requests)${NC}"
            error_429_count=$((error_429_count + 1))
        else
            echo -e "Request $i: ${YELLOW}⚠ ERROR ($status)${NC}"
            other_error_count=$((other_error_count + 1))
        fi
    else
        echo -e "Request $i: ${RED}✗ NO RESPONSE${NC}"
        other_error_count=$((other_error_count + 1))
    fi
done

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo "Total requests: 5"
echo -e "Successful (200): ${GREEN}$success_count${NC}"
echo -e "Rejected (429): ${RED}$error_429_count${NC}"
echo -e "Other errors: ${YELLOW}$other_error_count${NC}"
echo ""

# Verification
echo "=========================================="
echo "Verification"
echo "=========================================="

if [ $success_count -eq 5 ]; then
    echo -e "${GREEN}✓ PASS: All 5 concurrent requests succeeded${NC}"
    echo "✓ Queue successfully buffered all requests"
    echo "✓ No requests were rejected with 429 errors"
    EXIT_CODE=0
else
    echo -e "${RED}✗ FAIL: Not all requests succeeded${NC}"
    echo "Expected: All 5 requests return 200 status"
    echo "Actual: $success_count succeeded, $error_429_count rejected (429), $other_error_count other errors"

    if [ $error_429_count -gt 0 ]; then
        echo ""
        echo "NOTE: 429 errors indicate queue is full or system is overloaded"
        echo "This test expects all 5 requests to be buffered in the queue (maxsize=10)"
    fi
    EXIT_CODE=1
fi

echo ""
echo "Results saved in: $RESULTS_DIR/"
echo ""

# Clean up old results after displaying summary
# (Keep for inspection if needed)

exit $EXIT_CODE

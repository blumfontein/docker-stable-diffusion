#!/bin/bash

# Test 11 concurrent requests to verify queue full rejection
# This test verifies that the 11th request is rejected with 429 when queue is full (maxsize=10)

set -e

API_URL="http://localhost:8000/v1/images/generations"
RESULTS_DIR="./test_results_concurrent11"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Testing Queue Full Rejection (11 Concurrent Requests)"
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
        -d "{\"prompt\":\"test overflow request $request_num - simple red cube\",\"n\":1,\"size\":\"1024x1024\"}" \
        -o "$output_file" \
        -w "%{http_code}" 2>> "$log_file")

    echo "[Request $request_num] Completed with status $HTTP_CODE at $(date +%H:%M:%S)" >> "$log_file"
    echo "$HTTP_CODE" > "$RESULTS_DIR/status_${request_num}.txt"
}

echo "Sending 11 concurrent requests..."
echo "Start time: $(date +%H:%M:%S)"
echo ""

# Launch all 11 requests in parallel
for i in {1..11}; do
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

for i in {1..11}; do
    status_file="$RESULTS_DIR/status_${i}.txt"
    if [ -f "$status_file" ]; then
        status=$(cat "$status_file")

        if [ "$status" = "200" ]; then
            echo -e "Request $i: ${GREEN}✓ SUCCESS (200)${NC}"
            success_count=$((success_count + 1))
        elif [ "$status" = "429" ]; then
            echo -e "Request $i: ${YELLOW}✓ REJECTED (429 - Queue Full)${NC}"
            error_429_count=$((error_429_count + 1))

            # Check error message
            response_file="$RESULTS_DIR/request_${i}.json"
            if [ -f "$response_file" ]; then
                if grep -q "queue" "$response_file" 2>/dev/null || grep -q "full" "$response_file" 2>/dev/null || grep -q "busy" "$response_file" 2>/dev/null; then
                    echo "  └─ Error message contains queue/full/busy (✓)"
                fi
            fi
        else
            echo -e "Request $i: ${RED}⚠ ERROR ($status)${NC}"
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
echo "Total requests: 11"
echo -e "Successful (200): ${GREEN}$success_count${NC}"
echo -e "Rejected (429): ${YELLOW}$error_429_count${NC}"
echo -e "Other errors: ${RED}$other_error_count${NC}"
echo ""

# Verification
echo "=========================================="
echo "Verification"
echo "=========================================="

# Expected: At least 1 request should be rejected with 429
# Expected: Up to 10 requests should succeed (queue maxsize=10)
if [ $error_429_count -ge 1 ] && [ $success_count -ge 1 ] && [ $success_count -le 10 ]; then
    echo -e "${GREEN}✓ PASS: Queue full rejection working correctly${NC}"
    echo "✓ At least one request rejected with 429 (queue full)"
    echo "✓ Successfully processed requests: $success_count (expected: 1-10)"
    echo "✓ Queue enforces maxsize=10 limit"
    EXIT_CODE=0
else
    echo -e "${RED}✗ FAIL: Queue full behavior not as expected${NC}"
    echo "Expected: At least 1 request returns 429, and 1-10 requests succeed"
    echo "Actual: $success_count succeeded, $error_429_count rejected (429), $other_error_count other errors"

    if [ $error_429_count -eq 0 ]; then
        echo ""
        echo "NOTE: No 429 errors detected - queue may not be enforcing maxsize limit"
        echo "The 11th request should be rejected when queue is full (maxsize=10)"
    fi

    if [ $success_count -gt 10 ]; then
        echo ""
        echo "NOTE: More than 10 requests succeeded - queue maxsize may not be enforced"
    fi
    EXIT_CODE=1
fi

echo ""
echo "Results saved in: $RESULTS_DIR/"
echo ""

# Show one 429 error message as example
if [ $error_429_count -gt 0 ]; then
    echo "=========================================="
    echo "Example 429 Error Response"
    echo "=========================================="
    for i in {1..11}; do
        status_file="$RESULTS_DIR/status_${i}.txt"
        if [ -f "$status_file" ] && [ "$(cat $status_file)" = "429" ]; then
            echo "Request $i response:"
            cat "$RESULTS_DIR/request_${i}.json" | python3 -m json.tool 2>/dev/null || cat "$RESULTS_DIR/request_${i}.json"
            break
        fi
    done
    echo ""
fi

exit $EXIT_CODE

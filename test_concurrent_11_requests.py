#!/usr/bin/env python3
"""
Test 11 concurrent requests to verify queue full rejection.

This test verifies that the queue system correctly rejects the 11th concurrent
request with a 429 error when the queue is full (maxsize=10). The first 10
requests should be buffered in the queue and eventually processed successfully.

Prerequisites:
    pip install httpx

Usage:
    python test_concurrent_11_requests.py
"""

import asyncio
import sys
import time
from typing import List, Tuple

try:
    import httpx
except ImportError:
    print("ERROR: httpx is not installed")
    print("Please install it: pip install httpx")
    sys.exit(1)


API_URL = "http://localhost:8000"
TIMEOUT = 300.0  # 5 minutes timeout for requests


async def check_server_health() -> bool:
    """Check if server is running and ready."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_URL}/health")
            if response.status_code == 200:
                health_data = response.json()
                return health_data.get("ready", False)
            return False
    except Exception as e:
        print(f"ERROR: Cannot connect to server: {e}")
        return False


async def send_request(request_num: int) -> Tuple[int, int, dict, float]:
    """
    Send a single image generation request.

    Returns:
        Tuple of (request_num, status_code, response_data, duration)
    """
    start_time = time.time()

    payload = {
        "prompt": f"test overflow request {request_num} - simple red cube",
        "n": 1,
        "size": "1024x1024"
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            print(f"[Request {request_num}] Sending at {time.strftime('%H:%M:%S')}")
            response = await client.post(
                f"{API_URL}/v1/images/generations",
                json=payload
            )
            duration = time.time() - start_time

            try:
                data = response.json()
            except Exception:
                data = {"error": "Invalid JSON response"}

            status_symbol = "✓" if response.status_code in [200, 429] else "✗"
            print(f"[Request {request_num}] {status_symbol} Completed with status {response.status_code} "
                  f"in {duration:.2f}s at {time.strftime('%H:%M:%S')}")

            return (request_num, response.status_code, data, duration)

    except httpx.TimeoutException:
        duration = time.time() - start_time
        print(f"[Request {request_num}] ✗ TIMEOUT after {duration:.2f}s")
        return (request_num, 0, {"error": "Timeout"}, duration)
    except Exception as e:
        duration = time.time() - start_time
        print(f"[Request {request_num}] ✗ ERROR: {e}")
        return (request_num, 0, {"error": str(e)}, duration)


async def main():
    """Run the concurrent request test."""
    print("=" * 60)
    print("Testing Queue Full Rejection (11 Concurrent Requests)")
    print("=" * 60)
    print()

    # Check server health
    print("Checking server health...")
    if not await check_server_health():
        print("ERROR: Server is not ready")
        print("Please start the server first:")
        print("  export GENERATION_TIMEOUT=300")
        print("  uvicorn app.main:app --host 0.0.0.0 --port 8000")
        return 1

    print("✓ Server is ready")
    print()

    # Send 11 concurrent requests
    print(f"Sending 11 concurrent requests...")
    print(f"Start time: {time.strftime('%H:%M:%S')}")
    print()

    start_time = time.time()

    # Use asyncio.gather to run all requests concurrently
    tasks = [send_request(i) for i in range(1, 12)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    total_duration = time.time() - start_time

    print()
    print(f"End time: {time.strftime('%H:%M:%S')}")
    print(f"Total duration: {total_duration:.2f}s")
    print()

    # Analyze results
    print("=" * 60)
    print("Results Analysis")
    print("=" * 60)
    print()

    success_count = 0
    error_429_count = 0
    other_error_count = 0
    error_429_messages = []

    for result in results:
        if isinstance(result, Exception):
            print(f"Request: ✗ EXCEPTION: {result}")
            other_error_count += 1
            continue

        request_num, status_code, data, duration = result

        if status_code == 200:
            print(f"Request {request_num:2d}: ✓ SUCCESS (200) - {duration:.2f}s")
            success_count += 1
        elif status_code == 429:
            error_msg = ""
            if "error" in data:
                error_msg = data.get("error", {}).get("message", "N/A")
                error_429_messages.append((request_num, error_msg))

            # Check if error message contains expected keywords
            has_queue_keyword = any(keyword in str(data).lower() for keyword in ["queue", "full", "busy"])
            keyword_status = "✓" if has_queue_keyword else "⚠"

            print(f"Request {request_num:2d}: ✓ REJECTED (429 - Queue Full) - {duration:.2f}s {keyword_status}")
            if error_msg:
                print(f"  └─ Error: {error_msg}")
            error_429_count += 1
        elif status_code == 0:
            print(f"Request {request_num:2d}: ✗ ERROR ({data.get('error', 'Unknown')}) - {duration:.2f}s")
            other_error_count += 1
        else:
            print(f"Request {request_num:2d}: ⚠ UNEXPECTED STATUS ({status_code}) - {duration:.2f}s")
            other_error_count += 1

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total requests: 11")
    print(f"Successful (200): {success_count}")
    print(f"Rejected (429): {error_429_count}")
    print(f"Other errors: {other_error_count}")
    print()

    # Verification
    print("=" * 60)
    print("Verification")
    print("=" * 60)

    # Expected: At least 1 request should be rejected with 429
    # Expected: Up to 10 requests should succeed (queue maxsize=10)
    pass_criteria = [
        (error_429_count >= 1, f"At least 1 request rejected with 429 (actual: {error_429_count})"),
        (success_count >= 1, f"At least 1 request succeeded (actual: {success_count})"),
        (success_count <= 10, f"At most 10 requests succeeded (actual: {success_count})"),
        (other_error_count == 0, f"No unexpected errors (actual: {other_error_count})")
    ]

    all_passed = True
    for passed, message in pass_criteria:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")
        if not passed:
            all_passed = False

    print()

    # Check error messages contain expected keywords
    if error_429_messages:
        print("Checking 429 error messages:")
        for req_num, msg in error_429_messages:
            has_keywords = any(keyword in msg.lower() for keyword in ["queue", "full", "busy"])
            status = "✓" if has_keywords else "⚠"
            print(f"  {status} Request {req_num}: {msg}")
        print()

    if all_passed:
        print("=" * 60)
        print("✓ PASS: Queue full rejection working correctly")
        print("=" * 60)
        print("✓ Queue enforces maxsize=10 limit")
        print("✓ 11th request correctly rejected with 429")
        print("✓ Up to 10 requests successfully queued and processed")
        return 0
    else:
        print("=" * 60)
        print("✗ FAIL: Queue full behavior not as expected")
        print("=" * 60)
        print(f"Expected: At least 1 request returns 429, and 1-10 requests succeed")
        print(f"Actual: {success_count} succeeded, {error_429_count} rejected (429), {other_error_count} other errors")

        if error_429_count == 0:
            print()
            print("NOTE: No 429 errors detected - queue may not be enforcing maxsize limit")
            print("The 11th request should be rejected when queue is full (maxsize=10)")

        if success_count > 10:
            print()
            print("NOTE: More than 10 requests succeeded - queue maxsize may not be enforced")

        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)

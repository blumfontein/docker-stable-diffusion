#!/usr/bin/env python3
"""
Test 5 concurrent requests to verify queue buffering.

This test verifies that the queue system can handle 5 concurrent requests
without rejecting any with 429 errors. All requests should be buffered in
the queue and processed sequentially.

Prerequisites:
    pip install httpx

Usage:
    python test_concurrent_5_requests.py
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
        "prompt": f"test concurrent request {request_num} - simple red cube",
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

            print(f"[Request {request_num}] Completed with status {response.status_code} "
                  f"in {duration:.2f}s at {time.strftime('%H:%M:%S')}")

            return (request_num, response.status_code, data, duration)

    except httpx.TimeoutException:
        duration = time.time() - start_time
        print(f"[Request {request_num}] TIMEOUT after {duration:.2f}s")
        return (request_num, 0, {"error": "Timeout"}, duration)
    except Exception as e:
        duration = time.time() - start_time
        print(f"[Request {request_num}] ERROR: {e}")
        return (request_num, 0, {"error": str(e)}, duration)


async def main():
    """Run the concurrent request test."""
    print("=" * 50)
    print("Testing Queue Buffering (5 Concurrent Requests)")
    print("=" * 50)
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

    # Send 5 concurrent requests
    print(f"Sending 5 concurrent requests...")
    print(f"Start time: {time.strftime('%H:%M:%S')}")
    print()

    start_time = time.time()

    # Use asyncio.gather to run all requests concurrently
    results = await asyncio.gather(
        send_request(1),
        send_request(2),
        send_request(3),
        send_request(4),
        send_request(5),
        return_exceptions=True
    )

    total_duration = time.time() - start_time

    print()
    print(f"End time: {time.strftime('%H:%M:%S')}")
    print(f"Total duration: {total_duration:.2f}s")
    print()

    # Analyze results
    print("=" * 50)
    print("Results Analysis")
    print("=" * 50)
    print()

    success_count = 0
    error_429_count = 0
    other_error_count = 0

    for result in results:
        if isinstance(result, Exception):
            print(f"Request: ✗ EXCEPTION: {result}")
            other_error_count += 1
            continue

        request_num, status_code, data, duration = result

        if status_code == 200:
            print(f"Request {request_num}: ✓ SUCCESS (200) - {duration:.2f}s")
            success_count += 1
        elif status_code == 429:
            print(f"Request {request_num}: ✗ REJECTED (429 - Too Many Requests) - {duration:.2f}s")
            error_429_count += 1
            if "error" in data:
                print(f"  Error message: {data.get('error', {}).get('message', 'N/A')}")
        elif status_code == 0:
            print(f"Request {request_num}: ✗ ERROR ({data.get('error', 'Unknown')}) - {duration:.2f}s")
            other_error_count += 1
        else:
            print(f"Request {request_num}: ⚠ UNEXPECTED STATUS ({status_code}) - {duration:.2f}s")
            other_error_count += 1

    print()
    print("=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"Total requests: 5")
    print(f"Successful (200): {success_count}")
    print(f"Rejected (429): {error_429_count}")
    print(f"Other errors: {other_error_count}")
    print()

    # Verification
    print("=" * 50)
    print("Verification")
    print("=" * 50)

    if success_count == 5:
        print("✓ PASS: All 5 concurrent requests succeeded")
        print("✓ Queue successfully buffered all requests")
        print("✓ No requests were rejected with 429 errors")
        return 0
    else:
        print("✗ FAIL: Not all requests succeeded")
        print(f"Expected: All 5 requests return 200 status")
        print(f"Actual: {success_count} succeeded, {error_429_count} rejected (429), {other_error_count} other errors")

        if error_429_count > 0:
            print()
            print("NOTE: 429 errors indicate queue is full or system is overloaded")
            print("This test expects all 5 requests to be buffered in the queue (maxsize=10)")

        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)

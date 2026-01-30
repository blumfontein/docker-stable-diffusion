#!/usr/bin/env python3
"""Test script for sequential request processing.

This script verifies that the queue system correctly handles sequential
image generation requests by sending 3 requests one after another and
verifying that all succeed with 200 status and valid image data.
"""

import asyncio
import json
import sys
import time
from typing import Dict, Any

import httpx


API_BASE_URL = "http://localhost:8000"
HEALTH_ENDPOINT = f"{API_BASE_URL}/health"
GENERATION_ENDPOINT = f"{API_BASE_URL}/v1/images/generations"

# Simple prompt for quick testing
TEST_PROMPT = "a simple red cube on white background"


async def check_server_health() -> bool:
    """Check if the server is running and ready.

    Returns:
        True if server is healthy and ready, False otherwise.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(HEALTH_ENDPOINT, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Health check: {data}")
                if data.get("ready"):
                    print("✓ Server is ready")
                    return True
                else:
                    print("✗ Server is not ready yet (model may still be loading)")
                    return False
            else:
                print(f"✗ Health check failed with status {response.status_code}")
                return False
    except httpx.ConnectError:
        print("✗ Cannot connect to server - is it running?")
        print(f"  Start server with: uvicorn app.main:app --host 0.0.0.0 --port 8000")
        return False
    except Exception as e:
        print(f"✗ Health check error: {e}")
        return False


async def send_generation_request(request_num: int) -> Dict[str, Any]:
    """Send a single image generation request.

    Args:
        request_num: The request number (for logging).

    Returns:
        Dictionary with response data and metadata.
    """
    print(f"\n--- Request {request_num} ---")
    start_time = time.time()

    request_body = {
        "prompt": TEST_PROMPT,
        "n": 1,
        "size": "1024x1024",
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                GENERATION_ENDPOINT,
                json=request_body,
            )

            elapsed = time.time() - start_time

            result = {
                "request_num": request_num,
                "status_code": response.status_code,
                "elapsed_seconds": round(elapsed, 2),
                "success": False,
                "error": None,
            }

            if response.status_code == 200:
                data = response.json()
                # Verify response structure
                if "data" in data and len(data["data"]) > 0:
                    image_data = data["data"][0]
                    has_image = "b64_json" in image_data or "url" in image_data
                    if has_image:
                        result["success"] = True
                        result["has_image_data"] = True
                        result["created"] = data.get("created")
                        print(f"✓ Request {request_num} succeeded in {elapsed:.2f}s")
                        print(f"  Status: {response.status_code}")
                        print(f"  Image data present: Yes")
                        print(f"  Created timestamp: {data.get('created')}")
                    else:
                        result["error"] = "Response missing image data (no b64_json or url)"
                        print(f"✗ Request {request_num} failed: {result['error']}")
                else:
                    result["error"] = "Response missing 'data' field or empty"
                    print(f"✗ Request {request_num} failed: {result['error']}")
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text}"
                print(f"✗ Request {request_num} failed with status {response.status_code}")
                print(f"  Error: {response.text}")

            return result

    except httpx.TimeoutException:
        elapsed = time.time() - start_time
        print(f"✗ Request {request_num} timed out after {elapsed:.2f}s")
        return {
            "request_num": request_num,
            "status_code": 0,
            "elapsed_seconds": round(elapsed, 2),
            "success": False,
            "error": "Request timed out",
        }
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"✗ Request {request_num} failed: {e}")
        return {
            "request_num": request_num,
            "status_code": 0,
            "elapsed_seconds": round(elapsed, 2),
            "success": False,
            "error": str(e),
        }


async def main():
    """Run sequential request test."""
    print("=" * 60)
    print("Sequential Request Processing Test")
    print("=" * 60)

    # Step 1: Check server health
    print("\n1. Checking server health...")
    if not await check_server_health():
        print("\n✗ Test aborted - server is not ready")
        sys.exit(1)

    # Step 2: Send 3 sequential requests
    print("\n2. Sending 3 sequential requests...")
    results = []

    for i in range(1, 4):
        result = await send_generation_request(i)
        results.append(result)

        # Small delay between requests to ensure they're truly sequential
        if i < 3:
            await asyncio.sleep(0.5)

    # Step 3: Verify results
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    all_success = all(r["success"] for r in results)
    success_count = sum(1 for r in results if r["success"])

    print(f"\nTotal requests: 3")
    print(f"Successful: {success_count}")
    print(f"Failed: {3 - success_count}")

    for result in results:
        status = "✓ PASS" if result["success"] else "✗ FAIL"
        print(f"  Request {result['request_num']}: {status} "
              f"(status={result['status_code']}, time={result['elapsed_seconds']}s)")
        if result["error"]:
            print(f"    Error: {result['error']}")

    # Final verdict
    print("\n" + "=" * 60)
    if all_success:
        print("✓ TEST PASSED: All 3 sequential requests succeeded")
        print("=" * 60)
        sys.exit(0)
    else:
        print("✗ TEST FAILED: Not all requests succeeded")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

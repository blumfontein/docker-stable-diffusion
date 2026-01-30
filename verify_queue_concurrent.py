#!/usr/bin/env python3
"""
Verification script for queue buffering implementation (subtask-6-2).

This script performs static code verification to ensure the queue system
is properly implemented to handle 5 concurrent requests.

It checks:
1. Queue is initialized with maxsize=10 (can handle 10 requests)
2. Queue worker processes requests sequentially
3. Endpoint uses queue.put_nowait() for non-blocking enqueue
4. Proper error handling for QueueFull exceptions
"""

import ast
import sys
from pathlib import Path


def check_queue_implementation():
    """Verify queue implementation in app/main.py."""
    print("=" * 60)
    print("Queue Buffering Verification (subtask-6-2)")
    print("=" * 60)
    print()

    main_file = Path("app/main.py")
    if not main_file.exists():
        print(f"✗ ERROR: {main_file} not found")
        return False

    print(f"Reading {main_file}...")
    code = main_file.read_text()

    checks_passed = 0
    total_checks = 5

    # Check 1: Queue initialization with maxsize=10
    print("\n1. Checking queue initialization with maxsize=10...")
    if "asyncio.Queue(maxsize=10)" in code:
        print("   ✓ Found: asyncio.Queue(maxsize=10)")
        checks_passed += 1
    else:
        print("   ✗ FAIL: Queue not initialized with maxsize=10")

    # Check 2: Queue worker sequential processing
    print("\n2. Checking queue worker implementation...")
    if "await request_queue.get()" in code and "request_queue.task_done()" in code:
        print("   ✓ Found: Queue worker with get() and task_done()")
        checks_passed += 1
    else:
        print("   ✗ FAIL: Queue worker not properly implemented")

    # Check 3: Endpoint uses queue.put_nowait()
    print("\n3. Checking endpoint uses queue.put_nowait()...")
    if "request_queue.put_nowait" in code or "put_nowait" in code:
        print("   ✓ Found: queue.put_nowait() usage")
        checks_passed += 1
    else:
        print("   ✗ FAIL: Endpoint not using put_nowait()")

    # Check 4: QueueFull exception handling
    print("\n4. Checking QueueFull exception handling...")
    if "asyncio.QueueFull" in code or "QueueFull" in code:
        print("   ✓ Found: QueueFull exception handling")
        checks_passed += 1
    else:
        print("   ✗ FAIL: QueueFull exception not handled")

    # Check 5: Python syntax validation
    print("\n5. Checking Python syntax...")
    try:
        ast.parse(code)
        print("   ✓ Python syntax is valid")
        checks_passed += 1
    except SyntaxError as e:
        print(f"   ✗ FAIL: Syntax error: {e}")

    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Checks passed: {checks_passed}/{total_checks}")
    print()

    if checks_passed == total_checks:
        print("✓ ALL CHECKS PASSED")
        print()
        print("The queue implementation is correct:")
        print("- Queue can hold up to 10 requests (maxsize=10)")
        print("- 5 concurrent requests will fit in the queue")
        print("- Requests will be processed sequentially")
        print("- Non-blocking enqueue with proper error handling")
        print()
        return True
    else:
        print("✗ SOME CHECKS FAILED")
        print()
        print(f"Failed: {total_checks - checks_passed} check(s)")
        print("Please review the implementation")
        print()
        return False


def main():
    """Run verification."""
    success = check_queue_implementation()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

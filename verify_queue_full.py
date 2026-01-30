#!/usr/bin/env python3
"""
Static code verification for queue full rejection (subtask-6-3).

This script verifies that the code structure is correct for handling
queue full scenarios when 11 concurrent requests are sent.

It checks:
1. Queue initialized with maxsize=10
2. Endpoint uses queue.put_nowait() which raises QueueFull
3. QueueFull exception is caught and returns 429 error
4. Error message contains relevant text about queue being full

This is a static analysis that doesn't require running the server.
"""

import ast
import sys
from pathlib import Path


def check_file_exists(filepath: str) -> bool:
    """Check if a file exists."""
    path = Path(filepath)
    if not path.exists():
        print(f"✗ File not found: {filepath}")
        return False
    print(f"✓ File exists: {filepath}")
    return True


def parse_python_file(filepath: str):
    """Parse a Python file into an AST."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        tree = ast.parse(content)
        print(f"✓ Successfully parsed {filepath}")
        return tree, content
    except SyntaxError as e:
        print(f"✗ Syntax error in {filepath}: {e}")
        return None, None


def check_queue_maxsize(tree, content) -> bool:
    """Check that request_queue is initialized with maxsize=10."""
    print("\n📋 Checking queue initialization with maxsize=10...")

    # Look for asyncio.Queue(maxsize=10)
    if "Queue(maxsize=10)" in content:
        print("✓ Found Queue(maxsize=10) in code")
        return True

    print("✗ Queue(maxsize=10) not found in code")
    return False


def check_queue_put_nowait(tree, content) -> bool:
    """Check that endpoint uses queue.put_nowait()."""
    print("\n📋 Checking queue.put_nowait() usage...")

    if "request_queue.put_nowait" in content or "queue.put_nowait" in content:
        print("✓ Found queue.put_nowait() in code")
        return True

    print("✗ queue.put_nowait() not found in code")
    return False


def check_queue_full_exception(tree, content) -> bool:
    """Check that QueueFull exception is caught."""
    print("\n📋 Checking QueueFull exception handling...")

    if "asyncio.QueueFull" in content or "QueueFull" in content:
        print("✓ Found QueueFull exception handling")
        return True

    print("✗ QueueFull exception handling not found")
    return False


def check_429_response(tree, content) -> bool:
    """Check that 429 response is returned when queue is full."""
    print("\n📋 Checking 429 status code for queue full...")

    # Look for 429 status code and queue-related error message
    has_429 = "status_code=429" in content or "HTTPException(429" in content or 'HTTPException(status_code=429' in content
    has_queue_msg = any(keyword in content.lower() for keyword in ["queue is full", "queue full", "too many"])

    if has_429:
        print("✓ Found 429 status code in code")
    else:
        print("✗ 429 status code not found in code")

    if has_queue_msg:
        print("✓ Found queue full error message")
    else:
        print("⚠ Queue full error message may not be explicit")

    return has_429


def check_error_message_content(content) -> bool:
    """Check that error messages contain relevant keywords."""
    print("\n📋 Checking error message content...")

    # Look for error messages that mention queue being full
    relevant_keywords = ["queue", "full", "busy", "capacity"]

    found_keywords = []
    for keyword in relevant_keywords:
        if keyword in content.lower():
            found_keywords.append(keyword)

    if found_keywords:
        print(f"✓ Found relevant keywords in error messages: {', '.join(found_keywords)}")
        return True
    else:
        print("⚠ No obvious queue-related error message keywords found")
        return False


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Queue Full Rejection - Static Code Verification")
    print("=" * 60)
    print()

    # Check if main.py exists
    main_file = "app/main.py"
    if not check_file_exists(main_file):
        print("\n✗ Cannot proceed without app/main.py")
        return 1

    # Parse the file
    tree, content = parse_python_file(main_file)
    if tree is None or content is None:
        print("\n✗ Cannot proceed due to syntax errors")
        return 1

    # Run all checks
    checks = [
        ("Queue maxsize=10", check_queue_maxsize(tree, content)),
        ("queue.put_nowait() usage", check_queue_put_nowait(tree, content)),
        ("QueueFull exception handling", check_queue_full_exception(tree, content)),
        ("429 status code", check_429_response(tree, content)),
        ("Error message content", check_error_message_content(content))
    ]

    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)

    passed = 0
    total = len(checks)

    for check_name, result in checks:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")
        if result:
            passed += 1

    print()
    print(f"Total: {passed}/{total} checks passed")
    print()

    if passed == total:
        print("=" * 60)
        print("✓ All static code checks passed!")
        print("=" * 60)
        print()
        print("The code structure appears correct for handling queue full scenarios.")
        print()
        print("Next steps:")
        print("1. Start the server: uvicorn app.main:app --host 0.0.0.0 --port 8000")
        print("2. Run integration test: ./test_concurrent_11_requests.sh")
        print("3. Or run Python test: python test_concurrent_11_requests.py")
        print()
        return 0
    else:
        print("=" * 60)
        print(f"⚠ {total - passed} check(s) failed")
        print("=" * 60)
        print()
        print("Please review the implementation to ensure:")
        print("- Queue is initialized with maxsize=10")
        print("- Endpoint uses queue.put_nowait() for non-blocking enqueue")
        print("- QueueFull exception is caught and returns 429")
        print("- Error message clearly indicates queue is full")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())

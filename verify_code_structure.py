#!/usr/bin/env python3
"""Verify code structure for queue implementation.

This script performs static verification of the queue system implementation
without requiring a running server or GPU access.
"""

import ast
import sys
from pathlib import Path


def verify_imports():
    """Verify required imports are present in main.py."""
    print("1. Checking imports...")
    main_py = Path("app/main.py").read_text()

    required_imports = [
        "asyncio",
        "dataclass",
        "FastAPI",
        "QueuedRequest",  # Should be defined
    ]

    missing = []
    for imp in required_imports:
        if imp not in main_py:
            missing.append(imp)

    if missing:
        print(f"  ✗ Missing imports/definitions: {', '.join(missing)}")
        return False
    else:
        print("  ✓ All required imports present")
        return True


def verify_dataclass():
    """Verify QueuedRequest dataclass exists."""
    print("\n2. Checking QueuedRequest dataclass...")
    main_py = Path("app/main.py").read_text()

    if "@dataclass" not in main_py:
        print("  ✗ @dataclass decorator not found")
        return False

    if "class QueuedRequest" not in main_py:
        print("  ✗ QueuedRequest class not found")
        return False

    # Check for required fields
    if "request:" not in main_py or "future:" not in main_py:
        print("  ✗ QueuedRequest missing required fields (request, future)")
        return False

    print("  ✓ QueuedRequest dataclass properly defined")
    return True


def verify_globals():
    """Verify global variables are defined."""
    print("\n3. Checking global variables...")
    main_py = Path("app/main.py").read_text()

    required_globals = {
        "request_queue": "asyncio.Queue",
        "queue_worker_task": "asyncio.Task",
    }

    missing = []
    for var, type_hint in required_globals.items():
        if f"{var}:" not in main_py and f"{var} =" not in main_py:
            missing.append(var)

    if missing:
        print(f"  ✗ Missing global variables: {', '.join(missing)}")
        return False

    # Verify generation_lock is NOT present
    if "generation_lock" in main_py:
        print("  ⚠ Warning: generation_lock still present (should be removed)")
        return False

    print("  ✓ Global variables properly defined")
    print("  ✓ Old generation_lock removed")
    return True


def verify_queue_worker():
    """Verify queue_worker function exists and is async."""
    print("\n4. Checking queue_worker function...")
    main_py = Path("app/main.py").read_text()

    if "async def queue_worker" not in main_py:
        print("  ✗ queue_worker function not found or not async")
        return False

    # Check for key components
    required_components = [
        "while True:",
        "await request_queue.get()",
        "request_queue.task_done()",
    ]

    missing = []
    for component in required_components:
        if component not in main_py:
            missing.append(component)

    if missing:
        print(f"  ✗ Missing queue_worker components: {', '.join(missing)}")
        return False

    print("  ✓ queue_worker function properly implemented")
    return True


def verify_lifespan():
    """Verify lifespan function initializes queue and worker."""
    print("\n5. Checking lifespan initialization...")
    main_py = Path("app/main.py").read_text()

    required_init = [
        "asyncio.Queue(maxsize=10)",
        "asyncio.create_task(queue_worker())",
    ]

    missing = []
    for init in required_init:
        if init not in main_py:
            missing.append(init)

    if missing:
        print(f"  ✗ Missing lifespan initialization: {', '.join(missing)}")
        return False

    print("  ✓ Lifespan properly initializes queue and worker")
    return True


def verify_endpoint():
    """Verify endpoint uses queue instead of lock."""
    print("\n6. Checking endpoint implementation...")
    main_py = Path("app/main.py").read_text()

    # Should have queue logic
    required_queue_logic = [
        "QueuedRequest(",
        "request_queue.put_nowait",
        "asyncio.QueueFull",
    ]

    missing = []
    for logic in required_queue_logic:
        if logic not in main_py:
            missing.append(logic)

    if missing:
        print(f"  ✗ Missing endpoint queue logic: {', '.join(missing)}")
        return False

    # Should NOT have lock logic
    if "generation_lock.locked()" in main_py or "async with generation_lock" in main_py:
        print("  ✗ Endpoint still uses generation_lock (should use queue)")
        return False

    print("  ✓ Endpoint properly uses queue system")
    return True


def verify_syntax():
    """Verify Python syntax is valid."""
    print("\n7. Checking Python syntax...")
    try:
        main_py = Path("app/main.py").read_text()
        ast.parse(main_py)
        print("  ✓ Python syntax is valid")
        return True
    except SyntaxError as e:
        print(f"  ✗ Syntax error: {e}")
        return False


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("Code Structure Verification for Request Queue System")
    print("=" * 70)
    print()

    checks = [
        verify_imports,
        verify_dataclass,
        verify_globals,
        verify_queue_worker,
        verify_lifespan,
        verify_endpoint,
        verify_syntax,
    ]

    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Error during check: {e}")
            results.append(False)

    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total checks: {len(results)}")
    print(f"Passed: {sum(results)}")
    print(f"Failed: {len(results) - sum(results)}")
    print()

    if all(results):
        print("✓ ALL CHECKS PASSED - Code structure is correct")
        print()
        print("Next steps:")
        print("  1. Start the server: uvicorn app.main:app --host 0.0.0.0 --port 8000")
        print("  2. Run integration tests: ./test_sequential_requests.sh")
        print("  3. See TESTING_INTEGRATION.md for detailed test instructions")
        sys.exit(0)
    else:
        print("✗ SOME CHECKS FAILED - Review errors above")
        sys.exit(1)


if __name__ == "__main__":
    main()

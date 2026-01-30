#!/usr/bin/env python3
"""Simple test runner script."""
import sys
sys.path.insert(0, '/Users/ilyasmak/Library/Python/3.9/lib/python/site-packages')
import pytest

if __name__ == "__main__":
    sys.exit(pytest.main(['tests/', '-v']))

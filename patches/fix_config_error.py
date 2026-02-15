#!/usr/bin/env python3
"""
Patch script to fix vLLM-Omni config() decorator error with vLLM v0.14.0.

This patch modifies the installed vllm-omni library to fix the incompatibility
between vLLM-Omni's @config decorator usage and vLLM v0.14.0's API.

The issue: vllm_omni/config/model.py uses @config(config=ConfigDict(...))
but vLLM v0.14.0's config() decorator only accepts a positional cls argument,
not keyword arguments.

The fix: Replace @config(config=ConfigDict(...)) with @config

Usage:
    python3 patches/fix_config_error.py

Exit codes:
    0 - Patch applied successfully (or already applied)
    1 - Error: file not found or patch failed
"""

import importlib.util
import os
import re
import sys


def find_vllm_omni_path():
    """Locate the vllm-omni installation directory."""
    try:
        spec = importlib.util.find_spec("vllm_omni")
        if spec and spec.origin:
            return os.path.dirname(os.path.dirname(spec.origin))
    except ImportError:
        pass

    # Fallback: check common installation paths
    common_paths = [
        "/usr/local/lib/python3.10/dist-packages/vllm_omni",
        "/usr/lib/python3.10/dist-packages/vllm_omni",
        "/usr/local/lib/python3/dist-packages/vllm_omni",
    ]

    for path in common_paths:
        if os.path.isdir(path):
            return path

    return None


def find_config_model_file(vllm_omni_path):
    """Find the config/model.py file within vllm-omni installation."""
    target_file = os.path.join(vllm_omni_path, "config", "model.py")

    if os.path.isfile(target_file):
        return target_file

    # Fallback: search for model.py in config directory
    for root, dirs, files in os.walk(vllm_omni_path):
        if "config" in root and "model.py" in files:
            return os.path.join(root, "model.py")

    return None


def apply_patch(file_path):
    """
    Apply the config decorator patch to model.py.

    Returns:
        tuple: (success: bool, message: str)
    """
    # Pattern to match: @config(config=ConfigDict(...))
    # This matches the decorator line with any ConfigDict arguments
    old_pattern = r"^(\s*)@config\s*\(\s*config\s*=\s*ConfigDict\s*\([^)]*\)\s*\)\s*$"

    # Replacement: just @config (the plain decorator)
    new_pattern = r"\1@config"

    # Pattern to check if already patched (plain @config without arguments)
    # We need to be careful - we want to detect if the line is just "@config" alone
    # without any parentheses following it
    patched_pattern = r"^\s*@config\s*$"

    print(f"[PATCH] Reading file: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as e:
        return False, f"Failed to read file: {e}"

    # Check if the problematic pattern exists
    if re.search(old_pattern, content, re.MULTILINE):
        # Apply the patch
        patched_content, count = re.subn(old_pattern, new_pattern, content, flags=re.MULTILINE)

        if count == 0:
            return False, "Regex substitution failed"

        print(f"[PATCH] Replaced {count} occurrence(s)")

        # Write the patched content
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(patched_content)
        except IOError as e:
            return False, f"Failed to write file: {e}"

        # Verify the patch was applied
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                verify_content = f.read()
            # Verify the problematic pattern is gone
            if not re.search(old_pattern, verify_content, re.MULTILINE):
                print("[PATCH] Verification passed")
                return True, f"Successfully patched {count} occurrence(s)"
            else:
                return False, "Verification failed - problematic pattern still present"
        except IOError as e:
            return False, f"Failed to verify: {e}"

    # Check if already patched
    if re.search(patched_pattern, content, re.MULTILINE):
        print("[PATCH] File already patched - skipping (idempotent)")
        return True, "Already patched"

    # Pattern not found - could be a different version
    print("[PATCH] Warning: Original pattern not found in file")
    print("[PATCH] This may indicate a different vllm-omni version")
    # Not a failure - the code may have been fixed upstream
    return True, "Pattern not found (may already be fixed)"


def main():
    """Main entry point for the patch script."""
    print("=" * 60)
    print("vllm-omni Config Decorator Compatibility Patch")
    print("=" * 60)
    print()

    # Find vllm-omni installation
    print("[PATCH] Locating vllm-omni installation...")
    vllm_path = find_vllm_omni_path()

    if not vllm_path:
        print("[PATCH] ERROR: vllm-omni package not found")
        print("[PATCH] Ensure vllm-omni is installed before running this patch")
        sys.exit(1)

    print(f"[PATCH] Found vllm-omni at: {vllm_path}")

    # Find config/model.py
    print("[PATCH] Locating config/model.py...")
    model_file = find_config_model_file(vllm_path)

    if not model_file:
        print("[PATCH] ERROR: config/model.py not found")
        print("[PATCH] Expected location: config/model.py")
        sys.exit(1)

    print(f"[PATCH] Found target file: {model_file}")

    # Apply the patch
    print()
    print("[PATCH] Applying patch...")
    success, message = apply_patch(model_file)

    print()
    if success:
        print(f"[PATCH] SUCCESS: {message}")
        print("=" * 60)
        sys.exit(0)
    else:
        print(f"[PATCH] FAILED: {message}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

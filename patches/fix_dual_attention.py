#!/usr/bin/env python3
"""
Patch script to fix SD3.5 dual_attention_layers AttributeError in vllm-omni.

This patch modifies the installed vllm-omni library to handle the missing
'dual_attention_layers' attribute in SD3.5 Large Turbo model configuration.

The issue: sd3_transformer.py directly accesses model_config.dual_attention_layers
without fallback, causing AttributeError when the attribute doesn't exist.

The fix: Replace direct attribute access with getattr() fallback to empty tuple.

Usage:
    python3 patches/fix_dual_attention.py

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


def find_sd3_transformer_file(vllm_omni_path):
    """Find the sd3_transformer.py file within vllm-omni installation."""
    target_file = os.path.join(
        vllm_omni_path, "diffusion", "models", "sd3", "sd3_transformer.py"
    )

    if os.path.isfile(target_file):
        return target_file

    # Fallback: search for the file
    for root, _, files in os.walk(vllm_omni_path):
        if "sd3_transformer.py" in files:
            return os.path.join(root, "sd3_transformer.py")

    return None


def apply_patch(file_path):
    """
    Apply the dual_attention_layers patch to sd3_transformer.py.

    Returns:
        tuple: (success: bool, message: str)
    """
    # Pattern to match: self.dual_attention_layers = model_config.dual_attention_layers
    # Must preserve leading whitespace (indentation)
    old_pattern = r"^(\s*)self\.dual_attention_layers\s*=\s*model_config\.dual_attention_layers\s*$"

    # Replacement using getattr with fallback to empty tuple
    new_pattern = r"\1self.dual_attention_layers = getattr(model_config, 'dual_attention_layers', ())"

    # Pattern to check if already patched
    patched_pattern = r"getattr\(model_config,\s*['\"]dual_attention_layers['\"]"

    print(f"[PATCH] Reading file: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as e:
        return False, f"Failed to read file: {e}"

    # Check if already patched
    if re.search(patched_pattern, content):
        print("[PATCH] File already patched - skipping (idempotent)")
        return True, "Already patched"

    # Check if the problematic pattern exists
    if not re.search(old_pattern, content, re.MULTILINE):
        # Pattern not found - could be a different version
        print("[PATCH] Warning: Original pattern not found in file")
        print("[PATCH] This may indicate a different vllm-omni version")
        # Not a failure - the code may have been fixed upstream
        return True, "Pattern not found (may already be fixed)"

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
        if re.search(patched_pattern, verify_content):
            print("[PATCH] Verification passed")
            return True, f"Successfully patched {count} occurrence(s)"
        else:
            return False, "Verification failed - patch not found after writing"
    except IOError as e:
        return False, f"Failed to verify: {e}"


def main():
    """Main entry point for the patch script."""
    print("=" * 60)
    print("vllm-omni SD3 dual_attention_layers Patch")
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

    # Find sd3_transformer.py
    print("[PATCH] Locating sd3_transformer.py...")
    transformer_file = find_sd3_transformer_file(vllm_path)

    if not transformer_file:
        print("[PATCH] ERROR: sd3_transformer.py not found")
        print("[PATCH] Expected location: diffusion/models/sd3/sd3_transformer.py")
        sys.exit(1)

    print(f"[PATCH] Found target file: {transformer_file}")

    # Apply the patch
    print()
    print("[PATCH] Applying patch...")
    success, message = apply_patch(transformer_file)

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

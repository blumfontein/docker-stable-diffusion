#!/usr/bin/env python3
"""
Patch to fix vllm-omni config() decorator incompatibility with vLLM v0.14.0
"""

import sys
from pathlib import Path


def apply_patch():
    print('=' * 60)
    print('vllm-omni Config Decorator Compatibility Patch')
    print('=' * 60)
    print()

    # Find vllm_omni directly in site-packages without importing
    site_packages = Path('/usr/local/lib/python3.10/dist-packages')
    vllm_omni_path = site_packages / 'vllm_omni'
    
    if not vllm_omni_path.exists():
        print(f'[PATCH] ERROR: vllm_omni not found at {vllm_omni_path}')
        sys.exit(1)

    print(f'[PATCH] Found vllm_omni at: {vllm_omni_path}')

    target_file = vllm_omni_path / 'config' / 'model.py'
    
    if not target_file.exists():
        print(f'[PATCH] ERROR: Target file not found: {target_file}')
        sys.exit(1)

    print(f'[PATCH] Found target file: {target_file}')
    print()

    print('[PATCH] Applying patch...')
    content = target_file.read_text()

    old_pattern = '@config(config=ConfigDict(arbitrary_types_allowed=True))'
    new_pattern = '@config'

    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)
        target_file.write_text(content)
        print(f'[PATCH] Successfully patched {target_file}')
    elif '@config' in content and old_pattern not in content:
        print('[PATCH] File already patched - skipping')
    else:
        print('[PATCH] Warning: Pattern not found')

    print()
    print('[PATCH] SUCCESS')
    print('=' * 60)


if __name__ == '__main__':
    apply_patch()

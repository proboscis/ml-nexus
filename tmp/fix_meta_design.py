#!/usr/bin/env python3
"""Fix deprecated __meta_design__ in test files"""
import re
from pathlib import Path

# List of files to fix
files_to_fix = [
    "test/test_docker_build_context_verification.py",
    "test/test_docker_env_host_with_schematics.py",
    "test/test_embedded_components_verification.py",
    "test/test_embedded_docker_execution.py",
    "test/test_embedded_dockerfile_preview.py",
    "test/test_schematics_docker_run.py",
    "test/test_schematics_for_uv_with_accelerator.py",
    "test/test_schematics_pytest_compatible.py",
    "test/test_schematics_simple.py",
    "test/test_schematics_universal_kinds.py",
    "test/test_schematics_universal_kinds_runner.py",
    "test/test_schematics_uv_only.py",
    "test/test_schematics_working_kinds.py",
]

for file_path in files_to_fix:
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        continue
    
    content = path.read_text()
    
    # Replace __meta_design__ = with comment
    new_content = re.sub(
        r'^(__meta_design__\s*=.*?)$',
        r'# \1  # Removed deprecated __meta_design__',
        content,
        flags=re.MULTILINE
    )
    
    # Check if design definition needs load_env_design
    if 'load_env_design' not in new_content and 'design(' in new_content:
        # Find the line with design( and ensure it includes load_env_design
        new_content = re.sub(
            r'^(\w+_design\s*=\s*)(design\()',
            r'\1load_env_design + \2',
            new_content,
            flags=re.MULTILINE
        )
    
    if new_content != content:
        path.write_text(new_content)
        print(f"Fixed: {file_path}")
    else:
        print(f"No changes needed: {file_path}")
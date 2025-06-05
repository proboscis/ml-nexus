#!/usr/bin/env python
"""Script to convert IProxy test objects to pytest-compatible modules

Usage:
    python convert_iproxy_tests.py test_all_schematics_kinds.py -o test_all_schematics_pytest.py
    python convert_iproxy_tests.py test_schematics_working_kinds.py --list
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import the adapter
sys.path.insert(0, str(Path(__file__).parent.parent))

from test.pytest_iproxy_adapter import create_pytest_module, convert_module_iproxy_tests


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Convert IProxy test files to pytest-compatible modules"
    )
    parser.add_argument("source", help="Source test file containing IProxy objects")
    parser.add_argument("-o", "--output", help="Output pytest file (default: <source>_pytest.py)")
    parser.add_argument("--list", action="store_true", help="Just list IProxy tests found")
    parser.add_argument("--convert-all", action="store_true", 
                       help="Convert all test_*.py files with IProxy objects")
    
    args = parser.parse_args()
    
    if args.convert_all:
        # Find all test files with IProxy objects
        test_dir = Path(__file__).parent
        for test_file in test_dir.glob("test_*.py"):
            if test_file.name == Path(__file__).name:
                continue
                
            try:
                content = test_file.read_text()
                if 'IProxy' in content and 'test_' in content:
                    output_name = test_file.stem + "_pytest.py"
                    output_path = test_file.parent / output_name
                    print(f"\nConverting {test_file.name}...")
                    create_pytest_module(str(test_file), str(output_path))
            except Exception as e:
                print(f"Error processing {test_file}: {e}")
    
    elif args.list:
        tests = convert_module_iproxy_tests(args.source)
        print(f"\nFound {len(tests)} IProxy tests in {args.source}:")
        for name in sorted(tests.keys()):
            print(f"  - {name}")
    
    else:
        # Convert single file
        output = args.output
        if not output:
            source_path = Path(args.source)
            output = str(source_path.parent / (source_path.stem + "_pytest.py"))
        
        create_pytest_module(args.source, output)
        print(f"\nYou can now run: pytest {output}")


if __name__ == "__main__":
    main()
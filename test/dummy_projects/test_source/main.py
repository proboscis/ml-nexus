#!/usr/bin/env python3
"""Main module for source-only project."""

import sys
from utils import calculate_sum, format_output, process_data


def main():
    """Main entry point for the application."""
    print("Source-only project example")
    
    # Example calculations
    numbers = [1, 2, 3, 4, 5]
    result = calculate_sum(numbers)
    print(format_output("Sum", result))
    
    # Process some data
    data = {
        'name': 'test',
        'values': [10, 20, 30],
        'active': True
    }
    processed = process_data(data)
    print(format_output("Processed", processed))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
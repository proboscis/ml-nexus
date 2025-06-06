"""Utility functions for source-only project."""


def calculate_sum(numbers):
    """Calculate the sum of a list of numbers.

    Args:
        numbers: List of numeric values

    Returns:
        Sum of all numbers
    """
    return sum(numbers)


def format_output(label, value):
    """Format a label-value pair for display.

    Args:
        label: Label string
        value: Value to display

    Returns:
        Formatted string
    """
    return f"{label}: {value}"


def process_data(data_dict):
    """Process a data dictionary.

    Args:
        data_dict: Dictionary containing data to process

    Returns:
        Processed data summary
    """
    result = {
        "item_count": len(data_dict),
        "keys": list(data_dict.keys()),
        "has_values": "values" in data_dict,
    }

    if "values" in data_dict:
        result["values_sum"] = sum(data_dict["values"])

    return result

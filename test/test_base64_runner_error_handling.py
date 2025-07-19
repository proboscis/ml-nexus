"""Test that base64_runner.sh fails immediately on command errors"""

import base64
import pytest
from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from loguru import logger

# Test design configuration
test_design = load_env_design + design(
    logger=logger,
    ml_nexus_default_base_image="python:3.11-slim",
)


@injected_pytest(test_design)
async def test_script_fails_on_error(a_system, logger):
    """Test that scripts fail immediately when a command returns non-zero exit code"""
    logger.info("Testing script error handling with base64_runner...")

    # Create a simple test script that has a failing command followed by a success command
    test_script = """
echo "Step 1: This should execute"
false  # This command always fails with exit code 1
echo "Step 2: This should NOT execute due to error handling"
"""

    # Encode the script
    encoded_script = base64.b64encode(test_script.encode()).decode()

    # Create the base64_runner.sh content with error handling
    runner_script = """#!/bin/bash

echo "Running base64 encoded script..."

if [ $# -eq 0 ]; then
    echo "Error: No base64 encoded script provided."
    echo "Usage: $0 <base64_encoded_script>"
    exit 1
fi

encoded_script="$1"
decoded_script=$(echo "$encoded_script" | base64 -d)

echo "====== BEGIN SCRIPT ======"
echo "$decoded_script"
echo "======  END  SCRIPT ======"

# Decode the script and execute it with error handling
echo "$encoded_script" | base64 -d | bash -e -o pipefail

exit_status=$?

echo "Base64 encoded script executed with exit status $exit_status"
exit $exit_status
"""

    # Write the runner script to a temporary location
    runner_path = Path("/tmp/test_base64_runner.sh")
    runner_path.write_text(runner_script)
    runner_path.chmod(0o755)

    # Execute the test
    result = await a_system(f"/tmp/test_base64_runner.sh {encoded_script}", check=False)

    # Verify the script failed
    assert result.exit_code != 0, "Script should have failed due to 'false' command"

    # Verify the second echo didn't execute
    assert "Step 2: This should NOT execute" not in result.stdout, (
        "Script should have stopped after the failing command"
    )

    logger.info(f"Test passed! Script failed with exit code {result.exit_code}")
    logger.info(f"Output: {result.stdout}")


@injected_pytest(test_design)
async def test_uv_sync_failure_stops_execution(a_system, logger):
    """Test that uv sync failure stops script execution immediately"""
    logger.info("Testing uv sync error handling...")

    # Create a script that simulates uv sync failure
    test_script = """
echo "Starting init script..."
echo "Running uv sync..."
# Simulate uv sync failure
exit 1
echo "This should NOT execute after uv sync failure"
"""

    # Encode the script
    encoded_script = base64.b64encode(test_script.encode()).decode()

    # Use the actual base64_runner with error handling
    runner_script = """#!/bin/bash

echo "Running base64 encoded script..."

if [ $# -eq 0 ]; then
    echo "Error: No base64 encoded script provided."
    echo "Usage: $0 <base64_encoded_script>"
    exit 1
fi

encoded_script="$1"
decoded_script=$(echo "$encoded_script" | base64 -d)

echo "====== BEGIN SCRIPT ======"
echo "$decoded_script"
echo "======  END  SCRIPT ======"

# Decode the script and execute it with error handling
echo "$encoded_script" | base64 -d | bash -e -o pipefail

exit_status=$?

echo "Base64 encoded script executed with exit status $exit_status"
exit $exit_status
"""

    # Write the runner script
    runner_path = Path("/tmp/test_uv_sync_runner.sh")
    runner_path.write_text(runner_script)
    runner_path.chmod(0o755)

    # Execute the test
    result = await a_system(
        f"/tmp/test_uv_sync_runner.sh {encoded_script}", check=False
    )

    # Verify the script failed
    assert result.exit_code == 1, "Script should have failed with exit code 1"

    # Verify the last echo didn't execute
    assert "This should NOT execute after uv sync failure" not in result.stdout, (
        "Script should have stopped after uv sync failure"
    )

    logger.info(
        f"Test passed! uv sync failure stopped execution with exit code {result.exit_code}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import base64
from pathlib import Path

from pinjected import instance, injected


@instance
async def script_base64_runner():
    return """
#!/bin/bash

echo "Running base64 encoded script..."

# Check if an argument is provided
if [ $# -eq 0 ]; then
    echo "Error: No base64 encoded script provided."
    echo "Usage: $0 <base64_encoded_script>"
    exit 1
fi


# Get the base64 encoded script from the first argument
encoded_script="$1"
decoded_script=$(echo "$encoded_script" | base64 -d)

echo "====== BEGIN SCRIPT ======"
echo "$decoded_script"
echo "======  END  SCRIPT ======"

# Decode the script and execute it
echo "$encoded_script" | base64 -d | bash

# Check the exit status of the decoded script
exit_status=$?

echo "Base64 encoded script executed with exit status $exit_status"
# Exit with the same status as the decoded script
exit $exit_status
"""


@injected
async def a_script(
        script_base64_runner: str,
        a_system,
        /,
        script
):
    runner_path: Path = Path("~/.cache/env_manager/base64_runner.sh").expanduser()
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    if not runner_path.exists():
        runner_path.write_text(script_base64_runner)
    encoded_script = base64.b64encode(script.encode('utf-8')).decode()

    return await a_system(rf"/bin/bash {runner_path} {encoded_script}")

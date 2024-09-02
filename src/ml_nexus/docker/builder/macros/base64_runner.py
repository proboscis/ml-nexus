from pathlib import Path

from pinjected import *

from ml_nexus.docker.builder.macros.macro_defs import RCopy

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



@instance
async def macro_install_base64_runner(script_base64_runner: str):
    script_path = Path("~/.cache/base64_runner.sh").expanduser()
    script_path.write_text(script_base64_runner)
    return [
        RCopy(src=script_path, dst=Path("/usr/local/bin/base64_runner.sh")),
        "RUN chmod +x /usr/local/bin/base64_runner.sh"
    ]

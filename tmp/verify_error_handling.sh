#!/bin/bash

echo "Testing error handling in base64_runner..."

# Test script with a failing command
TEST_SCRIPT='echo "Step 1: This executes"
false
echo "Step 2: This should NOT execute"'

# Encode the script
ENCODED=$(echo "$TEST_SCRIPT" | base64)

# Create a test runner with error handling
cat > /tmp/test_runner.sh << 'EOF'
#!/bin/bash
encoded_script="$1"
echo "$encoded_script" | base64 -d | bash -e -o pipefail
exit_status=$?
echo "Exit status: $exit_status"
exit $exit_status
EOF

chmod +x /tmp/test_runner.sh

echo "Running test with error handling..."
/tmp/test_runner.sh "$ENCODED" || echo "Script failed as expected!"

echo ""
echo "Now testing without error handling for comparison..."
cat > /tmp/test_runner_no_error.sh << 'EOF'
#!/bin/bash
encoded_script="$1"
echo "$encoded_script" | base64 -d | bash
exit_status=$?
echo "Exit status: $exit_status"
exit $exit_status
EOF

chmod +x /tmp/test_runner_no_error.sh
/tmp/test_runner_no_error.sh "$ENCODED" || echo "Script failed"

echo ""
echo "Test complete!"
#!/bin/bash

RCLONE_CONFIG_PATH="/root/.config/rclone/rclone.conf"
RCLONE_REMOTE_NAME="gdrive" # Default, can be overridden by .env

# Source .env file if it exists to get RCLONE_REMOTE_NAME
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "--- Rclone Setup & Test ---"

# 1. Check if rclone.conf exists in the project root
if [ -f "rclone.conf" ]; then
    echo "Found rclone.conf in project root."
    # Ensure the target directory exists
    mkdir -p "$(dirname "$RCLONE_CONFIG_PATH")"
    # Copy it to the expected location for the container
    cp "rclone.conf" "$RCLONE_CONFIG_PATH"
    echo "Copied rclone.conf to $RCLONE_CONFIG_PATH"
elif [ -f "$RCLONE_CONFIG_PATH" ]; then
    echo "Existing Rclone config found at $RCLONE_CONFIG_PATH."
else
    echo "Rclone config not found."
    echo "Please run 'rclone config' to set up a new remote."
    echo "Follow the prompts. For headless setup, you might need to run this on a local machine and copy the config."
    # The 'rclone config' command is interactive, so we just prompt the user.
    exit 1
fi

# 2. Test the configuration
echo "--- Testing Rclone Configuration ---"
REMOTE_NAME="${RCLONE_REMOTE_NAME:-gdrive}" # Use from .env or default
TEST_FILE="rclone_test_file.txt"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

echo "Creating a test file..."
echo "This is a test file created at $TIMESTAMP" > $TEST_FILE

echo "Attempting to copy to remote: ${REMOTE_NAME}:test_folder/"

# Execute the copy command
rclone copyto "$TEST_FILE" "${REMOTE_NAME}:test_folder/$TEST_FILE" --retries 3

# Check the exit code of the rclone command
if [ $? -eq 0 ]; then
    echo "✅ Test file successfully copied."

    echo "Attempting to delete test file from remote..."
    rclone deletefile "${REMOTE_NAME}:test_folder/$TEST_FILE"

    if [ $? -eq 0 ]; then
        echo "✅ Test file successfully deleted from remote."
    else
        echo "⚠️  Could not delete test file from remote. Please remove it manually."
    fi

    echo "--- Rclone setup appears to be working correctly! ---"
else
    echo "❌ ERROR: Failed to copy test file to remote."
    echo "Please check your rclone configuration and remote name."
fi

# Clean up the local test file
rm $TEST_FILE
echo "Cleaned up local test file."

#!/bin/bash
echo "========================================"
echo "      Wedding App - Rclone Setup        "
echo "========================================"
echo "Use this script to configure the backup remote."
echo ""
echo "IMPORTANT INSTRUCTIONS:"
echo "1. When asked 'Use auto config?', answer 'n' (No)."
echo "2. Rclone will provide a command (e.g., 'rclone authorize \"drive\"')."
echo "3. Run that command ON YOUR LOCAL COMPUTER (not this server)."
echo "4. Paste the result code back here."
echo "========================================"
echo ""
read -p "Press [Enter] to start rclone config..."

# Run rclone config
rclone config

echo ""
echo "Configuration saved."

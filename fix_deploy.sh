#!/bin/bash
set -e

echo "Cleaning up Docker state for Wedding App..."

# Stop containers if running
echo "Stopping containers..."
docker-compose down --remove-orphans || true

# Explicitly remove the named containers if they exist (handles the KeyError case)
echo "Removing containers..."
docker rm -f wedding_app wedding_daemon 2>/dev/null || true

# Prune dangling images to save space (optional)
# echo "Pruning dangling images..."
# docker image prune -f

# Check rclone.conf status
if [ -d "rclone.conf" ]; then
    echo "WARN: rclone.conf is a directory. Removing it..."
    rmdir rclone.conf || rm -rf rclone.conf
fi

if [ ! -f "rclone.conf" ]; then
    echo "Creating empty rclone.conf (preventing Docker from creating a directory)..."
    touch rclone.conf
    echo "Please configure rclone by editing rclone.conf or running 'rclone config' locally and copying content."
fi

echo "Rebuilding and starting..."
if docker-compose up -d --build --force-recreate; then
    echo "Deployment reset complete."
    docker-compose ps
else
    echo ""
    echo "❌ Deployment Failed."
    echo "If you see 'iptables failed' or 'No chain/target/match', run this command:"
    echo "    sudo systemctl restart docker"
    echo "Then run this script again."
    exit 1
fi

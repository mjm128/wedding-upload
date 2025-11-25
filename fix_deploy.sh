#!/bin/bash
set -e

echo "Cleaning up Docker state for Wedding App..."

# Stop containers if running
echo "Stopping containers..."
docker-compose down --remove-orphans || true

# Explicitly remove the named containers if they exist (handles the KeyError case)
echo "Removing containers..."
docker rm -f wedding_app wedding_daemon || true

# Prune dangling images to save space (optional)
# echo "Pruning dangling images..."
# docker image prune -f

echo "Rebuilding and starting..."
docker-compose up -d --build --force-recreate

echo "Deployment reset complete."
docker-compose ps

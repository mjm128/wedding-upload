#!/bin/bash
set -e

if [ "$1" = "app" ]; then
    echo "Starting FastAPI App..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
elif [ "$1" = "daemon" ]; then
    echo "Starting Archive Daemon..."
    exec python daemon/archive_daemon.py
else
    echo "Unknown command: $1"
    exit 1
fi

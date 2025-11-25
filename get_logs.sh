#!/bin/bash
echo "=== Wedding App Logs ==="
docker logs --tail 100 wedding_app
echo ""
echo "=== Wedding Daemon Logs ==="
docker logs --tail 100 wedding_daemon

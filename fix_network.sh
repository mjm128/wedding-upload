#!/bin/bash
+echo "========================================"
+echo "      Fix Docker Network / IP Tables    "
+echo "========================================"
+echo "This script restarts the Docker service to regenerate missing firewall rules."
+echo "It requires sudo privileges."
+echo ""
+
+echo "Restarting Docker..."
+sudo systemctl restart docker
+
+echo "Docker restarted. Waiting 5 seconds..."
+sleep 5
+
+echo "Retrying deployment..."
+./fix_deploy.sh
